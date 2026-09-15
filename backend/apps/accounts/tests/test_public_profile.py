"""Perfil público e "Quem escreve" (docs/12, docs/13, E22)."""

import pytest
from django.urls import reverse

from apps.accounts import public_views, selectors
from apps.accounts.services import deactivate_user
from apps.publications import services
from apps.publications.cache import public_version
from apps.publications.models import Article, ArticleContributor
from tests.factories import (
    ArticleFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

Role = ArticleContributor.Role


def publish(author, title, **fields):
    article = ArticleFactory(ready=True, author=author, created_by=author, title=title, **fields)
    services.publish(author, article)
    return Article.objects.get(pk=article.pk)


def credit(article, user, role, **fields):
    return ArticleContributor.objects.create(
        article=article, user=user, display_name=user.public_name, role=role, order=5, **fields
    )


@pytest.fixture
def carla():
    user = UserFactory(full_name="Carla Souza", email="carla@professor.educacao.sp.gov.br")
    profile = user.profile
    profile.headline = "Professora de Biologia"
    profile.bio = "Primeira linha.\nSegunda linha."
    profile.since_year = 2019
    profile.education = [
        {"degree": "Licenciatura em Biologia", "institution": "UFXX", "year": 2012}
    ]
    profile.links = [
        {"label": "Lattes", "url": "https://lattes.cnpq.br/123"},
        {"label": "Ruim", "url": "javascript:alert(1)"},
    ]
    profile.save()
    return user


@pytest.fixture
def tabs_data(carla):
    """Carla: 1 como autora, 1 como coautora, 1 colaboração, 1 revisão, 1 edição, 1 rascunho."""
    other = UserFactory(full_name="Rafael Lima")
    as_author = publish(carla, "Como autora")
    as_coauthor = publish(other, "Como coautora")
    credit(as_coauthor, carla, Role.COAUTHOR)
    collab = publish(other, "Colaboração")
    credit(collab, carla, Role.COLLABORATOR)
    review = publish(other, "Revisão")
    credit(review, carla, Role.REVIEWER)
    edit = publish(other, "Edição")
    credit(edit, carla, Role.EDITOR)
    hidden = publish(other, "Crédito escondido")
    credit(hidden, carla, Role.COLLABORATOR, show_in_credits=False)
    ArticleFactory(ready=True, author=carla, created_by=carla, title="Rascunho da Carla")
    return {"author": as_author, "coauthor": as_coauthor, "review": review}


def titles(response):
    return [card.title for card in response.context["cards"]]


# --- abas ---


def test_tabs_split_author_and_collaborations(client, carla, tabs_data):
    url = carla.profile.get_absolute_url()

    assert url == "/professores/carla-souza/"
    everything = client.get(url)
    author = client.get(url, {"aba": "autor"})
    collaborations = client.get(url, {"aba": "colaboracoes"})

    assert set(titles(everything)) == {
        "Como autora",
        "Como coautora",
        "Colaboração",
        "Revisão",
        "Edição",
    }
    assert set(titles(author)) == {"Como autora", "Como coautora"}
    assert set(titles(collaborations)) == {"Colaboração", "Revisão", "Edição"}
    counts = {t["key"]: t["count"] for t in everything.context["tabs"]}
    assert counts == {"todas": 5, "autor": 2, "colaboracoes": 3}
    assert author.context["tab"] == "autor"
    assert 'aria-current="page">\n                    Como autor(a)' in author.content.decode()


def test_reviewer_credit_respects_profile_setting(client, carla, tabs_data):
    carla.profile.show_reviewer_credit = False
    carla.profile.save()

    response = client.get(carla.profile.get_absolute_url(), {"aba": "colaboracoes"})

    assert set(titles(response)) == {"Colaboração", "Edição"}
    assert response.context["total"] == 4


def test_unknown_tab_falls_back_to_all(client, carla, tabs_data):
    response = client.get(carla.profile.get_absolute_url(), {"aba": "xyz"})

    assert response.context["tab"] == "todas"
    assert len(response.context["cards"]) == 5


def test_profile_articles_are_paginated_with_htmx(client, carla, monkeypatch):
    monkeypatch.setattr(public_views, "PROFILE_PER_PAGE", 2)
    for n in range(3):
        publish(carla, f"Texto {n}")
    url = carla.profile.get_absolute_url()

    first = client.get(url)
    more = client.get(url, {"pagina": 2}, HTTP_HX_REQUEST="true")

    assert len(first.context["cards"]) == 2
    assert "Carregar mais" in first.content.decode()
    assert more.templates[0].name == "accounts/partials/profile_more.html"
    assert len(more.context["cards"]) == 1


# --- dados exibidos ---


def test_profile_shows_public_data_and_never_email(client, carla):
    area = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza", color="verde")
    carla.profile.disciplines.add(DisciplineFactory(name="Biologia", area=area))

    html = client.get(carla.profile.get_absolute_url()).content.decode()

    assert "Carla Souza" in html
    assert "Professora de Biologia" in html
    assert "Na escola desde 2019" in html
    assert "Primeira linha.<br>Segunda linha." in html
    assert "Licenciatura em Biologia, UFXX, 2012" in html
    assert 'href="https://lattes.cnpq.br/123"' in html
    assert 'rel="noopener nofollow"' in html
    assert "javascript:" not in html
    assert 'href="/disciplinas/' in html
    assert "from-area-verde-soft" in html  # cabeçalho na cor da área principal
    assert "carla@professor" not in html
    assert "Equipe" not in html  # papel no sistema
    assert "Ainda não há publicações" in html


@pytest.mark.parametrize(
    ("kind", "headline", "expected"),
    [
        ("teacher", "Professora de Biologia", ""),
        ("teacher", "Biologia e Ciências", "Professor"),
        ("coordinator", "Coordenadora pedagógica", ""),
        ("principal", "Diretora", ""),
        ("monitor", "", "Monitor"),
        ("librarian", "Responsável pela biblioteca", ""),
        ("other", "Secretaria", ""),
    ],
)
def test_kind_label_only_when_headline_does_not_mention_it(kind, headline, expected):
    user = UserFactory.build(staff_kind=kind)

    assert public_views.kind_label(user, headline) == expected


# --- estados ---


def test_hidden_profile_is_404_except_for_owner(client, carla):
    carla.profile.is_public = False
    carla.profile.save()
    url = carla.profile.get_absolute_url()

    assert client.get(url).status_code == 404
    client.force_login(UserFactory())
    assert client.get(url).status_code == 404
    client.force_login(carla)
    response = client.get(url)
    assert response.status_code == 200
    assert "Seu perfil está oculto" in response.content.decode()
    assert response["X-Robots-Tag"] == "noindex"


def test_unknown_slug_is_404(client):
    assert client.get(reverse("accounts:teacher_detail", args=["ninguem"])).status_code == 404


def test_deactivated_user_keeps_page_only_with_publications(client, carla):
    url = carla.profile.get_absolute_url()
    deactivate_user(carla)
    assert client.get(url).status_code == 404

    publish(UserFactory(), "Texto antigo")
    article = Article.objects.get(title="Texto antigo")
    credit(article, carla, Role.COAUTHOR)
    html = client.get(url).content.decode()

    assert "Texto antigo" in html
    assert "Primeira linha." not in html
    assert "lattes" not in html
    assert "Licenciatura" not in html


def test_edit_link_only_for_admin(client, carla):
    url = carla.profile.get_absolute_url()

    assert "Editar perfil" not in client.get(url).content.decode()
    client.force_login(UserFactory(admin=True))
    assert "Editar perfil" in client.get(url).content.decode()


# --- Quem escreve ---


@pytest.fixture
def team():
    natureza = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza")
    humanas = KnowledgeAreaFactory(name="Ciências Humanas", slug="humanas")
    ana = UserFactory(full_name="Ana Prado")
    bruno = UserFactory(full_name="Bruno Reis", staff_kind="monitor")
    celia = UserFactory(full_name="Célia Dias", staff_kind="principal")
    oculto = UserFactory(full_name="Oculto Silva")
    oculto.profile.is_public = False
    oculto.profile.save()
    inativo = UserFactory(full_name="Inativo Costa")
    deactivate_user(inativo)
    ana.profile.areas.add(humanas)
    old = publish(bruno, "Antiga", disciplines=[DisciplineFactory(area=natureza)])
    Article.objects.filter(pk=old.pk).update(published_at=old.published_at.replace(year=2020))
    publish(celia, "Nova", disciplines=[DisciplineFactory(area=humanas)])
    credit(old, celia, Role.REVIEWER)
    return {"natureza": natureza, "humanas": humanas}


def names(response):
    return [card.person.name for card in response.context["cards"]]


def test_team_list_shows_whole_public_team_most_recent_first(client, team):
    response = client.get(reverse("accounts:teacher_list"))

    assert names(response) == ["Célia Dias", "Bruno Reis", "Ana Prado"]
    cards = {card.person.name: card for card in response.context["cards"]}
    assert cards["Célia Dias"].published_count == 2
    assert cards["Célia Dias"].kind == "Direção"
    assert cards["Ana Prado"].published_count == 0
    assert 'href="/professores/ana-prado/"' in response.content.decode()


def test_team_list_filters_and_order(client, team):
    url = reverse("accounts:teacher_list")

    assert names(client.get(url, {"cargo": "monitores"})) == ["Bruno Reis"]
    assert names(client.get(url, {"cargo": "coordenacao"})) == ["Célia Dias"]
    assert names(client.get(url, {"area": "humanas"})) == ["Célia Dias", "Ana Prado"]
    assert names(client.get(url, {"ordem": "nome"})) == ["Ana Prado", "Bruno Reis", "Célia Dias"]
    empty = client.get(url, {"area": "natureza", "cargo": "professores"})
    assert "Ninguém com esses filtros" in empty.content.decode()


def test_team_selector_hides_reviewer_count_when_profile_asks(team):
    celia = selectors.team().get(full_name="Célia Dias")
    celia.profile.show_reviewer_credit = False
    celia.profile.save()

    assert selectors.team().get(full_name="Célia Dias").published_count == 1


# --- ligações com o resto do site ---


def test_masthead_links_to_team(client):
    html = client.get(reverse("accounts:teacher_list")).content.decode()

    assert 'aria-current="page">Quem escreve</a>' in html


def test_writer_names_link_to_profiles_on_home_area_and_article(client, carla):
    area = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza")
    article = publish(carla, "Feira", disciplines=[DisciplineFactory(area=area)])
    profile_link = 'href="/professores/carla-souza/"'

    home = client.get("/").content.decode()
    area_page = client.get(area.get_absolute_url()).content.decode()
    detail = client.get(article.get_absolute_url()).content.decode()

    assert profile_link in home
    assert 'href="/professores/"' in home
    assert profile_link in area_page
    assert 'href="/professores/?area=natureza"' in area_page
    assert profile_link in detail


def test_hidden_profile_is_not_linked(client, carla):
    carla.profile.is_public = False
    carla.profile.save()
    article = publish(carla, "Feira")

    assert (
        "/professores/carla-souza/" not in client.get(article.get_absolute_url()).content.decode()
    )


def test_profile_change_refreshes_home_cache(carla):
    before = public_version()
    carla.profile.headline = "Professora de Química"
    carla.profile.save()
    after_profile = public_version()
    carla.last_login = carla.date_joined
    carla.save(update_fields=["last_login"])

    assert after_profile > before
    assert public_version() == after_profile
