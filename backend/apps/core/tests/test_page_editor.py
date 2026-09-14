"""Páginas institucionais no painel, com o editor das publicações (E25, docs/18)."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse

from apps.core import services
from apps.core.models import StaticPage
from tests.factories import UserFactory, text_doc

pytestmark = pytest.mark.django_db


@pytest.fixture
def about():
    services.seed_site()
    return StaticPage.objects.get(slug="sobre")


def put(client, page, payload):
    return client.put(
        reverse("core:page_save_body", args=[page.slug]),
        data=json.dumps(payload),
        content_type="application/json",
    )


# --- telas ---


def test_urls():
    assert reverse("core:page_list") == "/painel/paginas/"
    assert reverse("core:page_edit", args=["sobre"]) == "/painel/paginas/sobre/editar/"
    assert reverse("core:page_save_body", args=["colaborar"]) == "/x/pages/colaborar/body/"


def test_list_requires_editor(client, staff_user):
    assert client.get(reverse("core:page_list")).status_code == 302
    client.force_login(staff_user)

    assert client.get(reverse("core:page_list")).status_code == 403
    assert client.get(reverse("core:page_edit", args=["sobre"])).status_code == 403


def test_list_creates_missing_pages(client, editor_user):
    client.force_login(editor_user)

    html = client.get(reverse("core:page_list")).content.decode()

    assert StaticPage.objects.count() == 3
    assert html.index('data-page="sobre"') < html.index('data-page="privacidade"')
    assert 'href="/painel/paginas/colaborar/editar/"' in html
    assert "Fora do ar" in html  # privacidade nasce despublicada
    assert 'title="Páginas"' in html.split('aria-current="page"')[0].rsplit("<a ", 1)[1]


def test_edit_page_uses_editor_without_images(client, editor_user, about):
    client.force_login(editor_user)

    response = client.get(reverse("core:page_edit", args=["sobre"]))

    html = response.content.decode()
    assert response.status_code == 200
    assert "src/js/editor.js" in html
    data = json.loads(html.split('id="editor-data" type="application/json">')[1].split("<")[0])
    assert data["mediaUrl"] is None
    assert data["saveUrl"] == "/x/pages/sobre/body/"
    assert data["title"] == "Sobre o jornal"
    assert data["body"]["type"] == "doc"
    assert 'data-cmd="image"' not in html
    assert 'data-cmd="bold"' in html
    assert 'href="/painel/paginas/"' in html


# --- autosave ---


def test_save_renders_html_and_updates_public_page(client, editor_user, about):
    client.force_login(editor_user)
    document = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Quem"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": "Nova versão."}]},
        ],
    }

    response = put(
        client,
        about,
        {
            "title": "Sobre nós",
            "subtitle": "Outra linha fina",
            "body_json": document,
            "updated_at": about.updated_at.isoformat(),
        },
    )

    assert response.status_code == 200
    about.refresh_from_db()
    assert about.title == "Sobre nós"
    assert about.lead == "Outra linha fina"
    assert about.body_html == "<h2>Quem</h2><p>Nova versão.</p>"
    assert about.updated_by == editor_user
    assert response.json()["updated_at"] == about.updated_at.isoformat()
    html = client.get("/sobre/").content.decode()
    assert "<h2>Quem</h2><p>Nova versão.</p>" in html
    assert "Outra linha fina" in html


def test_save_strips_scripts_links_and_images(client, editor_user, about):
    client.force_login(editor_user)
    document = {
        "type": "doc",
        "content": [
            text_doc("<script>alert(1)</script>")["content"][0],
            {"type": "figure", "attrs": {"assetId": 1, "alt": "x"}},
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "clique",
                        "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}],
                    }
                ],
            },
            {"type": "codeBlock", "content": [{"type": "text", "text": "x"}]},
        ],
    }

    put(client, about, {"body_json": document})

    about.refresh_from_db()
    assert about.body_html == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p><p>clique</p>"
    assert all(node["type"] == "paragraph" for node in about.body_json["content"])


def test_empty_title_keeps_previous(client, editor_user, about):
    client.force_login(editor_user)

    assert put(client, about, {"title": "   "}).status_code == 200

    about.refresh_from_db()
    assert about.title == "Sobre o jornal"


def test_save_denied_to_staff_and_anonymous(client, staff_user, about):
    assert put(client, about, {"title": "X"}).status_code == 401
    client.force_login(staff_user)

    assert put(client, about, {"title": "X"}).status_code == 403
    about.refresh_from_db()
    assert about.title == "Sobre o jornal"


def test_conflict_when_other_person_saved(client, editor_user, about):
    other = UserFactory(editor=True)
    loaded = about.updated_at
    services.update_page(other, about, body_json=text_doc("Da outra pessoa"))
    client.force_login(editor_user)

    payload = {"body_json": text_doc("Minha"), "updated_at": loaded.isoformat()}
    response = put(client, about, payload)

    assert response.status_code == 409
    about.refresh_from_db()
    assert "Da outra pessoa" in about.body_html


def test_own_consecutive_saves_do_not_conflict(client, editor_user, about):
    client.force_login(editor_user)
    old = (about.updated_at - timedelta(minutes=1)).isoformat()
    put(client, about, {"body_json": text_doc("Um")})

    assert put(client, about, {"body_json": text_doc("Dois"), "updated_at": old}).status_code == 200


def test_invalid_json(client, editor_user, about):
    client.force_login(editor_user)

    response = client.put(
        reverse("core:page_save_body", args=["sobre"]), data="{", content_type="application/json"
    )

    assert response.status_code == 400


# --- publicar ---


def test_publish_and_unpublish(client, editor_user, about):
    client.force_login(editor_user)
    url = reverse("core:page_publish", args=["sobre"])

    response = client.post(url, {"publicada": "0"})

    assert response.url == reverse("core:page_list")
    assert client.get("/sobre/").status_code == 404
    client.post(url, {"publicada": "1"})
    assert client.get("/sobre/").status_code == 200
    about.refresh_from_db()
    assert about.updated_by == editor_user


def test_staff_cannot_publish(client, staff_user, about):
    client.force_login(staff_user)

    response = client.post(reverse("core:page_publish", args=["sobre"]), {"publicada": "0"})

    assert response.status_code == 403
    about.refresh_from_db()
    assert about.is_published
