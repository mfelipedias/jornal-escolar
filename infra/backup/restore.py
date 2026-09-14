"""Restauração do Jornal Escolar a partir do backup (docs/31, "Como restaurar").

Uso (na raiz do repositório, no servidor):
    make backups                                    lista os backups disponíveis
    make restore FILE=mais-recente                  restaura o último
    make restore FILE=jornal-2026-09-14_030000.dump restaura um específico

O que acontece:
  1. Baixa o backup do banco escolhido e confere se está íntegro.
  2. APAGA o banco atual (tabelas e dados) e carrega o backup no lugar.
  3. Traz as fotos: o espelho mais recente e, se o backup for antigo, também as fotos que
     foram apagadas depois daquela data.
Funciona num servidor novo e vazio, inclusive de x86 para ARM: o formato é o mesmo.
Depois: "docker compose ... restart web" (make deploy também serve).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import comum

CONFIRMACAO = "RESTAURAR"


def listar_backups(ambiente: dict) -> list[str]:
    nomes = comum.listar(ambiente, comum.PASTA_BANCO)
    return sorted((n for n in nomes if comum.data_do_dump(n)), key=comum.data_do_dump)


def escolher(nomes: list[str], pedido: str) -> str:
    if not nomes:
        raise comum.ErroBackup("Nenhum backup do banco encontrado no destino.")
    if pedido == "mais-recente":
        return nomes[-1]
    pedido = pedido.removesuffix(".bin").split("/")[-1]
    if pedido not in nomes:
        raise comum.ErroBackup(f"Backup {pedido!r} não existe. Veja a lista com: make backups")
    return pedido


def restaurar(pedido: str, sem_confirmar: bool) -> None:
    ambiente = comum.ambiente_rclone()
    nome = escolher(listar_backups(ambiente), pedido)
    momento = comum.data_do_dump(nome)

    if not sem_confirmar:
        print(f"\nIsto vai APAGAR o banco atual e colocar no lugar o backup {nome}.")
        print(f"Para continuar, digite {CONFIRMACAO} e aperte Enter: ", end="", flush=True)
        if sys.stdin.readline().strip() != CONFIRMACAO:
            raise comum.ErroBackup("Restauração cancelada. Nada foi alterado.")

    with tempfile.TemporaryDirectory(prefix="restore-") as temporaria:
        dump = Path(temporaria) / nome
        comum.log(f"1/4 Baixando {nome}...")
        comum.rclone(ambiente, "copyto", f"cofre:{comum.PASTA_BANCO}/{nome}", str(dump))
        comum.executar(["pg_restore", "--list", str(dump)])

        comum.log("2/4 Limpando o banco atual...")
        limpar = (
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid();"
            "DROP SCHEMA IF EXISTS public CASCADE;"
            "CREATE SCHEMA public;"
        )
        comum.executar(["psql", "--quiet", "--set", "ON_ERROR_STOP=1", "--command", limpar])

        comum.log("3/4 Carregando o backup no banco (pg_restore)...")
        comum.executar(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--dbname",
                os.environ["PGDATABASE"],  # servidor, usuário e senha vêm de PGHOST etc.
                str(dump),
            ]
        )

    comum.log("4/4 Trazendo as fotos...")
    midia = comum.MIDIA_LOCAL
    comum.rclone(ambiente, "sync", f"cofre:{comum.PASTA_MIDIA}", midia)
    removidas = comum.listar(ambiente, comum.PASTA_MIDIA_REMOVIDA, apenas_pastas=True)
    for pasta in comum.pastas_removidas_depois(removidas, momento):
        comum.log(f"    devolvendo fotos apagadas em {pasta}")
        comum.rclone(ambiente, "copy", f"cofre:{comum.PASTA_MIDIA_REMOVIDA}/{pasta}", midia)
    # O site roda com o usuário 1000 (infra/Dockerfile) e precisa poder gravar fotos novas.
    comum.executar(["chown", "-R", "1000:1000", midia])

    comum.log(f"Restauração de {nome} concluída. Reinicie o site: docker compose ... restart web")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura banco e fotos do backup.")
    parser.add_argument(
        "backup", nargs="?", help="nome do backup, 'mais-recente' ou nada para listar"
    )
    parser.add_argument("--sim", action="store_true", help="não pede confirmação")
    argumentos = parser.parse_args()

    if not argumentos.backup:
        nomes = listar_backups(comum.ambiente_rclone())
        print("Backups do banco disponíveis (mais antigo primeiro):")
        for nome in nomes:
            print(f"  {nome}")
        if not nomes:
            print("  (nenhum)")
        return
    restaurar(argumentos.backup, argumentos.sim)


if __name__ == "__main__":
    comum.principal(main)
