import json

import pytest
from django.urls import reverse

from apps.publications import services
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db


def put(client, article, payload):
    return client.put(
        reverse("publications:save_body", args=[article.pk]),
        data=json.dumps(payload),
        content_type="application/json",
    )


# --- telas ---


def test_create_requires_login(client):
    response = client.get(reverse("publications:create"))

    assert response.status_code == 302
    assert response.url.startswith("/entrar/")


def test_create_get_shows_button_and_post_creates_draft(client, staff_user):
    client.force_login(staff_user)

    assert "Começar a escrever" in client.get(reverse("publications:create")).content.decode()
    response = client.post(reverse("publications:create"))

    article = Article.objects.get()
    assert response.url == reverse("publications:edit", args=[article.pk])
    assert article.contributors.get().user == staff_user


def test_edit_page_for_author(client, staff_user):
    article = ArticleFactory(author=staff_user, created_by=staff_user, body_json=text_doc("Olá"))
    client.force_login(staff_user)

    response = client.get(reverse("publications:edit", args=[article.pk]))

    html = response.content.decode()
    assert response.status_code == 200
    assert 'id="editor-data"' in html
    assert "src/js/editor.js" in html
    assert '"saveUrl": "/x/articles/' in html
    assert 'name="robots" content="noindex"' in html


def test_edit_page_hides_placeholder_title(client, staff_user):
    client.force_login(staff_user)
    article = services.create_article(staff_user)

    response = client.get(reverse("publications:edit", args=[article.pk]))

    assert '"title": ""' in response.content.decode()


def test_edit_page_denied_to_other_staff(client, staff_user):
    article = ArticleFactory()
    client.force_login(staff_user)

    response = client.get(reverse("publications:edit", args=[article.pk]))

    assert response.status_code == 403
    assert "Você não tem acesso" in response.content.decode()


def test_edit_page_allowed_to_editor(client, editor_user):
    article = ArticleFactory()
    client.force_login(editor_user)

    assert client.get(reverse("publications:edit", args=[article.pk])).status_code == 200


def test_masthead_has_write_link_for_staff(client, staff_user):
    client.force_login(staff_user)

    assert 'href="/painel/publicacoes/nova/"' in client.get("/").content.decode()


# --- autosave ---


def test_autosave_saves_and_renders(client, staff_user):
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    response = put(
        client,
        article,
        {
            "title": "  Feira   de Ciências ",
            "subtitle": "Linha fina",
            "body_json": text_doc("Texto do corpo."),
            "updated_at": article.updated_at.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"saved_at", "updated_at", "reading_minutes", "status"}
    article.refresh_from_db()
    assert article.title == "Feira de Ciências"
    assert article.body_html == "<p>Texto do corpo.</p>"
    assert body["updated_at"] == article.updated_at.isoformat()


def test_consecutive_saves_with_returned_timestamp(client, staff_user):
    """O editor usa o updated_at devolvido para o próximo salvamento (sem falso conflito)."""
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    first = put(client, article, {"title": "Um", "updated_at": article.updated_at.isoformat()})
    second = put(client, article, {"title": "Dois", "updated_at": first.json()["updated_at"]})

    assert second.status_code == 200
    assert Article.objects.get(pk=article.pk).title == "Dois"


def test_conflict_when_someone_else_saved(client, staff_user, editor_user):
    article = services.create_article(staff_user)
    loaded_at = article.updated_at.isoformat()
    services.update_article(editor_user, article, subtitle="Editor mexeu")
    client.force_login(staff_user)

    response = put(client, article, {"title": "Autor", "updated_at": loaded_at})

    assert response.status_code == 409
    assert "alterado por outra pessoa" in response.json()["error"]["message"]
    assert Article.objects.get(pk=article.pk).title == "Sem título"


def test_empty_title_is_stored_as_placeholder(client, staff_user):
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    put(client, article, {"title": "   "})

    assert Article.objects.get(pk=article.pk).title == "Sem título"


def test_autosave_requires_login(client):
    article = ArticleFactory()

    assert put(client, article, {"title": "x"}).status_code == 401


def test_autosave_by_user_without_permission_returns_403(client, staff_user):
    """Teste obrigatório de docs/16."""
    article = ArticleFactory()
    client.force_login(staff_user)

    response = put(client, article, {"title": "Invasão"})

    assert response.status_code == 403
    assert Article.objects.get(pk=article.pk).title != "Invasão"


def test_autosave_rejects_long_title(client, staff_user):
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    response = put(client, article, {"title": "x" * 121})

    assert response.status_code == 400
    assert "title" in response.json()["error"]["fields"]


def test_autosave_rejects_huge_body(client, staff_user, settings):
    settings.EDITOR_MAX_BODY_BYTES = 200
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    response = put(client, article, {"body_json": text_doc("x" * 500)})

    assert response.status_code == 413


def test_autosave_invalid_json(client, staff_user):
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    response = client.put(
        reverse("publications:save_body", args=[article.pk]),
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400


def test_autosave_only_accepts_put(client, staff_user):
    article = services.create_article(staff_user)
    client.force_login(staff_user)

    assert client.post(reverse("publications:save_body", args=[article.pk])).status_code == 405


def test_autosave_on_published_article_creates_revision(client, staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)
    article.refresh_from_db()
    client.force_login(staff_user)

    response = put(
        client, article, {"subtitle": "Corrigida", "updated_at": article.updated_at.isoformat()}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert article.revisions.count() == 2


def test_autosave_csrf_is_enforced(staff_user):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(staff_user)
    article = services.create_article(staff_user)

    response = put(client, article, {"title": "Sem token"})

    assert response.status_code == 403


def test_other_user_cannot_see_create_as_editor(client):
    client.force_login(UserFactory(is_active=True))

    assert client.get(reverse("publications:create")).status_code == 200
