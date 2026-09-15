"""Lista, área, disciplina, tipo e agenda (docs/12, E21)."""

from datetime import timedelta

import pytest
from django.http import QueryDict
from django.utils import timezone

from apps.accounts.models import TeacherProfile
from apps.publications import listing, services
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


@pytest.fixture
def taxonomy():
    natureza = KnowledgeAreaFactory(
        name="Ciências da Natureza", slug="natureza", short_name="Natureza", color="verde", order=1
    )
    humanas = KnowledgeAreaFactory(
        name="Ciências Humanas", slug="humanas", short_name="Humanas", color="ambar", order=2
    )
    return {
        "natureza": natureza,
        "humanas": humanas,
        "fisica": DisciplineFactory(name="Física", slug="fisica", area=natureza),
        "quimica": DisciplineFactory(name="Química", slug="quimica", area=natureza),
        "historia": DisciplineFactory(name="História", slug="historia", area=humanas),
        "noticia": ArticleTypeFactory(name="Notícia", slug="noticia"),
        "entrevista": ArticleTypeFactory(name="Entrevista", slug="entrevista"),
    }


def publish(author, title, discipline, article_type, *, days_ago=0, **fields):
    article = ArticleFactory(
        ready=True, author=author, created_by=author, title=title, disciplines=[discipline]
    )
    # Tipo e data do evento antes de publicar: a checklist exige a data em eventos.
    Article.objects.filter(pk=article.pk).update(type=article_type, **fields)
    article.refresh_from_db()
    services.publish(author, article)
    Article.objects.filter(pk=article.pk).update(
        published_at=timezone.now() - timedelta(days=days_ago)
    )
    return Article.objects.get(pk=article.pk)


@pytest.fixture
def articles(author, taxonomy):
    t = taxonomy
    return [
        publish(author, "Pêndulo na sala", t["fisica"], t["noticia"], days_ago=1),
        publish(author, "Entrevista com químico", t["quimica"], t["entrevista"], days_ago=2),
        publish(author, "Memórias do bairro", t["historia"], t["entrevista"], days_ago=3),
    ]


# --- filtros ---


def test_parse_ignores_unknown_values(taxonomy):
    filters = listing.parse(QueryDict("area=inexistente&disciplina=fisica&disciplina=xyz&tipo=?"))

    assert filters.area is None
    assert [d.slug for d in filters.disciplines] == ["fisica"]
    assert filters.types == []


def test_parse_drops_disciplines_outside_chosen_area(taxonomy):
    filters = listing.parse(QueryDict("area=humanas&disciplina=fisica&disciplina=historia"))

    assert [d.slug for d in filters.disciplines] == ["historia"]


def test_chip_removal_urls(taxonomy):
    query = QueryDict("area=natureza&disciplina=fisica&disciplina=quimica&tipo=noticia&pagina=3")
    chips = listing.chips(listing.parse(query), query)

    by_label = {c.label: c.remove_url for c in chips}
    assert by_label["Área: Ciências da Natureza"] == "?tipo=noticia"  # leva as disciplinas junto
    assert by_label["Física"] == "?area=natureza&disciplina=quimica&tipo=noticia"
    assert by_label["Notícia"] == "?area=natureza&disciplina=fisica&disciplina=quimica"


def test_fixed_filter_chip_is_not_removable(taxonomy):
    filters = listing.parse(QueryDict("area=humanas"), fixed_area=taxonomy["natureza"])

    assert filters.area is None  # a página fixa a área; o parâmetro é ignorado
    assert listing.chips(filters, QueryDict()) == [listing.Chip("Área: Ciências da Natureza")]


# --- /publicacoes/ ---


def test_list_shows_published_only(client, articles, author, taxonomy):
    ArticleFactory(ready=True, author=author, created_by=author, title="Rascunho escondido")

    response = client.get("/publicacoes/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "3 publicações" in html
    assert "Pêndulo na sala" in html
    assert "Rascunho escondido" not in html
    assert html.count("<h1") == 1


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("area=natureza", {"Pêndulo na sala", "Entrevista com químico"}),
        ("disciplina=historia", {"Memórias do bairro"}),
        ("tipo=entrevista", {"Entrevista com químico", "Memórias do bairro"}),
        ("area=natureza&tipo=entrevista", {"Entrevista com químico"}),
        ("disciplina=fisica&disciplina=historia", {"Pêndulo na sala", "Memórias do bairro"}),
    ],
)
def test_list_filters_without_javascript(client, articles, query, expected):
    html = client.get(f"/publicacoes/?{query}").content.decode()

    shown = {a.title for a in articles if a.title in html}
    assert shown == expected


def test_article_with_two_disciplines_is_not_repeated(client, author, taxonomy):
    article = publish(author, "Ciência e história", taxonomy["fisica"], taxonomy["noticia"])
    article.disciplines.add(taxonomy["quimica"])

    html = client.get("/publicacoes/?area=natureza").content.decode()

    assert "1 publicação" in html
    assert html.count("Ciência e história") == 1


def test_list_form_marks_selected_values(client, articles):
    html = client.get("/publicacoes/?area=natureza&tipo=noticia").content.decode()

    assert "Remover filtro Área: Ciências da Natureza" in html
    assert "Remover filtro Notícia" in html
    assert "História" not in html.split("<form")[1].split("</form>")[0]  # só disciplinas da área


def test_empty_filtered_list(client, articles):
    html = client.get("/publicacoes/?disciplina=historia&tipo=noticia").content.decode()

    assert "Nenhuma publicação com esses filtros" in html
    assert "Limpar filtros" in html


def test_list_load_more(client, author, taxonomy):
    for n in range(listing.PER_PAGE + 2):
        publish(author, f"Item {n:02d}", taxonomy["fisica"], taxonomy["noticia"], days_ago=n)

    first = client.get("/publicacoes/?area=natureza").content.decode()
    assert "Item 11" in first
    assert "Item 12" not in first
    assert "pagina=2" in first
    assert "area=natureza" in first

    more = client.get("/publicacoes/?area=natureza&pagina=2", HTTP_HX_REQUEST="true")
    html = more.content.decode()
    assert 'hx-swap-oob="beforeend:#article-grid"' in html
    assert "Item 12" in html
    assert "Item 13" in html
    assert "Item 00" not in html


def test_list_query_count(client, author, taxonomy, django_assert_max_num_queries):
    for n in range(listing.PER_PAGE):
        publish(author, f"Item {n}", taxonomy["fisica"], taxonomy["noticia"], days_ago=n)

    with django_assert_max_num_queries(20):
        client.get("/publicacoes/?area=natureza&tipo=noticia")


# --- área, disciplina, tipo ---


def test_area_page(client, articles, author, taxonomy):
    other = UserFactory(full_name="Bruno Lima")
    TeacherProfile.objects.get(user=other).areas.add(taxonomy["natureza"])

    response = client.get("/areas/natureza/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "<title>Ciências da Natureza · Jornal Escolar</title>" in html
    assert "2 publicações" in html
    assert "Pêndulo na sala" in html
    assert "Memórias do bairro" not in html
    assert 'href="/disciplinas/fisica/"' in html
    assert "Quem escreve sobre a área" in html
    assert "Bruno Lima" in html
    assert "Carla Souza" in html
    assert "Área: Ciências da Natureza" in html


def test_area_hero_needs_cover(client, articles):
    # Sem capa: nenhuma publicação vira destaque, todas ficam na grade.
    html = client.get("/areas/natureza/").content.decode()

    assert 'fetchpriority="high"' not in html


def test_area_page_filters_by_type(client, articles):
    html = client.get("/areas/natureza/?tipo=entrevista").content.decode()

    assert "Entrevista com químico" in html
    assert "Pêndulo na sala" not in html


def test_inactive_or_unknown_area_is_404(client, taxonomy):
    taxonomy["humanas"].is_active = False
    taxonomy["humanas"].save()

    assert client.get("/areas/humanas/").status_code == 404
    assert client.get("/areas/nao-existe/").status_code == 404


def test_discipline_page_and_empty_state(client, articles, taxonomy):
    html = client.get("/disciplinas/fisica/").content.decode()
    assert "Pêndulo na sala" in html
    assert "Entrevista com químico" not in html
    assert 'href="/areas/natureza/"' in html

    DisciplineFactory(name="Biologia", slug="biologia", area=taxonomy["natureza"])
    empty = client.get("/disciplinas/biologia/").content.decode()
    assert "Ainda não há publicações em Biologia" in empty
    assert "Ver outras disciplinas" in empty


def test_type_page(client, articles):
    html = client.get("/tipos/entrevista/?area=humanas").content.decode()

    assert "Memórias do bairro" in html
    assert "Entrevista com químico" not in html
    assert "Tipo: Entrevista" in html


# --- agenda ---


def test_agenda_splits_upcoming_and_past(client, author, taxonomy):
    event_type = ArticleTypeFactory(name="Evento", slug="evento", has_event_date=True)
    now = timezone.now()
    publish(author, "Sarau", taxonomy["historia"], event_type, event_at=now + timedelta(days=9))
    publish(author, "Feira", taxonomy["fisica"], event_type, event_at=now + timedelta(days=2))
    publish(author, "Formatura", taxonomy["fisica"], event_type, event_at=now - timedelta(days=5))

    html = client.get("/agenda/").content.decode()

    upcoming, past = html.split("Já aconteceram")
    assert upcoming.index("Feira") < upcoming.index("Sarau")
    assert "Formatura" in past
    assert "Ciências Humanas" in upcoming  # etiqueta da área
    # Só os que já aconteceram levam o selo (a lista "past" da página não pode vazar para o item).
    assert "Aconteceu" not in upcoming
    assert "Aconteceu" in past


def test_agenda_empty(client):
    html = client.get("/agenda/").content.decode()

    assert "Nenhum evento marcado" in html
    assert "Já aconteceram" not in html


# --- navegação ---


def test_masthead_lists_active_areas_with_current_page(client, taxonomy):
    html = client.get("/areas/natureza/").content.decode()

    nav = html.split('aria-label="Seções do jornal"')[1].split("</nav>")[0]
    assert "Natureza" in nav
    assert "Humanas" in nav
    assert nav.index("Natureza") < nav.index("Humanas")
    assert 'aria-current="page"' in nav
    assert 'href="/agenda/"' in nav


def test_masthead_areas_follow_admin_changes(client, taxonomy):
    client.get("/")  # guarda as áreas em cache
    area = taxonomy["humanas"]
    area.short_name = "Sociedade"
    area.save()

    assert "Sociedade" in client.get("/").content.decode()


def test_home_links_to_agenda_and_lists(client, author, taxonomy):
    event_type = ArticleTypeFactory(name="Evento", slug="evento", has_event_date=True)
    publish(
        author,
        "Sarau",
        taxonomy["historia"],
        event_type,
        event_at=timezone.now() + timedelta(days=3),
    )

    html = client.get("/").content.decode()

    assert 'href="/agenda/"' in html
    assert 'href="/publicacoes/"' in html
