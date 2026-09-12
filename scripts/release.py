"""Cria uma versão do Jornal Escolar (docs/30, "Mecânica").

Uso (na raiz do repositório):
    make release VERSION=0.3.0
    uv run --directory backend python ../scripts/release.py 0.3.0

1. Confere o formato SemVer, que a árvore do git está limpa e que a versão é maior que a atual.
2. Escreve o arquivo VERSION.
3. Move a seção "[Não lançado]" do CHANGELOG.md para "[X.Y.Z] - AAAA-MM-DD" e abre uma nova vazia.
4. Faz o commit "release: vX.Y.Z" e cria a tag "vX.Y.Z".

Não faz push nem deploy: lembra de rodar "git push --follow-tags" depois.
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
UNRELEASED = "## [Não lançado]"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return result.stdout.strip()


def parse(version: str) -> tuple[int, int, int]:
    match = SEMVER.match(version)
    if not match:
        raise SystemExit(f"Versão inválida: {version!r}. Use o formato 1.2.3, sem 'v'.")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def update_changelog(text: str, version: str, today: str) -> str:
    if UNRELEASED not in text:
        raise SystemExit("CHANGELOG.md não tem a seção '## [Não lançado]'.")
    head, _, rest = text.partition(UNRELEASED)
    # Conteúdo da seção vai até o próximo "## [" (versão anterior).
    next_section = rest.find("\n## [")
    body = rest if next_section == -1 else rest[:next_section]
    tail = "" if next_section == -1 else rest[next_section:]
    if not body.strip():
        raise SystemExit("A seção '[Não lançado]' está vazia: nada para lançar.")
    return f"{head}{UNRELEASED}\n\n## [{version}] - {today}\n\n{body.strip()}\n{tail}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("version", help="Nova versão, ex.: 0.3.0")
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra o que faria, sem alterar nada"
    )
    args = parser.parse_args()

    new = parse(args.version)
    current_text = VERSION_FILE.read_text(encoding="utf-8").strip()
    if new <= parse(current_text):
        raise SystemExit(
            f"A nova versão ({args.version}) precisa ser maior que a atual ({current_text})."
        )
    if git("status", "--porcelain"):
        raise SystemExit("Há alterações não commitadas. Faça o commit antes de lançar uma versão.")
    tag = f"v{args.version}"
    if git("tag", "--list", tag):
        raise SystemExit(f"A tag {tag} já existe.")

    changelog = update_changelog(
        CHANGELOG.read_text(encoding="utf-8"), args.version, date.today().isoformat()
    )
    if args.dry_run:
        print(f"[simulação] VERSION: {current_text} -> {args.version}; tag {tag}")
        return

    VERSION_FILE.write_text(f"{args.version}\n", encoding="utf-8", newline="\n")
    CHANGELOG.write_text(changelog, encoding="utf-8", newline="\n")
    git("add", "VERSION", "CHANGELOG.md")
    git("commit", "-m", f"release: {tag}")
    git("tag", "-a", tag, "-m", f"Jornal Escolar {tag}")
    print(f"Versão {tag} criada. Envie com: git push --follow-tags")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Erro no git: {exc.stderr or exc}")
