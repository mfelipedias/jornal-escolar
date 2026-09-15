import re

import pytest
from django.conf import settings

from apps.core.context_processors import split_wordmark
from apps.core.site_settings import REGISTRY

SITE_DEFAULTS = {
    "footer_credit": REGISTRY["site.footer_credit"].default,
    "contact_email": REGISTRY["site.contact_email"].default,
}

pytestmark = pytest.mark.django_db

MONTHS_PT = {
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
}  # fmt: skip


@pytest.fixture
def home(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.content.decode()


def test_home_uses_public_layout(client):
    response = client.get("/")

    templates = [t.name for t in response.templates]
    assert "core/home.html" in templates
    assert "layouts/public.html" in templates
    assert "components/masthead.html" in templates
    assert "components/footer.html" in templates


def test_home_basics(home):
    assert '<html lang="pt-BR">' in home
    assert 'href="#conteudo"' in home
    assert 'id="conteudo"' in home
    assert home.count("<h1") == 1


def test_masthead_wordmark_and_glyph(home):
    assert "Jornal" in home
    assert '<span class="wordmark-accent">Escolar</span>' in home
    assert "<svg" in home


def test_masthead_date_is_lowercase_portuguese(home):
    match = re.search(r"(\w+-?\w*), (\d{1,2}) de (\w+) de (\d{4})</p>", home)

    assert match is not None
    weekday, _, month, _ = match.groups()
    assert weekday == weekday.lower()
    assert month == month.lower()
    assert month in MONTHS_PT


def test_footer_credit_email_and_version(home):
    assert SITE_DEFAULTS["footer_credit"] in home
    assert f'href="mailto:{SITE_DEFAULTS["contact_email"]}"' in home
    assert f"v{settings.APP_VERSION}" in home


def test_school_name_never_appears(home):
    lowered = home.lower()
    assert "[omitido]" not in lowered
    assert "jornal da rosa" not in lowered


def test_assets_come_from_vite(home):
    assert "src/js/app.js" in home
    assert "fonts.googleapis.com" not in home


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Jornal Escolar", ("Jornal", "Escolar")),
        ("Jornal da Escola Nova", ("Jornal da Escola", "Nova")),
        ("Gazeta", ("", "Gazeta")),
    ],
)
def test_split_wordmark(name, expected):
    assert split_wordmark(name) == expected
