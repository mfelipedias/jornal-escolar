"""Filtros completos das listas: professor, período, ordem, HTMX e cache (docs/12, docs/19; E37)."""

from datetime import date, timedelta

import pytest
from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import TeacherProfile
from apps.publications import listing, services
from apps.publications.models import Article, ArticleContributor
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def taxonomy():
    natureza = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza", color="verde")
    humanas = KnowledgeAreaFactory(name="Ciências Humanas", slug="humanas", color="ambar")
    return {
        "natureza": natureza,
        "fisica": DisciplineFactory(name="Física", slug="fisica", area=natureza),
        "historia": DisciplineFactory(name="História", slug="historia", area=humanas),
        "noticia": ArticleTypeFactory(name="Notícia", slug="noticia"),
        "entrevista": ArticleTypeFactory(name="Entrevista", slug="entrevista"),
    }


@pytest.fixture
def carla():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def bruno():
    return UserFactory(full_name="Bruno Lima")


def publish(author, title, discipline, article_type, *, days_ago=0, body=None):
    article = ArticleFactory(
        ready=True, author=author, created_by=author, title=title, disciplines=[discipline]
    )
    Article.objects.filter(pk=article.pk).update(type=article_type)
    article.refresh_from_db()
    if body:
        services.update_article(author, article, body_json=text_doc(body))
    services.publish(author, article)
    Article.objects.filter(pk=article.pk).update(
        published_at=timezone.now() - timedelta(days=days_ago)
    )
    return Article.objects.get(pk=article.pk)


@pytest.fixture
def articles(carla, bruno, taxonomy):
    t = taxonomy
    return {
        "pendulo": publish(carla, "Pêndulo na sala", t["fisica"], t["noticia"], days_ago=1),
        "feira": publish(bruno, "Feira de ciências", t["fisica"], t["entrevista"], days_ago=10),
        "bairro": publish(carla, "Memórias do bairro", t["historia"], t["noticia"], days_ago=60),
        "antiga": publish(bruno, "Horta de 2020", t["historia"], t["entrevista"], days_ago=400),
    }


def slug_of(user) -> str:
    return TeacherProfile.objects.get(user=user).slug


def titles(html: str, articles: dict) -> set[str]:
    return {a.title for a in articles.values() if a.title in html}


def region(html: str) -> str:
    """Só a região da lista (o que o HTMX troca), sem cabeçalho nem masthead."""
    start = html.index('id="listing-region"')
    return html[start : html.index("</main>", start)]


# --- professor ---


def test_professor_filter_uses_visible_credits(client, articles, carla, bruno):
    html = client.get(f"/publicacoes/?professor={slug_of(carla)}").content.decode()

    assert titles(html, articles) == {"Pêndulo na sala", "Memórias do bairro"}
    assert "Remover filtro Por: Carla Souza" in html


def test_professor_filter_counts_collaboration_but_respects_hidden_review(
    client, articles, carla, bruno
):
    ArticleContributor.objects.create(
        article=articles["feira"], user=carla, display_name="Carla Souza", role="collaborator"
    )
    ArticleContributor.objects.create(
        article=articles["antiga"], user=carla, display_name="Carla Souza", role="reviewer"
    )
    TeacherProfile.objects.filter(user=carla).update(show_reviewer_credit=False)

    html = client.get(f"/publicacoes/?professor={slug_of(carla)}").content.decode()

    assert "Feira de ciências" in html
    assert "Horta de 2020" not in html


def test_private_or_unknown_professor_is_ignored(client, articles, carla):
    TeacherProfile.objects.filter(user=carla).update(is_public=False)

    for slug in (slug_of(carla), "nao-existe"):
        filters = listing.parse(QueryDict(f"professor={slug}"))
        assert filters.professor is None
        assert "4 publicações" in client.get(f"/publicacoes/?professor={slug}").content.decode()


def test_professor_options_are_public_people_with_published_credits(articles, carla, bruno):
    UserFactory(full_name="Sem Publicação")
    TeacherProfile.objects.filter(user=bruno).update(is_public=False)

    options = listing.options(listing.parse(QueryDict()))

    assert [p.user.full_name for p in options.professors] == ["Carla Souza"]


# --- período ---


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("periodo=30-dias", {"Pêndulo na sala", "Feira de ciências"}),
        (
            "de=2000-01-01&ate=2100-01-01",
            {"Pêndulo na sala", "Feira de ciências", "Memórias do bairro", "Horta de 2020"},
        ),
        ("ate=2000-01-01", set()),
    ],
)
def test_period_filters(client, articles, query, expected):
    html = client.get(f"/publicacoes/?{query}").content.decode()

    assert titles(html, articles) == expected


def test_date_interval_is_inclusive_and_wins_over_period(client, articles):
    day = timezone.localdate(articles["feira"].published_at).isoformat()

    html = client.get(f"/publicacoes/?periodo=30-dias&de={day}&ate={day}").content.decode()

    assert titles(html, articles) == {"Feira de ciências"}
    label = f"De {day[8:10]}/{day[5:7]}/{day[:4]} a {day[8:10]}/{day[5:7]}/{day[:4]}"
    assert f"Remover filtro {label}" in html


def test_parse_period_and_dates():
    swapped = listing.parse(QueryDict("de=2026-05-10&ate=2026-03-01"))
    assert (swapped.date_from, swapped.date_to) == (date(2026, 3, 1), date(2026, 5, 10))

    invalid = listing.parse(QueryDict("de=ontem&ate=2026-13-40&periodo=sempre"))
    assert (invalid.date_from, invalid.date_to, invalid.period) == (None, None, "")
    assert not invalid.has_user_filters

    assert listing.period_range("semestre", date(2026, 9, 14)) == (date(2026, 7, 1), None)
    assert listing.period_range("semestre", date(2026, 3, 2)) == (date(2026, 1, 1), None)
    assert listing.period_range("ano", date(2026, 9, 14)) == (date(2026, 1, 1), None)
    assert listing.period_range("30-dias", date(2026, 9, 14)) == (date(2026, 8, 15), None)


def test_period_chip_removes_period_and_dates(taxonomy):
    query = QueryDict("tipo=noticia&periodo=ano&pagina=2")
    chips = {c.label: c.remove_url for c in listing.chips(listing.parse(query), query)}

    assert chips["Este ano"] == "?tipo=noticia"


# --- ordem ---


def test_list_order_offers_only_recent_until_reads_exist(client, articles):
    filters = listing.parse(QueryDict("ordem=lidas"))

    assert filters.order == "recentes"  # "lidas" chega com as leituras (E39)
    assert listing.options(filters).orders == {}
    html = client.get("/publicacoes/?ordem=lidas").content.decode()
    assert 'name="ordem"' not in html
    assert html.index("Pêndulo na sala") < html.index("Horta de 2020")


def test_search_order_by_relevance_or_recent(client, carla, taxonomy):
    t = taxonomy
    publish(carla, "Horta na escola", t["fisica"], t["noticia"], days_ago=30)
    publish(
        carla, "Oficina de solo", t["fisica"], t["noticia"], days_ago=1, body="Falamos da horta."
    )

    relevance = client.get("/busca/?q=horta").content.decode()
    recent = client.get("/busca/?q=horta&ordem=recentes").content.decode()

    assert relevance.index("Horta na escola") < relevance.index("Oficina de solo")
    assert recent.index("Oficina de solo") < recent.index("Horta na escola")
    assert 'id="filtro-ordem-relevancia"' in relevance
    assert "Remover filtro Mais recentes" in recent
    assert "Remover filtro Mais relevantes" not in relevance


def test_search_filters_by_professor_and_period(client, articles, carla, taxonomy):
    t = taxonomy
    publish(carla, "Horta da Carla", t["fisica"], t["noticia"], days_ago=90)

    html = client.get(
        "/busca/", {"q": "horta", "professor": slug_of(carla), "periodo": "30-dias"}
    ).content.decode()

    assert "Horta da Carla" not in html
    assert "Horta de 2020" not in html
    assert 'name="q" value="horta"' in html


# --- HTMX, URL e aceite ---


FILTERED_URL = "/publicacoes/?area=natureza&tipo=entrevista&periodo=30-dias"


def test_filter_form_swaps_region_and_pushes_url(client, articles):
    html = client.get("/publicacoes/").content.decode()

    start = html.index('hx-target="#listing-region"')
    bar = html[start : html.index("</form>", start)]
    assert 'hx-select="#listing-region"' in bar
    assert 'hx-push-url="true"' in bar
    assert 'hx-select-oob="#listing-count"' in bar
    assert 'method="get"' in bar
    assert 'hx-get="/publicacoes/"' in bar
    assert 'id="filtro-periodo-30-dias"' in bar
    assert 'id="listing-count"' in html


def test_url_reproduces_filter_with_and_without_javascript(client, articles):
    """Aceite da E37: a URL que o HTMX põe no histórico, aberta sem JavaScript, mostra a mesma
    lista filtrada que a troca feita pelo HTMX."""
    with_htmx = client.get(FILTERED_URL, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="listing-region")
    without_js = client.get(FILTERED_URL)

    assert with_htmx.status_code == without_js.status_code == 200
    assert region(with_htmx.content.decode()) == region(without_js.content.decode())
    assert titles(region(without_js.content.decode()), articles) == {"Feira de ciências"}
    assert "Remover filtro Últimos 30 dias" in without_js.content.decode()
    assert "HX-Request" in without_js["Vary"]


def test_chip_links_work_with_and_without_htmx(client, articles):
    html = client.get("/publicacoes/?tipo=noticia&tipo=entrevista").content.decode()

    assert 'href="/publicacoes/?tipo=entrevista"' in html
    assert 'hx-get="/publicacoes/?tipo=entrevista"' in html


def test_area_page_keeps_fixed_filter_with_new_filters(client, articles, bruno):
    html = client.get(f"/areas/natureza/?professor={slug_of(bruno)}").content.decode()

    assert titles(region(html), articles) == {"Feira de ciências"}
    assert "Área: Ciências da Natureza" in html
    assert 'hx-get="/areas/natureza/"' in html


# --- cache ---


def test_cache_token_ignores_parameter_order_and_junk(taxonomy):
    a = listing.parse(QueryDict("tipo=noticia&tipo=entrevista&utm=x&area=natureza"))
    b = listing.parse(QueryDict("area=natureza&tipo=entrevista&tipo=noticia&tipo=noticia"))

    assert a.cache_token() == b.cache_token()
    assert a.cache_token() != listing.parse(QueryDict("area=natureza")).cache_token()


def test_listing_is_cached_and_publishing_invalidates(client, articles, carla, taxonomy):
    url = "/publicacoes/?tipo=noticia"
    uncached = _count_queries(client, url)
    cached = _count_queries(client, url)
    assert cached < uncached
    Article.objects.update(title="Trocado sem avisar")  # update() não dispara sinais
    assert "Pêndulo na sala" in client.get(url).content.decode()  # ainda do cache

    publish(carla, "Notícia fresquinha", taxonomy["fisica"], taxonomy["noticia"])

    html = client.get(url).content.decode()
    assert "Notícia fresquinha" in html
    assert "Pêndulo na sala" not in html


def _count_queries(client, url: str) -> int:
    with CaptureQueriesContext(connection) as ctx:
        client.get(url)
    return len(ctx.captured_queries)


def test_search_results_are_cached_per_term(client, carla, taxonomy):
    publish(carla, "Horta na escola", taxonomy["fisica"], taxonomy["noticia"])
    client.get("/busca/?q=horta")
    Article.objects.update(title="Título trocado sem sinal")  # update() não avisa o cache

    assert "Horta na escola" in client.get("/busca/?q=horta").content.decode()
    assert "Horta na escola" not in client.get("/busca/?q=horta&ordem=recentes").content.decode()


def test_card_count_matches_in_cached_pages(client, carla, taxonomy):
    for n in range(listing.PER_PAGE + 3):
        publish(carla, f"Item {n:02d}", taxonomy["fisica"], taxonomy["noticia"], days_ago=n)

    client.get("/publicacoes/")
    html = client.get("/publicacoes/").content.decode()
    more = client.get("/publicacoes/?pagina=2", HTTP_HX_REQUEST="true").content.decode()

    assert "15 publicações" in html
    assert "Item 11" in html
    assert "Item 12" not in html
    assert "Item 12" in more
    assert "Item 14" in more
    assert "Item 00" not in more
    assert "Item 11" not in more
