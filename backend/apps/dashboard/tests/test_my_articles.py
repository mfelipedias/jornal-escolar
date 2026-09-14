"""Minhas publicações (E24, docs/15): filtro por estado, papel e ações por linha."""

import pytest
from django.urls import reverse

from apps.publications import services
from apps.publications.models import Article, ArticleContributor
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/painel/publicacoes/"


@pytest.fixture
def ana():
    return UserFactory(full_name="Ana Autora")


@pytest.fixture
def articles(ana):
    draft = ArticleFactory(author=ana, created_by=ana, title="Meu rascunho")
    published = ArticleFactory(ready=True, author=ana, created_by=ana, title="No ar")
    services.publish(ana, published)
    archived = ArticleFactory(ready=True, author=ana, created_by=ana, title="Guardada")
    services.archive(ana, archived)
    other = UserFactory()
    ArticleFactory(author=other, created_by=other, title="Alheia")
    return {"draft": draft, "published": published, "archived": archived}


def test_url(client):
    assert reverse("dashboard:my_articles") == URL
    assert client.get(URL).status_code == 302


def test_lists_only_my_articles_with_counts(client, ana, articles):
    client.force_login(ana)
    response = client.get(URL)
    html = response.content.decode()

    assert [row.article.title for row in response.context["rows"]] == [
        "Guardada",
        "No ar",
        "Meu rascunho",
    ]
    assert "Alheia" not in html
    counts = {chip["key"]: chip["count"] for chip in response.context["chips"]}
    assert counts == {"": 3, "rascunhos": 1, "publicados": 1, "arquivados": 1}
    # Estados e aba da Fase 2 ainda não aparecem.
    assert "Em revisão" not in html
    assert "Revisando" not in html


@pytest.mark.parametrize(
    ("estado", "title"),
    [("rascunhos", "Meu rascunho"), ("publicados", "No ar"), ("arquivados", "Guardada")],
)
def test_status_filter(client, ana, articles, estado, title):
    client.force_login(ana)
    response = client.get(URL, {"estado": estado})

    assert [row.article.title for row in response.context["rows"]] == [title]


def test_unknown_filter_shows_all(client, ana, articles):
    client.force_login(ana)
    response = client.get(URL, {"estado": "qualquer"})
    assert len(response.context["rows"]) == 3


def test_row_actions(client, ana, articles):
    client.force_login(ana)
    response = client.get(URL)
    rows = {row.article.title: row for row in response.context["rows"]}

    draft, live, old = rows["Meu rascunho"], rows["No ar"], rows["Guardada"]
    assert draft.my_roles == "Autor"
    actions = ("can_edit", "can_duplicate", "can_archive", "can_restore")
    assert [getattr(draft, name) for name in actions] == [True, True, True, False]
    assert [getattr(live, name) for name in actions] == [True, True, True, False]
    assert [getattr(old, name) for name in actions] == [True, True, False, True]

    html = response.content.decode()
    assert articles["published"].get_absolute_url() in html
    assert reverse("publications:duplicate", args=[articles["draft"].pk]) in html


def test_collaborator_row_has_no_edit_actions(client, ana):
    other = UserFactory()
    article = ArticleFactory(ready=True, author=other, created_by=other, title="Colaborei")
    services.publish(other, article)
    ArticleContributor.objects.create(
        article=article, user=ana, display_name=ana.public_name, role="collaborator"
    )
    client.force_login(ana)
    [row] = client.get(URL).context["rows"]

    assert row.my_roles == "Colaboração"
    assert not row.can_edit
    assert not row.has_more


def test_editor_does_not_archive_others_text_from_list(client, editor_user):
    """Arquivar texto alheio pede motivo; isso fica no editor."""
    other = UserFactory()
    article = ArticleFactory(ready=True, author=other, created_by=other)
    services.publish(other, article)
    ArticleContributor.objects.create(
        article=article, user=editor_user, display_name="Edição", role="editor"
    )
    client.force_login(editor_user)
    [row] = client.get(URL).context["rows"]

    assert row.can_edit
    assert not row.can_archive


def test_empty_state(client, ana):
    client.force_login(ana)
    html = client.get(URL).content.decode()
    assert "Você ainda não escreveu nada" in html
    assert reverse("publications:create") in html


def test_archive_from_list_returns_to_list(client, ana, articles):
    client.force_login(ana)
    back = f"{URL}?estado=publicados"
    response = client.post(
        reverse("publications:transition", args=[articles["published"].pk, "archive"]),
        {"next": back},
    )

    assert response.status_code == 302
    assert response.url == back
    articles["published"].refresh_from_db()
    assert articles["published"].status == Article.Status.ARCHIVED


def test_transition_ignores_external_next(client, ana, articles):
    client.force_login(ana)
    response = client.post(
        reverse("publications:transition", args=[articles["archived"].pk, "restore"]),
        {"next": "https://exemplo.com/"},
    )
    assert response.url == reverse("publications:edit", args=[articles["archived"].pk])


def test_duplicate_as_draft(client, ana, articles):
    source = articles["published"]
    student = ArticleContributor.objects.create(
        article=source, display_name="Lia M.", is_student=True, consent_ok=True, order=2
    )
    client.force_login(ana)
    response = client.post(reverse("publications:duplicate", args=[source.pk]))

    copy = Article.objects.get(title="No ar (cópia)")
    assert response.url == reverse("publications:edit", args=[copy.pk])
    assert copy.status == Article.Status.DRAFT
    assert copy.slug is None
    assert copy.body_text == "Texto da publicação."
    assert copy.type_id == source.type_id
    assert list(copy.disciplines.all()) == list(source.disciplines.all())
    credits = list(copy.contributors.values_list("display_name", "role", "is_student"))
    assert credits == [(ana.public_name, "author", False), (student.display_name, "author", True)]
    source.refresh_from_db()
    assert source.status == Article.Status.PUBLISHED


def test_duplicate_requires_edit_permission(client, ana):
    other = UserFactory()
    article = ArticleFactory(author=other, created_by=other)
    client.force_login(ana)
    response = client.post(reverse("publications:duplicate", args=[article.pk]))

    assert response.status_code == 403
    assert Article.objects.count() == 1
