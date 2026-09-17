"""Página de busca /busca/ (docs/12, docs/19; E36)."""

import re

import pytest
from django.urls import reverse

from apps.publications import search, services
from apps.taxonomy.models import Topic
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db

URL = "/busca/"


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza", display_name="Carla Souza")


def publish(user, title, body="Texto da publicação.", **fields):
    article = ArticleFactory(ready=True, author=user, created_by=user, title=title)
    services.update_article(user, article, body_json=text_doc(body), **fields)
    return services.publish(user, article)


def page(client, **params) -> str:
    return client.get(URL, params).content.decode()


def results_section(html: str) -> str:
    """Só a coluna de publicações (sem masthead nem o grupo de pessoas)."""
    start = html.index('id="search-articles-title"')
    end = html.index("</section>", start)
    return html[start:end]


# --- rota, noindex e página sem termo ---


def test_route_name_and_empty_query_suggests_areas(client):
    KnowledgeAreaFactory(name="Linguagens e Códigos", slug="linguagens-teste", color="coral")

    response = client.get(URL)
    html = response.content.decode()

    assert reverse("search:results") == URL
    assert response.status_code == 200
    assert '<meta name="robots" content="noindex">' in html
    assert 'name="q"' in html
    assert "Linguagens e Códigos" in html
    assert 'id="search-articles-title"' not in html


def test_results_page_is_noindex_without_canonical(client, author):
    publish(author, "Horta da escola")

    html = page(client, q="horta")

    assert '<meta name="robots" content="noindex">' in html
    assert 'rel="canonical"' not in html
    assert "application/ld+json" not in html


# --- grupo publicações: trechos destacados ---


def test_publication_group_shows_highlighted_snippet(client, author):
    publish(
        author,
        "Feira de ciências",
        body="Na feira, os alunos do segundo ano mostraram experiências com ímãs e bússolas.",
    )

    html = page(client, q="imas")

    section = results_section(html)
    assert "Feira de ciências" in section
    assert "1 publicação" in section
    assert "<mark>ímãs</mark>" in section
    assert 'class="search-snippet' in section


def test_snippet_escapes_html_and_only_allows_mark(client, author):
    publish(
        author,
        "Texto perigoso",
        body='Robótica <script>alert("x")</script> e <img src=x onerror=alert(1)> no pátio.',
    )

    html = page(client, q="robotica")

    section = results_section(html)
    assert "<mark>Robótica</mark>" in section
    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in section  # o PostgreSQL deixa passar
    snippet = re.search(r'class="search-snippet[^"]*">(.*?)</p>', section, re.S).group(1)
    assert set(re.findall(r"</?([a-z]+)", snippet)) == {"mark"}


def test_query_itself_is_escaped(client, author):
    response = client.get(URL, {"q": '<script>alert("q")</script>'})
    html = response.content.decode()

    assert response.status_code == 200
    assert '<script>alert("q")' not in html
    assert "&lt;script&gt;" in html


def test_highlight_escapes_limits_and_marks():
    raw = f"a <b>&amp; {search.MARK_START}Física{search.MARK_STOP} " + "palavra " * 60
    body = raw.replace(search.MARK_START, "").replace(search.MARK_STOP, "")

    html = search.highlight(raw, body_text=body)

    assert html.startswith("a &lt;b&gt;&amp;amp; <mark>Física</mark> palavra")
    assert html.endswith("…")
    assert len(re.sub(r"<[^>]+>", "", html)) <= search.SNIPPET_MAX_CHARS + 30  # entidades
    assert search.highlight("", body_text="") == ""


def test_highlight_marks_ellipsis_when_snippet_starts_mid_body():
    body = "Começo do texto que fica de fora. Depois vem a horta da escola."
    raw = f"Depois vem a {search.MARK_START}horta{search.MARK_STOP} da escola."

    html = search.highlight(raw, body_text=body)

    assert html == "…Depois vem a <mark>horta</mark> da escola."


def test_drafts_never_appear(client, author):
    ArticleFactory(ready=True, author=author, created_by=author, title="Astronomia em rascunho")
    publish(author, "Astronomia no pátio")

    html = page(client, q="astronomia")

    section = results_section(html)
    assert "Astronomia no pátio" in section
    assert "rascunho" not in section


def test_filters_apply_over_search_and_keep_the_term(client, author):
    noticia = ArticleTypeFactory(name="Notícia", slug="noticia-busca")
    entrevista = ArticleTypeFactory(name="Entrevista", slug="entrevista-busca")
    publish(author, "Reciclagem no intervalo", type=noticia)
    publish(author, "Reciclagem com a diretora", type=entrevista)

    html = page(client, q="reciclagem", tipo="entrevista-busca")

    section = results_section(html)
    assert "Reciclagem com a diretora" in section
    assert "Reciclagem no intervalo" not in section
    assert '<input type="hidden" name="q" value="reciclagem">' in section
    assert "?q=reciclagem" in section  # limpar filtros ou remover o chip mantém o termo


def test_load_more_returns_next_results_only(client, author):
    for n in range(14):
        publish(author, f"Olimpíada de matemática {n}")

    response = client.get(URL, {"q": "olimpiada", "pagina": 2}, HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert 'hx-swap-oob="beforeend:#search-results"' in html
    assert html.count("<article") == 2
    assert "<header" not in html


# --- fallback por trigramas ---


def test_typo_falls_back_to_similar_titles(client, author):
    publish(author, "Astronomia na escola", body="Observamos a Lua.")
    publish(author, "Horta comunitária")

    html = page(client, q="astronomai")

    section = results_section(html)
    assert "Astronomia na escola" in section
    assert "Horta comunitária" not in section
    assert "Mostrando títulos parecidos" in section
    assert "<mark>" not in section


def test_typo_without_accent_in_title(client, author):
    publish(author, "Educação física inclusiva")

    html = page(client, q="educasao fisica")

    assert "Educação física inclusiva" in results_section(html)


def test_exact_results_do_not_use_fallback(client, author):
    publish(author, "Astronomia na escola")
    publish(author, "Astronomya errada no título")

    html = page(client, q="astronomia")

    section = results_section(html)
    assert "Mostrando títulos parecidos" not in section
    assert "Astronomya" not in section


def test_nothing_found_suggests_areas(client):
    KnowledgeAreaFactory(name="Matemática e suas Tecnologias", slug="mat-teste", color="azul")

    response = client.get(URL, {"q": "zzzqqq"})
    html = response.content.decode()

    assert response.status_code == 200
    assert "Nada encontrado para “zzzqqq”" in html
    assert "Tente termos mais gerais ou navegue por área." in html
    assert "Matemática e suas Tecnologias" in html


# --- grupo pessoas ---


def test_people_group_by_name_with_typo_and_accent(client, author):
    UserFactory(full_name="João Brandão", display_name="")

    html = page(client, q="joao brandao")
    assert "Pessoas da equipe" in html
    assert "João Brandão" in html

    html = page(client, q="Cala Souza")
    assert "Carla Souza" in html


def test_people_group_by_headline_and_discipline(client):
    biologa = UserFactory(full_name="Marta Lins")
    biologa.profile.headline = "Professora de Biologia"
    biologa.profile.save()
    quimico = UserFactory(full_name="Paulo Reis")
    quimico.profile.disciplines.add(DisciplineFactory(name="Química", slug="quimica-busca"))

    assert "Marta Lins" in page(client, q="biologia")
    assert "Paulo Reis" in page(client, q="quimica")


def test_people_group_hides_private_profiles_and_inactive_accounts(client):
    hidden = UserFactory(full_name="Renata Oculta")
    hidden.profile.is_public = False
    hidden.profile.save()
    UserFactory(full_name="Renata Inativa", is_active=False)

    html = page(client, q="renata")

    assert "Renata Oculta" not in html
    assert "Renata Inativa" not in html


def test_people_group_limited_to_five(client):
    for n in range(7):
        UserFactory(full_name=f"Beatriz Almeida {n}", display_name=f"Beatriz Almeida {n}")

    html = page(client, q="beatriz almeida")

    assert len(re.findall(r"Beatriz Almeida \d", html)) == 5


# --- grupo disciplinas, áreas e tópicos ---


def test_taxonomy_group_with_area_discipline_and_topic(client):
    area = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza-busca", color="verde")
    discipline = DisciplineFactory(name="Física Moderna", slug="fisica-moderna", area=area)
    Topic.objects.create(name="Física no cotidiano", slug="fisica-cotidiano", is_active=True)
    Topic.objects.create(name="Física inativa", slug="fisica-inativa", is_active=False)

    html = page(client, q="fisica")

    assert "Disciplinas e tópicos" in html
    assert f'href="{discipline.get_absolute_url()}"' in html
    assert 'href="/topicos/fisica-cotidiano/"' in html  # E43: tópico leva à página dele
    assert "Física inativa" not in html

    html = page(client, q="natureza")
    assert f'href="{area.get_absolute_url()}"' in html


# --- limite, masthead, 404 e JSON-LD ---


def test_rate_limit_per_ip(client, settings):
    settings.SEARCHES_PER_MINUTE = 2

    assert client.get(URL, {"q": "a1"}).status_code == 200
    assert client.get(URL, {"q": "a2"}).status_code == 200
    response = client.get(URL, {"q": "a3"})

    assert response.status_code == 429
    assert "Muitas buscas em pouco tempo" in response.content.decode()
    assert client.get(URL).status_code == 200  # sem termo não conta


def test_masthead_has_search_on_every_public_page(client):
    html = client.get("/").content.decode()

    assert 'role="search"' in html
    assert 'action="/busca/"' in html
    assert 'href="/busca/"' in html


def test_404_page_has_search_field(client):
    response = client.get("/nao-existe-mesmo/")

    html = response.content.decode()
    assert response.status_code == 404
    assert 'id="search-page-q"' in html
