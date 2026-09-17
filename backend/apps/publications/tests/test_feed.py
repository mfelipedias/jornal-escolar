"""Feed RSS 2.0 em /feed/ (docs/11, E43)."""

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import pytest
from django.urls import reverse

from apps.core.site_settings import get_setting
from apps.publications import feeds, services
from apps.publications.models import Article
from tests.factories import ArticleFactory, DisciplineFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db

DC = "{http://purl.org/dc/elements/1.1/}"
ATOM = "{http://www.w3.org/2005/Atom}"


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


def publish(author, **fields):
    article = ArticleFactory(ready=True, author=author, created_by=author, **fields)
    services.publish(author, article)
    return Article.objects.get(pk=article.pk)


def get_channel(client):
    response = client.get(reverse("publications:feed"))
    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)  # falha se o XML não for bem formado
    assert root.tag == "rss"
    assert root.get("version") == "2.0"
    return response, root.find("channel")


def test_feed_is_valid_rss_with_required_fields(client, author, settings):
    settings.SITE_URL = "https://jornal.exemplo"
    physics = DisciplineFactory(name="Física")
    article = publish(
        author, title="Feira de Ciências", subtitle="Energia solar", disciplines=[physics]
    )
    services.add_student_credit(
        author, article, name="Rafael S.", class_group="2ª série B", consent_ok=True
    )

    response, channel = get_channel(client)

    assert response["Content-Type"] == "application/rss+xml; charset=utf-8"
    # Obrigatórios do canal no RSS 2.0: title, link e description.
    assert channel.findtext("title") == get_setting("site.name")
    assert channel.findtext("link") == "https://jornal.exemplo/"
    assert channel.findtext("description")
    assert channel.findtext("language") == "pt-br"
    assert channel.find(f"{ATOM}link").get("href") == "https://jornal.exemplo/feed/"
    (item,) = channel.findall("item")
    url = f"https://jornal.exemplo{article.get_absolute_url()}"
    assert item.findtext("title") == "Feira de Ciências"
    assert item.findtext("link") == url
    assert item.findtext("guid") == url
    assert item.findtext("description") == "Energia solar"
    assert parsedate_to_datetime(item.findtext("pubDate")) == article.published_at.replace(
        microsecond=0
    )
    assert item.findtext(f"{DC}creator") == "Carla Souza e Rafael S."
    assert {c.text for c in item.findall("category")} == {"Física", article.type.name}
    assert "example.com" not in response.content.decode()


def test_only_published_most_recent_first(client, author):
    first = publish(author, title="Primeira")
    second = publish(author, title="Segunda")
    ArticleFactory(ready=True, author=author, created_by=author, title="Rascunho")
    archived = publish(author, title="Arquivada")
    Article.objects.filter(pk=archived.pk).update(status=Article.Status.ARCHIVED)

    _, channel = get_channel(client)

    assert [i.findtext("title") for i in channel.findall("item")] == [second.title, first.title]


def test_description_falls_back_to_body_excerpt(client, author):
    article = publish(author, title="Sem linha fina")
    services.update_article(author, article, body_json=text_doc("Texto do corpo <b> & mais."))
    Article.objects.filter(pk=article.pk).update(subtitle="")

    _, channel = get_channel(client)

    assert channel.find("item").findtext("description") == "Texto do corpo <b> & mais."


def test_limit_and_cache_invalidated_by_publishing(client, author, monkeypatch):
    monkeypatch.setattr(feeds, "FEED_ITEMS", 2)
    for n in range(3):
        publish(author, title=f"Publicação {n}")
    _, channel = get_channel(client)
    assert len(channel.findall("item")) == 2

    publish(author, title="Nova")

    _, channel = get_channel(client)
    assert channel.find("item").findtext("title") == "Nova"


def test_empty_feed_is_still_valid(client):
    _, channel = get_channel(client)
    assert channel.findall("item") == []


def test_pages_advertise_the_feed(client):
    html = client.get("/").content.decode()
    assert 'type="application/rss+xml"' in html
    assert f'href="{reverse("publications:feed")}"' in html
