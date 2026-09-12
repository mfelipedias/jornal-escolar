"""Página inicial com conteúdo (docs/10, E20)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import TeacherProfile
from apps.publications import home, services
from apps.publications.models import Article
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


def publish(author, title, *, days_ago=0, discipline=None, **fields):
    extra = {"disciplines": [discipline]} if discipline else {}
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title, **extra)
    services.publish(author, article)
    Article.objects.filter(pk=article.pk).update(
        published_at=timezone.now() - timedelta(days=days_ago), **fields
    )
    return Article.objects.get(pk=article.pk)


def test_empty_home_shows_single_empty_state(client):
    html = client.get("/").content.decode()

    assert "O jornal está sendo preparado" in html
    assert "Últimas publicações" not in html


def test_one_publication_becomes_hero(client, author):
    publish(author, "Feira de Ciências")

    html = client.get("/").content.decode()

    assert "Feira de Ciências" in html
    assert "O jornal está sendo preparado" not in html
    assert html.count("<h1") == 1
    assert "tudo o que foi publicado está nos destaques" in html
    assert "Carla Souza" in html


def test_featured_first_then_most_recent(author):
    old_featured = publish(author, "Destaque antigo", days_ago=30, is_featured=True)
    publish(author, "Recente 1", days_ago=1)
    publish(author, "Recente 2", days_ago=2)
    publish(author, "Recente 3", days_ago=3)

    blocks = home.build_blocks()

    assert [c.title for c in blocks.featured] == ["Destaque antigo", "Recente 1", "Recente 2"]
    assert blocks.featured_ids[0] == old_featured.pk


def test_featured_order_is_respected(author):
    publish(author, "Segundo", is_featured=True, featured_order=2)
    publish(author, "Primeiro", days_ago=5, is_featured=True, featured_order=1)

    assert [c.title for c in home.build_blocks().featured][:2] == ["Primeiro", "Segundo"]


def test_latest_excludes_featured_and_loads_more(client, author):
    for n in range(10):
        publish(author, f"Texto {n:02d}", days_ago=n)

    html = client.get("/").content.decode()
    # 3 no destaque (00-02), 6 nas últimas (03-08), 1 na página seguinte (09)
    assert 'id="latest-list"' in html
    assert "Texto 08" in html
    assert "Texto 09" not in html.split('id="latest-list"')[1].split("data-load-more")[0]
    assert "Carregar mais" in html

    more = client.get("/?pagina=2", HTTP_HX_REQUEST="true").content.decode()
    assert 'hx-swap-oob="beforeend:#latest-list"' in more
    assert "Texto 09" in more
    assert "Texto 03" not in more
    assert "<html" not in more


def test_agenda_upcoming_events(client, author):
    event_type = ArticleTypeFactory(name="Evento", has_event_date=True)
    now = timezone.now()
    publish(author, "Sarau", type=event_type, event_at=now + timedelta(days=5))
    publish(author, "Feira", type=event_type, event_at=now + timedelta(days=2))
    publish(author, "Formatura antiga", type=event_type, event_at=now - timedelta(days=40))

    blocks = home.build_blocks()

    assert [e.title for e in blocks.events] == ["Feira", "Sarau"]
    assert not blocks.events_past
    assert "Agenda" in client.get("/").content.decode()


def test_agenda_shows_last_past_event_when_none_upcoming(author):
    event_type = ArticleTypeFactory(name="Evento", has_event_date=True)
    now = timezone.now()
    publish(author, "Formatura", type=event_type, event_at=now - timedelta(days=3))
    publish(author, "Gincana", type=event_type, event_at=now - timedelta(days=30))

    blocks = home.build_blocks()

    assert [e.title for e in blocks.events] == ["Formatura"]
    assert blocks.events_past


def test_no_agenda_without_events(client, author):
    publish(author, "Sem evento")

    assert home.build_blocks().events == []
    assert 'id="agenda-title"' not in client.get("/").content.decode()


def test_writers_public_profiles_most_recent_first(author):
    other = UserFactory(full_name="Bruno Lima")
    hidden = UserFactory(full_name="Oculto")
    TeacherProfile.objects.filter(user=hidden).update(is_public=False)
    publish(author, "Antiga", days_ago=10)
    publish(other, "Nova", days_ago=1)

    names = [w.name for w in home.build_blocks().writers]

    assert names[:2] == ["Bruno Lima", "Carla Souza"]
    assert "Oculto" not in names


def test_area_strips_need_six_publications(author):
    area = KnowledgeAreaFactory(name="Ciências da Natureza", color="verde")
    physics = DisciplineFactory(name="Física", area=area)
    for n in range(5):
        publish(author, f"Física {n}", days_ago=n, discipline=physics)

    assert home.build_blocks().strips == []

    publish(author, "Física 5", days_ago=5, discipline=physics)
    strips = home.build_blocks().strips

    assert len(strips) == 1
    assert strips[0].area.name == "Ciências da Natureza"
    # sem as 3 do destaque, as 3 seguintes
    assert [c.title for c in strips[0].cards] == ["Física 3", "Física 4", "Física 5"]


def test_area_strips_follow_area_order_and_limit(client, author):
    areas = [KnowledgeAreaFactory(name=f"Área {n}", order=10 - n) for n in range(7)]
    for n, area in enumerate(areas):
        discipline = DisciplineFactory(area=area)
        publish(author, f"Destaque {n}", days_ago=n, discipline=discipline)
        publish(author, f"Extra {n}", days_ago=n + 10, discipline=discipline)

    strips = home.build_blocks().strips

    assert len(strips) == home.STRIP_LIMIT
    assert [s.area.name for s in strips] == ["Área 6", "Área 5", "Área 4", "Área 3", "Área 2"]
    html = client.get("/").content.decode()
    assert 'aria-labelledby="area-' in html


def test_publishing_refreshes_cached_home(client, author):
    publish(author, "Primeira")
    assert "Primeira" in client.get("/").content.decode()

    article = ArticleFactory(ready=True, author=author, created_by=author, title="Chegou agora")
    services.publish(author, article)

    assert "Chegou agora" in client.get("/").content.decode()


def test_archiving_removes_from_cached_home(client, author):
    article = publish(author, "Vai sair do ar")
    assert "Vai sair do ar" in client.get("/").content.decode()

    services.archive(author, article)

    assert "Vai sair do ar" not in client.get("/").content.decode()


def test_home_query_count_is_bounded(client, author, django_assert_max_num_queries):
    area = KnowledgeAreaFactory(name="Linguagens", color="coral")
    discipline = DisciplineFactory(area=area)
    for n in range(12):
        publish(author, f"Texto {n}", days_ago=n, discipline=discipline)

    with django_assert_max_num_queries(25):
        client.get("/")
    with django_assert_max_num_queries(12):  # blocos em cache
        client.get("/")
