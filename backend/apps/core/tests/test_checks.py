import pytest

from apps.core.checks import check_site_url


def ids(settings_url, settings):
    settings.SITE_URL = settings_url
    return [problema.id for problema in check_site_url()]


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://jornal.projetosrosa.com.br", []),
        ("https://jornal.projetosrosa.com.br/", []),
        ("http://localhost:8000", ["core.W001"]),
        ("http://127.0.0.1:8088", ["core.W001"]),
        ("localhost", ["core.W001"]),
        ("http://jornal.projetosrosa.com.br", ["core.W002"]),
        ("https://jornal.projetosrosa.com.br/jornal", ["core.W003"]),
    ],
)
def test_site_url_de_producao(settings, url, esperado):
    assert ids(url, settings) == esperado


def test_verificacao_roda_no_check_deploy(settings):
    from django.core import checks

    settings.SITE_URL = "http://localhost:8000"

    problemas = checks.run_checks(include_deployment_checks=True, tags=[checks.Tags.urls])

    assert "core.W001" in [problema.id for problema in problemas]
