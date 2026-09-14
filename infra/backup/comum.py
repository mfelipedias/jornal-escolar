"""Partes compartilhadas pelo backup.py e pelo restore.py (docs/31).

Onde as cópias ficam, dentro do destino (Cloudflare R2 ou uma pasta local):

    banco/jornal-AAAA-MM-DD_HHMMSS.dump.bin    um arquivo por backup do banco
    midia/...                                  espelho da pasta de fotos
    midia-removida/AAAA-MM-DD_HHMMSS/...       fotos apagadas ou trocadas naquele backup

Tudo passa pelo remoto "cofre" do rclone, que criptografa o conteúdo com BACKUP_PASSPHRASE
antes de sair do servidor. Os nomes dos arquivos continuam legíveis (para você conferir as
datas no painel da Cloudflare); o conteúdo não. O ".bin" no fim é colocado pelo rclone.

As funções de retenção não dependem do rclone e são testadas em backend/tests.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

PASTA_BANCO = "banco"
PASTA_MIDIA = "midia"
PASTA_MIDIA_REMOVIDA = "midia-removida"
PASTA_LOCAL = "/backup-local"
MIDIA_LOCAL = "/data/media"

FORMATO_DATA = "%Y-%m-%d_%H%M%S"
NOME_DUMP = re.compile(r"^jornal-(\d{4}-\d{2}-\d{2}_\d{6})\.dump$")
NOME_PASTA_DATA = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{6})/?$")

# Quantos backups do banco guardar (docs/24): 7 diários, 4 semanais e 6 mensais.
DIARIOS = 7
SEMANAIS = 4
MENSAIS = 6
# Fotos apagadas continuam recuperáveis por este tempo e depois somem de vez (LGPD, docs/23).
DIAS_MIDIA_REMOVIDA = 186

TAMANHO_MINIMO_SENHA = 12


class ErroBackup(Exception):
    """Falha com mensagem para pessoas: o script mostra só o texto, sem rastro de código."""


def agora() -> datetime:
    return datetime.now()


def carimbo(momento: datetime) -> str:
    return momento.strftime(FORMATO_DATA)


def nome_do_dump(momento: datetime) -> str:
    return f"jornal-{carimbo(momento)}.dump"


def data_do_dump(nome: str) -> datetime | None:
    """Data de um arquivo de backup do banco, ou None se o nome não segue o padrão."""
    nome = nome.removesuffix(".bin")
    encontrado = NOME_DUMP.match(nome)
    if not encontrado:
        return None
    return datetime.strptime(encontrado.group(1), FORMATO_DATA)


def data_da_pasta(nome: str) -> datetime | None:
    encontrado = NOME_PASTA_DATA.match(nome)
    if not encontrado:
        return None
    return datetime.strptime(encontrado.group(1), FORMATO_DATA)


def backups_mantidos(
    nomes: list[str], diarios: int = DIARIOS, semanais: int = SEMANAIS, mensais: int = MENSAIS
) -> set[str]:
    """Escolhe quais backups do banco ficam (esquema avô-pai-filho).

    Ficam todos os backups dos últimos `diarios` dias que têm backup (inclusive os feitos à
    mão, por exemplo antes de uma mudança grande), o mais recente de cada uma das últimas
    `semanais` semanas e o mais recente de cada um dos últimos `mensais` meses. Um mesmo
    arquivo pode contar para mais de uma regra.
    """
    datados = sorted(
        ((data, nome) for nome in nomes if (data := data_do_dump(nome)) is not None),
        reverse=True,
    )
    dias_recentes = sorted({data.date() for data, _ in datados}, reverse=True)[:diarios]
    mantidos: set[str] = {nome for data, nome in datados if data.date() in dias_recentes}

    regras = (
        (lambda data: tuple(data.isocalendar())[:2], semanais),
        (lambda data: (data.year, data.month), mensais),
    )
    for periodo, limite in regras:
        vistos: set = set()
        for data, nome in datados:
            chave = periodo(data)
            if chave in vistos:
                continue
            if len(vistos) >= limite:
                break
            vistos.add(chave)
            mantidos.add(nome)
    return mantidos


def backups_para_apagar(nomes: list[str]) -> list[str]:
    """Backups do banco que saem pela retenção. Arquivos com outro nome nunca são apagados."""
    mantidos = backups_mantidos(nomes)
    return sorted(nome for nome in nomes if data_do_dump(nome) and nome not in mantidos)


def pastas_removidas_vencidas(
    pastas: list[str], momento: datetime, dias: int = DIAS_MIDIA_REMOVIDA
) -> list[str]:
    limite = momento - timedelta(days=dias)
    return sorted(
        pasta for pasta in pastas if (data := data_da_pasta(pasta)) is not None and data < limite
    )


def pastas_removidas_depois(pastas: list[str], momento: datetime) -> list[str]:
    """Pastas de fotos removidas depois de `momento`: voltam quando se restaura um backup antigo."""
    return sorted(
        pasta for pasta in pastas if (data := data_da_pasta(pasta)) is not None and data > momento
    )


# --- rclone ----------------------------------------------------------------------------------


def log(mensagem: str) -> None:
    print(f"[{agora():%Y-%m-%d %H:%M:%S}] {mensagem}", flush=True)


def executar(comando: list[str], ambiente: dict | None = None, **opcoes) -> str:
    """Roda um programa e devolve a saída; se ele falhar, levanta ErroBackup com o erro."""
    resultado = subprocess.run(
        comando, env=ambiente, capture_output=True, text=True, check=False, **opcoes
    )
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout).strip()
        raise ErroBackup(f"'{comando[0]} {comando[1]}' falhou: {detalhe}")
    return resultado.stdout


def ambiente_rclone() -> dict:
    """Variáveis que configuram os remotos "destino" (R2 ou pasta) e "cofre" (criptografia).

    Nada é gravado em disco: o rclone lê a configuração destas variáveis.
    """
    ambiente = dict(os.environ)
    ambiente["RCLONE_CONFIG"] = "/dev/null"

    senha = os.environ.get("BACKUP_PASSPHRASE", "")
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ErroBackup(
            f"BACKUP_PASSPHRASE vazia ou curta (mínimo {TAMANHO_MINIMO_SENHA} caracteres). "
            "Defina a senha em infra/env/.env (docs/31)."
        )

    destino = os.environ.get("BACKUP_DESTINO", "r2").strip().lower()
    if destino == "r2":
        obrigatorias = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
        faltando = [nome for nome in obrigatorias if not os.environ.get(nome)]
        if faltando:
            raise ErroBackup(f"Faltam no infra/env/.env: {', '.join(faltando)} (docs/31).")
        ambiente.update(
            RCLONE_CONFIG_DESTINO_TYPE="s3",
            RCLONE_CONFIG_DESTINO_PROVIDER="Cloudflare",
            RCLONE_CONFIG_DESTINO_ACCESS_KEY_ID=os.environ["R2_ACCESS_KEY_ID"],
            RCLONE_CONFIG_DESTINO_SECRET_ACCESS_KEY=os.environ["R2_SECRET_ACCESS_KEY"],
            RCLONE_CONFIG_DESTINO_ENDPOINT=(
                f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
            ),
            RCLONE_CONFIG_DESTINO_REGION="auto",
            # A chave do R2 só enxerga o próprio bucket e não pode criá-lo.
            RCLONE_CONFIG_DESTINO_NO_CHECK_BUCKET="true",
        )
        base = f"destino:{os.environ['R2_BUCKET']}"
    elif destino == "local":
        ambiente["RCLONE_CONFIG_DESTINO_TYPE"] = "local"
        base = f"destino:{PASTA_LOCAL}"
    else:
        raise ErroBackup(f"BACKUP_DESTINO deve ser 'r2' ou 'local', não {destino!r}.")

    # O rclone guarda a senha "embaralhada"; "rclone obscure -" lê do stdin, sem expor na tela.
    senha_rclone = executar(["rclone", "obscure", "-"], ambiente, input=senha).strip()
    ambiente.update(
        RCLONE_CONFIG_COFRE_TYPE="crypt",
        RCLONE_CONFIG_COFRE_REMOTE=base,
        RCLONE_CONFIG_COFRE_PASSWORD=senha_rclone,
        RCLONE_CONFIG_COFRE_FILENAME_ENCRYPTION="off",
        RCLONE_CONFIG_COFRE_DIRECTORY_NAME_ENCRYPTION="false",
    )
    return ambiente


def rclone(ambiente: dict, *argumentos: str) -> str:
    try:
        return executar(["rclone", *argumentos], ambiente)
    except ErroBackup as erro:
        if "bad password" in str(erro):
            raise ErroBackup(
                "A BACKUP_PASSPHRASE não é a mesma usada para criar este backup. "
                "Confira a senha guardada fora do servidor (docs/31)."
            ) from erro
        raise


def listar(ambiente: dict, pasta: str, apenas_pastas: bool = False) -> list[str]:
    opcoes = ["--dirs-only"] if apenas_pastas else ["--files-only"]
    try:
        saida = rclone(ambiente, "lsf", *opcoes, f"cofre:{pasta}")
    except ErroBackup as erro:
        if "not found" in str(erro):  # pasta ainda não existe: primeiro backup
            return []
        raise
    return [linha.rstrip("/") for linha in saida.splitlines() if linha.strip()]


def principal(funcao) -> None:
    """Roda `funcao` mostrando só a mensagem de erro, com código de saída 1 em caso de falha."""
    try:
        funcao()
    except ErroBackup as erro:
        log(f"ERRO: {erro}")
        sys.exit(1)
