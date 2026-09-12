import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.core.models import SiteSetting, StaticPage
from apps.core.services import seed_site

pytestmark = pytest.mark.django_db


@pytest.fixture
def about():
    return StaticPage.objects.create(
        slug=StaticPage.Slug.ABOUT,
        title="Sobre o jornal",
        lead="Linha fina",
        body="Primeiro parágrafo.\n\nSegundo parágrafo.",
    )


def test_urls():
    assert reverse("core:page", kwargs={"slug": "sobre"}) == "/sobre/"
    assert reverse("core:page", kwargs={"slug": "privacidade"}) == "/privacidade/"
    assert reverse("core:page", kwargs={"slug": "colaborar"}) == "/colaborar/"


def test_page_renders_paragraphs(client, about):
    response = client.get("/sobre/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "<title>Sobre o jornal · Jornal Escolar</title>" in html
    assert "<p>Primeiro parágrafo.</p>" in html
    assert "<p>Segundo parágrafo.</p>" in html
    assert html.count("<h1") == 1


def test_missing_or_unpublished_page_is_404(client, about):
    about.is_published = False
    about.save()

    assert client.get("/sobre/").status_code == 404
    assert client.get("/privacidade/").status_code == 404


def test_other_slugs_are_not_pages(client):
    StaticPage.objects.create(slug="sobre", title="Sobre")

    assert client.get("/qualquer-coisa/").status_code == 404


def test_page_body_is_escaped(client):
    StaticPage.objects.create(slug="sobre", title="Sobre", body="<script>alert(1)</script>")

    html = client.get("/sobre/").content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_footer_links_only_published_pages(client, about):
    StaticPage.objects.create(slug="privacidade", title="Privacidade", is_published=False)

    html = client.get("/").content.decode()

    assert 'href="/sobre/"' in html
    assert 'href="/privacidade/"' not in html


def test_footer_updates_after_publishing(client, about):
    client.get("/")
    StaticPage.objects.create(slug="colaborar", title="Como participar")

    html = client.get("/").content.decode()

    assert 'href="/colaborar/"' in html


def test_seed_site_is_idempotent():
    first = seed_site()
    second = seed_site()

    assert first["páginas"] == 3
    assert second == {"configurações": 0, "páginas": 0}
    assert not StaticPage.objects.get(slug="privacidade").is_published
    assert SiteSetting.objects.filter(key="site.name").exists()


def test_seed_site_command(capsys):
    call_command("seed_site")

    assert "Páginas: 3 criadas" in capsys.readouterr().out


def test_admin_records_who_updated(admin_client, admin_user, about):
    response = admin_client.post(
        reverse("admin:core_staticpage_change", args=[about.pk]),
        {
            "slug": "sobre",
            "title": "Sobre (novo)",
            "lead": "",
            "body": "Texto",
            "is_published": "on",
        },
    )

    assert response.status_code == 302
    about.refresh_from_db()
    assert about.title == "Sobre (novo)"
    assert about.updated_by == admin_user
