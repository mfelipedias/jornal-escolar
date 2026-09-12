import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from apps.publications import presentation, services
from apps.publications.models import Article
from tests.factories import (
    ArticleFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def published(author):
    area = KnowledgeAreaFactory(name="Ciências da Natureza", color="verde")
    physics = DisciplineFactory(name="Física", area=area)
    article = ArticleFactory(
        ready=True,
        author=author,
        created_by=author,
        title="Feira de Ciências",
        subtitle="Projetos de energia solar",
        disciplines=[physics],
    )
    services.update_article(
        author, article, body_json=text_doc("Os alunos apresentaram <projetos>.")
    )
    services.add_student_credit(
        author, article, name="Rafael S.", class_group="2ª série B", consent_ok=True
    )
    services.add_guest_credit(author, article, name="Grêmio Estudantil", contribution_note="fotos")
    services.publish(author, article)
    article.refresh_from_db()
    return article


# --- apresentação ---


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([], ""),
        (["Ana"], "Ana"),
        (["Ana", "Rafael S."], "Ana e Rafael S."),
        (["A", "B", "C"], "A, B e C"),
    ],
)
def test_join_names(names, expected):
    assert presentation.join_names(names) == expected


def test_byline_and_credit_groups(published):
    article = Article.objects.get(pk=published.pk)

    assert presentation.byline(article) == "Carla Souza e Rafael S."
    groups = dict(presentation.credit_groups(article))
    assert [c.name for c in groups["Texto"]] == ["Carla Souza", "Rafael S."]
    assert groups["Texto"][1].detail == "Aluno, 2ª série B"
    assert groups["Com colaboração de"][0].detail == "fotos"


# --- página publicada ---


def test_published_page_for_anonymous(client, published):
    response = client.get(published.get_absolute_url())

    html = response.content.decode()
    assert response.status_code == 200
    assert "<title>Feira de Ciências · Jornal Escolar</title>" in html
    assert '<meta name="description"' in html
    assert "Projetos de energia solar" in html
    assert "Carla Souza e Rafael S." in html
    assert "Ciências da Natureza" in html
    assert "Os alunos apresentaram &lt;projetos&gt;." in html
    assert "Aluno, 2ª série B" in html
    assert 'rel="canonical"' in html
    assert "Pré-visualização" not in html
    assert ">Editar<" not in html
    assert html.count("<h1") == 1
    assert 'aria-labelledby="article-title"' in html


def test_author_sees_edit_link(client, published, author):
    client.force_login(author)

    assert (
        f'href="/painel/publicacoes/{published.pk}/editar/"'
        in client.get(published.get_absolute_url()).content.decode()
    )


def test_unknown_slug_is_404(client):
    response = client.get("/publicacoes/nao-existe/")

    assert response.status_code == 404
    assert "Página não encontrada" in response.content.decode()


def test_archived_is_410_for_public(client, published, author):
    services.archive(author, published)

    response = client.get(published.get_absolute_url())

    assert response.status_code == 410
    assert "Esta publicação foi retirada do ar" in response.content.decode()


def test_archived_is_preview_for_author(client, published, author):
    services.archive(author, published)
    client.force_login(author)

    response = client.get(published.get_absolute_url())

    assert response.status_code == 200
    assert "Pré-visualização" in response.content.decode()
    assert response["X-Robots-Tag"] == "noindex"


# --- pré-visualização de rascunho ---


def test_draft_preview_for_author(client, author):
    draft = ArticleFactory(author=author, created_by=author, title="Rascunho secreto")
    client.force_login(author)

    response = client.get(draft.get_absolute_url())

    assert draft.get_absolute_url() == reverse("publications:preview", args=[draft.pk])
    assert response.status_code == 200
    assert "Pré-visualização" in response.content.decode()
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("who", ["anon", "other"])
def test_draft_preview_hidden_from_others(client, author, who):
    draft = ArticleFactory(author=author, created_by=author)
    if who == "other":
        client.force_login(UserFactory())

    assert client.get(draft.get_absolute_url()).status_code == 404


def test_preview_of_published_redirects_to_slug(client, published, author):
    client.force_login(author)

    response = client.get(reverse("publications:preview", args=[published.pk]))

    assert response.status_code == 302
    assert response.url == published.get_absolute_url()


def test_editor_sees_preview(client, editor_user, author):
    draft = ArticleFactory(author=author, created_by=author)
    client.force_login(editor_user)

    assert client.get(draft.get_absolute_url()).status_code == 200


# --- blocos ---


def test_related_articles(client, published, author):
    physics = published.disciplines.first()
    other = ArticleFactory(
        ready=True,
        author=author,
        created_by=author,
        title="Robótica na escola",
        disciplines=[physics],
    )
    services.publish(author, other)
    unrelated = ArticleFactory(ready=True, author=author, created_by=author, title="Sem relação")
    services.publish(author, unrelated)

    html = client.get(published.get_absolute_url()).content.decode()

    assert "Leia também" in html
    assert "Robótica na escola" in html
    assert "Sem relação" not in html
    assert "border-area-verde" in html  # card com filete da área


def test_card_from_article(published):
    article = Article.objects.get(pk=published.pk)

    card = presentation.card(article)

    assert card.title == "Feira de Ciências"
    assert card.url == article.get_absolute_url()
    assert card.area.name == "Ciências da Natureza"
    assert card.byline == "Carla Souza e Rafael S."
    assert card.type_name == article.type.name
    assert card.published_at == article.published_at
    assert card.image is None


def test_related_cards_do_not_multiply_queries(
    client, published, author, django_assert_max_num_queries
):
    physics = published.disciplines.first()
    for n in range(3):
        other = ArticleFactory(
            ready=True, author=author, created_by=author, title=f"Outra {n}", disciplines=[physics]
        )
        services.publish(author, other)

    with django_assert_max_num_queries(20):
        client.get(published.get_absolute_url())


def test_sources_event_and_share(client, author):
    from datetime import timedelta

    from django.utils import timezone

    from tests.factories import ArticleTypeFactory

    event_type = ArticleTypeFactory(name="Evento", has_event_date=True)
    article = ArticleFactory(ready=True, author=author, created_by=author)
    services.set_metadata(
        author,
        article,
        type_id=event_type.pk,
        discipline_ids=[d.pk for d in article.disciplines.all()],
        topic_ids=[],
        event_at=timezone.now() + timedelta(days=3),
        event_location="Quadra coberta",
        sources=[
            {"title": "INEP", "url": "https://www.gov.br/inep", "publisher": "Governo Federal"}
        ],
    )
    services.publish(author, article)

    html = client.get(Article.objects.get(pk=article.pk).get_absolute_url()).content.decode()

    assert "Quadra coberta" in html
    assert "Fontes e referências" in html
    assert 'href="https://www.gov.br/inep"' in html
    assert "https://wa.me/?text=" in html


def test_page_query_count_is_bounded(client, published, django_assert_max_num_queries):
    with django_assert_max_num_queries(20):
        client.get(published.get_absolute_url())


def test_can_view_rules_used(published):
    assert Article.objects.get(pk=published.pk).status == Article.Status.PUBLISHED
    from apps.editorial.permissions import can_view

    assert can_view(AnonymousUser(), published)
