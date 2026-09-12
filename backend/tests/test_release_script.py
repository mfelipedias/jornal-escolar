import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release.py"


@pytest.fixture(scope="module")
def release():
    if not SCRIPT.exists():  # o container de testes monta o repositório inteiro; CI também
        pytest.skip("scripts/release.py fora do alcance")
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHANGELOG = """# Changelog

Texto.

## [Não lançado]

### Adicionado

- Coisa nova.

## [0.0.1] - 2026-09-12

- Início.
"""


def test_changelog_moves_unreleased_section(release):
    result = release.update_changelog(CHANGELOG, "0.3.0", "2026-09-13")

    expected = (
        "## [Não lançado]\n\n"
        "## [0.3.0] - 2026-09-13\n\n"
        "### Adicionado\n\n"
        "- Coisa nova.\n\n"
        "## [0.0.1]"
    )
    assert expected in result


def test_empty_unreleased_section_is_refused(release):
    empty = CHANGELOG.replace("### Adicionado\n\n- Coisa nova.\n\n", "")

    with pytest.raises(SystemExit):
        release.update_changelog(empty, "0.3.0", "2026-09-13")


@pytest.mark.parametrize("value", ["v0.3.0", "0.3", "1.2.3.4", "abc"])
def test_invalid_versions(release, value):
    with pytest.raises(SystemExit):
        release.parse(value)


def test_version_comparison(release):
    assert release.parse("0.10.0") > release.parse("0.9.9")
