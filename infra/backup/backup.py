"""Backup do Jornal Escolar: banco + fotos, criptografados, para o R2 (docs/31).

Roda sozinho todo dia às 3h (arquivo crontab) e à mão com:
    make backup
    docker compose -f infra/docker-compose.yml --env-file infra/env/.env exec backup \
        python /app/backup.py

Passos:
  1. pg_dump do banco para um arquivo temporário.
  2. pg_restore --list confere se o arquivo está íntegro.
  3. Envia o arquivo para banco/ (criptografado pelo rclone).
  4. Sincroniza a pasta de fotos com midia/. Fotos apagadas ou trocadas no site vão para
     midia-removida/<data>/ em vez de sumir.
  5. Retenção: apaga backups do banco além de 7 diários, 4 semanais e 6 mensais, e pastas de
     fotos removidas com mais de 6 meses.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import comum


def contar_arquivos(pasta: Path) -> int:
    return sum(len(arquivos) for _, _, arquivos in os.walk(pasta))


def fazer_backup() -> None:
    momento = comum.agora()
    ambiente = comum.ambiente_rclone()
    destino = os.environ.get("BACKUP_DESTINO", "r2")
    comum.log(f"Backup {comum.carimbo(momento)} para o destino '{destino}'.")

    with tempfile.TemporaryDirectory(prefix="backup-") as temporaria:
        dump = Path(temporaria) / comum.nome_do_dump(momento)
        comum.log("1/5 Exportando o banco (pg_dump)...")
        comum.executar(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump)])

        comum.log("2/5 Conferindo o arquivo (pg_restore --list)...")
        comum.executar(["pg_restore", "--list", str(dump)])
        tamanho = dump.stat().st_size

        comum.log(f"3/5 Enviando {dump.name} ({tamanho / 1024 / 1024:.1f} MB)...")
        comum.rclone(ambiente, "copyto", str(dump), f"cofre:{comum.PASTA_BANCO}/{dump.name}")

    comum.log("4/5 Sincronizando as fotos...")
    midia = Path(comum.MIDIA_LOCAL)
    if not midia.is_dir():
        raise comum.ErroBackup(f"Pasta de fotos {midia} não encontrada no container.")
    # Proteção: pasta local vazia com cópia cheia no destino quase sempre é volume errado.
    # Sincronizar assim moveria todas as fotos para midia-removida.
    if contar_arquivos(midia) == 0 and comum.listar(ambiente, comum.PASTA_MIDIA):
        raise comum.ErroBackup(
            "A pasta de fotos está vazia, mas o backup tem fotos. Nada foi sincronizado. "
            "Confira o volume 'media' antes de continuar."
        )
    comum.rclone(
        ambiente,
        "sync",
        str(midia),
        f"cofre:{comum.PASTA_MIDIA}",
        "--backup-dir",
        f"cofre:{comum.PASTA_MIDIA_REMOVIDA}/{comum.carimbo(momento)}",
    )

    comum.log("5/5 Aplicando a retenção...")
    for nome in comum.backups_para_apagar(comum.listar(ambiente, comum.PASTA_BANCO)):
        comum.log(f"    apagando backup antigo {nome}")
        comum.rclone(ambiente, "deletefile", f"cofre:{comum.PASTA_BANCO}/{nome}")
    pastas = comum.listar(ambiente, comum.PASTA_MIDIA_REMOVIDA, apenas_pastas=True)
    for pasta in comum.pastas_removidas_vencidas(pastas, momento):
        comum.log(f"    apagando fotos removidas em {pasta}")
        comum.rclone(ambiente, "purge", f"cofre:{comum.PASTA_MIDIA_REMOVIDA}/{pasta}")

    comum.log(f"Backup concluído: {comum.PASTA_BANCO}/{comum.nome_do_dump(momento)}")


if __name__ == "__main__":
    comum.principal(fazer_backup)
