"""Regras do backup (infra/backup/comum.py) e coerência dos arquivos de produção (E27).

O backup e o restore de verdade foram testados com o Compose de produção (docs/34,
"Teste de restauração"); aqui ficam as partes que não precisam de Docker.
"""

import importlib.util
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
INFRA = REPO / "infra"


def carregar(caminho: Path, nome: str):
    if not caminho.exists():  # o container de testes monta o repositório inteiro; CI também
        pytest.skip(f"{caminho} fora do alcance")
    sys.path.insert(0, str(caminho.parent))
    try:
        spec = importlib.util.spec_from_file_location(nome, caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(caminho.parent))
    return modulo


@pytest.fixture(scope="module")
def comum():
    return carregar(INFRA / "backup" / "comum.py", "comum")


@pytest.fixture(scope="module")
def restore(comum):
    sys.modules.setdefault("comum", comum)
    return carregar(INFRA / "backup" / "restore.py", "restore_backup")


@pytest.fixture(scope="module")
def healthcheck():
    return carregar(INFRA / "scripts" / "healthcheck.py", "healthcheck")


def dump(comum, momento: datetime) -> str:
    return comum.nome_do_dump(momento)


# --- nomes -------------------------------------------------------------------------------------


def test_nome_do_dump_ida_e_volta(comum):
    momento = datetime(2026, 9, 14, 3, 0, 5)
    nome = comum.nome_do_dump(momento)

    assert nome == "jornal-2026-09-14_030005.dump"
    assert comum.data_do_dump(nome) == momento
    assert comum.data_do_dump(nome + ".bin") == momento


@pytest.mark.parametrize(
    "nome", ["LEIA-ME.txt", "jornal-2026-09-14.dump", "outro-2026-09-14_030000.dump", ""]
)
def test_nomes_fora_do_padrao_nao_tem_data(comum, nome):
    assert comum.data_do_dump(nome) is None


# --- retenção do banco ----------------------------------------------------------------------


def test_um_backup_por_dia_por_um_ano_mantem_7_diarios_4_semanais_6_mensais(comum):
    inicio = datetime(2025, 9, 15, 3, 0, 0)
    nomes = [dump(comum, inicio + timedelta(days=dia)) for dia in range(365)]
    ultimo = inicio + timedelta(days=364)

    mantidos = comum.backups_mantidos(nomes)
    apagar = comum.backups_para_apagar(nomes)

    datas = sorted(comum.data_do_dump(nome) for nome in mantidos)
    assert set(apagar) == set(nomes) - mantidos
    # Os 7 últimos dias estão todos lá.
    assert all(dump(comum, ultimo - timedelta(days=d)) in mantidos for d in range(7))
    # Nada além de 6 meses e poucos arquivos no total (7 + até 4 + até 6, com sobreposição).
    assert datas[0] >= ultimo - timedelta(days=31 * 6)
    assert len(mantidos) <= 17
    # Um de cada um dos 6 meses mais recentes.
    meses = {(data.year, data.month) for data in datas}
    assert len(meses) == 6


def test_backups_extras_do_mesmo_dia_ficam_nos_dias_recentes(comum):
    dia = datetime(2026, 9, 14)
    madrugada = dump(comum, dia.replace(hour=3))
    antes_da_mudanca = dump(comum, dia.replace(hour=14))
    depois = dump(comum, dia.replace(hour=16))

    assert comum.backups_para_apagar([madrugada, antes_da_mudanca, depois]) == []


def test_extra_de_dia_antigo_sai_mas_o_mais_recente_da_semana_fica(comum):
    antigo = datetime(2026, 8, 3)  # segunda-feira
    extra = dump(comum, antigo.replace(hour=3))
    fim_da_semana = dump(comum, antigo.replace(hour=15))
    recentes = [dump(comum, datetime(2026, 9, 14) - timedelta(days=d)) for d in range(7)]

    apagar = comum.backups_para_apagar([extra, fim_da_semana, *recentes])

    assert apagar == [extra]


def test_arquivos_com_outro_nome_nunca_sao_apagados(comum):
    nomes = [dump(comum, datetime(2026, 1, 1) + timedelta(days=d)) for d in range(200)]
    nomes.append("copia-manual-importante.dump")

    assert "copia-manual-importante.dump" not in comum.backups_para_apagar(nomes)


def test_poucos_backups_nada_e_apagado(comum):
    nomes = [dump(comum, datetime(2026, 9, 1) + timedelta(days=d)) for d in range(3)]

    assert comum.backups_para_apagar(nomes) == []


# --- fotos removidas ---------------------------------------------------------------------------


def test_pastas_de_fotos_removidas_vencem_depois_de_6_meses(comum):
    agora = datetime(2026, 9, 14, 3, 0, 0)
    velha = "2026-03-01_030000"
    recente = "2026-08-01_030000"

    assert comum.pastas_removidas_vencidas([velha, recente, "estranha"], agora) == [velha]


def test_restaurar_backup_antigo_traz_fotos_removidas_depois_dele(comum):
    momento = datetime(2026, 9, 10, 3, 0, 0)
    pastas = ["2026-09-09_030000", "2026-09-11_030000", "2026-09-12_030000", "lixo"]

    assert comum.pastas_removidas_depois(pastas, momento) == [
        "2026-09-11_030000",
        "2026-09-12_030000",
    ]


# --- configuração do rclone ------------------------------------------------------------------


def test_senha_curta_para_antes_de_chamar_o_rclone(comum, monkeypatch):
    monkeypatch.setenv("BACKUP_PASSPHRASE", "curta")

    with pytest.raises(comum.ErroBackup, match="BACKUP_PASSPHRASE"):
        comum.ambiente_rclone()


def test_r2_sem_chaves_explica_o_que_falta(comum, monkeypatch):
    monkeypatch.setenv("BACKUP_PASSPHRASE", "uma frase longa o bastante")
    monkeypatch.setenv("BACKUP_DESTINO", "r2")
    for nome in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("R2_BUCKET", "jornal-backup")

    with pytest.raises(comum.ErroBackup, match="R2_ACCOUNT_ID, R2_ACCESS_KEY_ID"):
        comum.ambiente_rclone()


def test_destino_desconhecido(comum, monkeypatch):
    monkeypatch.setenv("BACKUP_PASSPHRASE", "uma frase longa o bastante")
    monkeypatch.setenv("BACKUP_DESTINO", "dropbox")

    with pytest.raises(comum.ErroBackup, match="BACKUP_DESTINO"):
        comum.ambiente_rclone()


def test_r2_monta_endpoint_e_criptografia(comum, monkeypatch):
    monkeypatch.setenv("BACKUP_PASSPHRASE", "uma frase longa o bastante")
    monkeypatch.setenv("BACKUP_DESTINO", "r2")
    monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "chave")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "segredo")
    monkeypatch.setenv("R2_BUCKET", "jornal-backup")
    chamadas = []

    def falso_executar(comando, ambiente=None, **opcoes):
        chamadas.append((comando, opcoes))
        return "senha-embaralhada\n"

    monkeypatch.setattr(comum, "executar", falso_executar)

    ambiente = comum.ambiente_rclone()

    assert ambiente["RCLONE_CONFIG_DESTINO_ENDPOINT"] == "https://abc123.r2.cloudflarestorage.com"
    assert ambiente["RCLONE_CONFIG_COFRE_REMOTE"] == "destino:jornal-backup"
    assert ambiente["RCLONE_CONFIG_COFRE_TYPE"] == "crypt"
    assert ambiente["RCLONE_CONFIG_COFRE_PASSWORD"] == "senha-embaralhada"
    # A senha vai pelo stdin, nunca na linha de comando.
    comando, opcoes = chamadas[0]
    assert comando == ["rclone", "obscure", "-"]
    assert opcoes["input"] == "uma frase longa o bastante"


# --- restore -----------------------------------------------------------------------------------


def test_restore_escolhe_mais_recente_ou_pelo_nome(restore):
    nomes = ["jornal-2026-09-13_030000.dump", "jornal-2026-09-14_030000.dump"]

    assert restore.escolher(nomes, "mais-recente") == "jornal-2026-09-14_030000.dump"
    assert restore.escolher(nomes, "banco/jornal-2026-09-13_030000.dump.bin") == nomes[0]


def test_restore_recusa_nome_inexistente(restore, comum):
    with pytest.raises(comum.ErroBackup, match="não existe"):
        restore.escolher(["jornal-2026-09-14_030000.dump"], "jornal-2020-01-01_030000.dump")


# --- healthcheck do container ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("allowed_hosts", "esperado"),
    [
        ("jornal.projetosrosa.com.br,localhost", "jornal.projetosrosa.com.br"),
        (" .projetosrosa.com.br ", "projetosrosa.com.br"),
        ("*", "localhost"),
        ("", "localhost"),
    ],
)
def test_healthcheck_usa_host_permitido(healthcheck, monkeypatch, allowed_hosts, esperado):
    monkeypatch.setenv("ALLOWED_HOSTS", allowed_hosts)

    assert healthcheck.host() == esperado


# --- coerência dos arquivos de produção ------------------------------------------------------


def test_toda_variavel_do_compose_esta_no_modelo_de_env():
    compose = INFRA / "docker-compose.yml"
    modelo = INFRA / "env" / ".env.producao.example"
    if not compose.exists():
        pytest.skip("infra/ fora do alcance")

    usadas = set(re.findall(r"\$\{([A-Z0-9_]+)", compose.read_text(encoding="utf-8")))
    documentadas = set(
        re.findall(r"^#?\s*([A-Z0-9_]+)=", modelo.read_text(encoding="utf-8"), re.MULTILINE)
    )

    assert usadas - documentadas == set()


def test_modelo_de_env_nao_tem_nome_da_escola_nem_segredo_real():
    modelo = (INFRA / "env" / ".env.producao.example").read_text(encoding="utf-8")

    assert "CLOUDFLARE_TUNNEL_TOKEN=\n" in modelo
    assert "R2_SECRET_ACCESS_KEY=\n" in modelo
    assert "SITE_URL=https://" in modelo
