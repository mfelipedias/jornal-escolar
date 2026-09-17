"""Leia também com pontuação por tópicos e disciplinas em comum (docs/11, E43)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.publications import selectors, services
from apps.publications.models import Article
from apps.taxonomy.models import Topic
from tests.factories import ArticleFactory, DisciplineFactory, KnowledgeAreaFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def taxonomy():
    natureza = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza")
    humanas = KnowledgeAreaFactory(name="Ciências Humanas", slug="humanas", color="ambar")
    return {
        "fisica": DisciplineFactory(name="Física", slug="fisica", area=natureza),
        "quimica": DisciplineFactory(name="Química", slug="quimica", area=natureza),
        "historia": DisciplineFactory(name="História", slug="historia", area=humanas),
        "energia": Topic.objects.create(name="Energia"),
        "clima": Topic.objects.create(name="Clima"),
    }


def publish(author, title, disciplines, topics=(), days_ago=0):
    article = ArticleFactory(
        ready=True, author=author, created_by=author, title=title, disciplines=disciplines
    )
    article.topics.set(topics)
    services.publish(author, article)
    Article.objects.filter(pk=article.pk).update(
        published_at=timezone.now() - timedelta(days=days_ago)
    )
    return Article.objects.get(pk=article.pk)


def titles(article):
    return [a.title for a in selectors.related_articles(article)]


def test_topics_weigh_more_than_disciplines(author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["fisica"]], [t["energia"]], days_ago=10)
    publish(author, "Só disciplina, recente", [t["fisica"]], days_ago=1)
    publish(author, "Só tópico, antiga", [t["historia"]], [t["energia"]], days_ago=30)
    publish(author, "Tópico e disciplina", [t["fisica"]], [t["energia"]], days_ago=20)

    assert titles(current) == [
        "Tópico e disciplina",
        "Só tópico, antiga",
        "Só disciplina, recente",
    ]


def test_more_topics_in_common_first_and_ties_go_to_most_recent(author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["historia"]], [t["energia"], t["clima"]])
    publish(author, "Um tópico, antiga", [t["quimica"]], [t["clima"]], days_ago=9)
    publish(author, "Um tópico, recente", [t["quimica"]], [t["energia"]], days_ago=2)
    publish(author, "Dois tópicos", [t["quimica"]], [t["energia"], t["clima"]], days_ago=40)

    assert titles(current) == ["Dois tópicos", "Um tópico, recente", "Um tópico, antiga"]


def test_excludes_itself_and_unpublished(author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["fisica"]], [t["energia"]])
    draft = ArticleFactory(ready=True, author=author, created_by=author, title="Rascunho")
    draft.disciplines.set([t["fisica"]])
    draft.topics.set([t["energia"]])
    archived = publish(author, "Arquivada", [t["fisica"]], [t["energia"]])
    Article.objects.filter(pk=archived.pk).update(status=Article.Status.ARCHIVED)

    assert titles(current) == []


def test_completes_with_same_area_but_not_other_areas(author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["fisica"]], days_ago=5)
    publish(author, "Mesma disciplina", [t["fisica"]], days_ago=4)
    publish(author, "Mesma área, antiga", [t["quimica"]], days_ago=30)
    publish(author, "Mesma área, recente", [t["quimica"]], days_ago=2)
    publish(author, "Outra área", [t["historia"]], days_ago=1)

    assert titles(current) == ["Mesma disciplina", "Mesma área, recente", "Mesma área, antiga"]


def test_limit_and_no_repeats(author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["fisica"], t["quimica"]], [t["energia"]])
    for n in range(5):
        publish(author, f"Outra {n}", [t["fisica"], t["quimica"]], [t["energia"]], days_ago=n + 1)

    assert titles(current) == ["Outra 0", "Outra 1", "Outra 2"]


def test_without_disciplines_or_topics_is_empty(author, taxonomy):
    current = publish(author, "Atual", [taxonomy["fisica"]])
    current.disciplines.clear()  # publicar exige disciplina; aqui é o caso-limite do selector
    publish(author, "Qualquer", [taxonomy["fisica"]])

    assert titles(current) == []


def test_topic_tags_on_page_link_to_topic_page(client, author, taxonomy):
    t = taxonomy
    inactive = Topic.objects.create(name="Tópico sugerido", is_active=False)
    current = publish(author, "Atual", [t["fisica"]], [t["energia"], inactive])

    html = client.get(current.get_absolute_url()).content.decode()

    assert 'aria-label="Tópicos"' in html
    assert f'href="{t["energia"].get_absolute_url()}"' in html
    assert "Tópico sugerido" not in html


def test_related_on_page_updates_after_publishing(client, author, taxonomy):
    t = taxonomy
    current = publish(author, "Atual", [t["fisica"]], [t["energia"]])
    assert "Leia também" not in client.get(current.get_absolute_url()).content.decode()

    publish(author, "Nova sobre energia", [t["historia"]], [t["energia"]])

    html = client.get(current.get_absolute_url()).content.decode()
    assert "Leia também" in html
    assert "Nova sobre energia" in html
