"""Página de tópico /topicos/<slug>/ (docs/12, E43)."""

import pytest
from django.urls import reverse

from apps.publications import services
from apps.publications.models import Article
from apps.taxonomy.models import Topic
from tests.factories import ArticleFactory, ArticleTypeFactory, DisciplineFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def topic():
    return Topic.objects.create(name="Inteligência Artificial", slug="inteligencia-artificial")


def publish(author, title, topics=(), **fields):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title, **fields)
    article.topics.set(topics)
    services.publish(author, article)
    return article


def test_topic_page_lists_only_published_with_topic(client, author, topic):
    physics = DisciplineFactory(name="Física")
    topic.disciplines.add(DisciplineFactory(name="Matemática"))
    publish(author, "Robôs que aprendem", [topic], disciplines=[physics])
    publish(author, "Outro assunto")
    draft = ArticleFactory(ready=True, author=author, created_by=author, title="Rascunho IA")
    draft.topics.set([topic])

    response = client.get(topic.get_absolute_url())

    assert response.status_code == 200
    html = response.content.decode()
    assert "Inteligência Artificial" in html
    assert "Robôs que aprendem" in html
    assert "Outro assunto" not in html
    assert "Rascunho IA" not in html
    # Disciplinas relacionadas: sugeridas no tópico e usadas nas publicações no ar.
    assert 'aria-label="Disciplinas relacionadas"' in html
    assert "Matemática" in html
    assert "Física" in html
    assert response.context["page_obj"].paginator.count == 1
    assert response.context["seo"].canonical.endswith("/topicos/inteligencia-artificial/")


@pytest.mark.parametrize("slug", ["nao-existe", "inativo"])
def test_unknown_or_inactive_topic_is_404(client, slug):
    Topic.objects.create(name="Inativo", slug="inativo", is_active=False)
    assert client.get(reverse("taxonomy:topic", args=[slug])).status_code == 404


def test_empty_topic_page(client, topic):
    html = client.get(topic.get_absolute_url()).content.decode()
    assert "Ainda não há publicações sobre Inteligência Artificial" in html


def test_topic_filters_and_load_more(client, author, topic):
    news = ArticleTypeFactory(name="Notícia", slug="noticia")
    for n in range(13):
        publish(author, f"IA {n}", [topic], **({"type": news} if n == 0 else {}))

    first = client.get(topic.get_absolute_url())
    assert len(first.context["cards"]) == 12
    assert "Tópico: Inteligência Artificial" in first.content.decode()  # chip fixo

    more = client.get(f"{topic.get_absolute_url()}?pagina=2", headers={"HX-Request": "true"})
    assert more.status_code == 200
    assert [c.title for c in more.context["cards"]] == ["IA 0"]

    filtered = client.get(f"{topic.get_absolute_url()}?tipo=noticia")
    assert [c.title for c in filtered.context["cards"]] == ["IA 0"]


def test_topic_page_cache_follows_topic_changes(client, author, topic):
    article = publish(author, "Robôs que aprendem")
    assert "Robôs que aprendem" not in client.get(topic.get_absolute_url()).content.decode()

    Article.objects.get(pk=article.pk).topics.add(topic)

    assert "Robôs que aprendem" in client.get(topic.get_absolute_url()).content.decode()


def test_topic_in_sitemap_only_with_published_article(client, author, topic):
    empty = Topic.objects.create(name="Sem nada", slug="sem-nada")
    publish(author, "Robôs que aprendem", [topic])

    xml = client.get("/sitemap.xml").content.decode()

    assert "/topicos/inteligencia-artificial/" in xml
    assert f"/topicos/{empty.slug}/" not in xml


def test_search_topic_chip_links_to_topic_page(client, topic):
    html = client.get(reverse("search:results"), {"q": "inteligencia"}).content.decode()
    assert f'href="{topic.get_absolute_url()}"' in html
