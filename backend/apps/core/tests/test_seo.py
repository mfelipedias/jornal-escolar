"""SEO do site: robots.txt, sitemap.xml, home, páginas de navegação e noindex (E26)."""

import json
import re
from xml.etree import ElementTree

import pytest
from django.test import RequestFactory

from apps.accounts.services import deactivate_user
from apps.core import seo
from apps.core.models import SiteSetting, StaticPage
from apps.core.site_settings import clear_cache
from apps.publications import services
from apps.publications.models import Article
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

SITE = "https://jornal.exemplo.org"
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture(autouse=True)
def site_url(settings):
    settings.SITE_URL = SITE


def sitemap_urls(client) -> list[str]:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    return [loc.text for loc in root.findall("s:url/s:loc", SITEMAP_NS)]


def publish(author, **fields):
    article = ArticleFactory(ready=True, author=author, created_by=author, **fields)
    services.publish(author, article)
    return Article.objects.get(pk=article.pk)


# --- robots.txt ---


def test_robots_txt(client):
    response = client.get("/robots.txt")

    body = response.content.decode()
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert body.startswith("User-agent: *\n")
    for path in ("/painel/", "/admin/", "/entrar/", "/x/", "/publicacoes/previa/"):
        assert f"Disallow: {path}\n" in body
    assert f"Sitemap: {SITE}/sitemap.xml" in body


# --- sitemap.xml ---


def test_sitemap_lists_public_pages_only(client):
    author = UserFactory(full_name="Carla Souza")
    hidden = UserFactory(full_name="Oculto")
    hidden.profile.is_public = False
    hidden.profile.save()
    article = publish(author, title="No ar")
    draft = ArticleFactory(author=author, created_by=author, title="Rascunho")
    archived = publish(author, title="Arquivada")
    services.archive(author, archived)
    StaticPage.objects.create(slug="sobre", title="Sobre")
    StaticPage.objects.create(slug="privacidade", title="Privacidade", is_published=False)
    area = KnowledgeAreaFactory(slug="natureza")
    discipline = DisciplineFactory(slug="fisica", area=area)
    KnowledgeAreaFactory(slug="inativa", is_active=False)
    article_type = ArticleTypeFactory(slug="noticia")

    urls = sitemap_urls(client)

    assert f"{SITE}/" in urls
    assert f"{SITE}/publicacoes/" in urls
    assert f"{SITE}/agenda/" in urls
    assert f"{SITE}/professores/" in urls
    assert f"{SITE}{article.get_absolute_url()}" in urls
    assert f"{SITE}/sobre/" in urls
    assert f"{SITE}{area.get_absolute_url()}" in urls
    assert f"{SITE}{discipline.get_absolute_url()}" in urls
    assert f"{SITE}{article_type.get_absolute_url()}" in urls
    assert f"{SITE}{author.profile.get_absolute_url()}" in urls

    assert f"{SITE}/privacidade/" not in urls
    assert f"{SITE}/areas/inativa/" not in urls
    assert f"{SITE}{hidden.profile.get_absolute_url()}" not in urls
    assert f"{SITE}{archived.get_absolute_url()}" not in urls
    assert not any(str(draft.pk) in url and "previa" in url for url in urls)
    assert not any("/painel/" in url or "/entrar/" in url for url in urls)
    assert all(url.startswith(SITE) for url in urls)


def test_sitemap_deactivated_profile_only_with_credits(client):
    with_credit = UserFactory(full_name="Com Crédito")
    publish(with_credit)
    without_credit = UserFactory(full_name="Sem Crédito")
    deactivate_user(with_credit)
    deactivate_user(without_credit)

    urls = sitemap_urls(client)

    assert f"{SITE}{with_credit.profile.get_absolute_url()}" in urls
    assert f"{SITE}{without_credit.profile.get_absolute_url()}" not in urls


# --- home ---


def test_home_has_website_json_ld_and_default_image(client):
    html = client.get("/").content.decode()

    [data] = [json.loads(block) for block in JSON_LD_RE.findall(html)]
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "WebSite"
    assert data["name"] == "Jornal Escolar"
    assert data["url"] == f"{SITE}/"
    assert data["publisher"]["@type"] == "NewsMediaOrganization"
    assert data["publisher"]["name"] == "Jornal Escolar"
    assert f'<link rel="canonical" href="{SITE}/">' in html
    assert f'<meta property="og:image" content="{SITE}/static/img/og-default.png">' in html


def test_home_description_setting(client):
    SiteSetting.objects.create(key="site.description", value="Notícias e projetos da escola.")
    clear_cache()

    html = client.get("/").content.decode()

    assert 'content="Notícias e projetos da escola."' in html
    assert json.loads(JSON_LD_RE.findall(html)[0])["description"] == (
        "Notícias e projetos da escola."
    )


# --- páginas de navegação ---


def test_static_page_uses_lead_as_description(client):
    StaticPage.objects.create(
        slug="sobre", title="Sobre o jornal", lead="Quem somos e o que fazemos."
    )

    html = client.get("/sobre/").content.decode()

    assert re.search(r'<meta name="description"\s+content="Quem somos e o que fazemos.">', html)
    assert '<meta property="og:description" content="Quem somos e o que fazemos.">' in html
    assert f'<link rel="canonical" href="{SITE}/sobre/">' in html


@pytest.mark.parametrize(
    ("url", "canonical"),
    [
        ("/publicacoes/", "/publicacoes/"),
        ("/publicacoes/?tipo=x&pagina=2", "/publicacoes/?pagina=2"),
        ("/agenda/", "/agenda/"),
        ("/areas/natureza/?disciplina=fisica", "/areas/natureza/"),
        ("/disciplinas/fisica/", "/disciplinas/fisica/"),
        ("/tipos/noticia/", "/tipos/noticia/"),
    ],
)
def test_navigation_pages_have_canonical_and_og(client, url, canonical):
    DisciplineFactory(slug="fisica", area=KnowledgeAreaFactory(slug="natureza"))
    ArticleTypeFactory(slug="noticia")

    html = client.get(url).content.decode()

    assert f'<link rel="canonical" href="{SITE}{canonical}">' in html
    assert '<meta property="og:title"' in html


# --- noindex ---


def test_login_is_noindex(client):
    html = client.get("/entrar/").content.decode()

    assert html.count('<meta name="robots" content="noindex">') == 1
    assert "og:title" not in html


def test_dashboard_is_noindex(client, staff_user):
    client.force_login(staff_user)

    html = client.get("/painel/").content.decode()

    assert '<meta name="robots" content="noindex">' in html
    assert "application/ld+json" not in html


# --- utilitários ---


def test_json_ld_script_escapes_html():
    script = seo.json_ld_script({"headline": "</script><script>alert(1)</script> & ç"})

    assert "<" not in script
    assert ">" not in script
    assert "&" not in script.replace("\\u0026", "")
    assert json.loads(script) == {"headline": "</script><script>alert(1)</script> & ç"}


def test_absolute_url_uses_site_url():
    assert seo.absolute_url("/publicacoes/x/") == f"{SITE}/publicacoes/x/"
    assert seo.absolute_url("https://cdn.exemplo/x.png") == "https://cdn.exemplo/x.png"
    assert seo.absolute_url("") == ""


def test_shorten():
    assert seo.shorten("  curto\n texto ") == "curto texto"
    long = "palavra " * 40
    assert len(seo.shorten(long)) <= 160
    assert seo.shorten(long).endswith("palavra…")


def test_listing_path_keeps_only_page():
    request = RequestFactory().get("/publicacoes/", {"area": "x", "pagina": "3"})

    assert seo.listing_path(request) == "/publicacoes/?pagina=3"
    assert seo.listing_path(RequestFactory().get("/agenda/?pagina=1")) == "/agenda/"
