"""Pautas: quadro, "Virar pauta" e conversão em rascunho (E49; docs/21, "Da sugestão à
publicação").

Aceite: o rascunho nasce com a fonte.
"""

import json
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.accounts import privacy
from apps.accounts.services import ensure_profile
from apps.curation import ideas, recommend, services
from apps.curation.models import NewsItem, NewsItemClassification, NewsRecommendation, StoryIdea
from apps.editorial.models import Notification
from apps.publications import services as publications
from apps.publications.models import Article
from apps.taxonomy.models import Topic
from tests.factories import ArticleTypeFactory, DisciplineFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db

Status = StoryIdea.Status
Method = NewsItemClassification.Method
HX = {"HTTP_HX_REQUEST": "true"}
BOARD = "/painel/pautas/"


@pytest.fixture
def robotica():
    return Topic.objects.create(name="Robótica", keywords=["robô"])


@pytest.fixture
def fisica():
    return DisciplineFactory(name="Física")


@pytest.fixture
def item(make_source, robotica, fisica):
    source = make_source(name="Agência Exemplo")
    news = NewsItem.objects.create(
        source=source,
        title="Robô de estudantes vence olimpíada",
        url="https://noticia.exemplo.org/robo",
        canonical_url="https://noticia.exemplo.org/robo",
        url_hash="a" * 64,
        title_hash="a" * 64,
        published_at=timezone.now(),
        fetched_at=timezone.now(),
        language="pt",
    )
    NewsItemClassification.objects.create(
        item=news, topic=robotica, score=0.9, method=Method.KEYWORD
    )
    NewsItemClassification.objects.create(
        item=news, discipline=fisica, score=0.9, method=Method.KEYWORD
    )
    return news


@pytest.fixture
def ana(robotica):
    user = UserFactory(full_name="Ana Lima")
    ensure_profile(user).topics.set([robotica])
    return user


@pytest.fixture
def rec(ana, item):
    recommend.recommend_for_user(ana)
    return NewsRecommendation.objects.get(user=ana, item=item)


def test_virar_pauta_cria_pauta_atribuida_com_topicos_e_fonte(ana, rec, item, robotica, fisica):
    idea = ideas.idea_from_recommendation(ana, rec)

    assert idea.title == "Pauta: Robô de estudantes vence olimpíada"
    assert idea.status == Status.ASSIGNED
    assert idea.assigned_to == ana
    assert idea.proposed_by == ana
    assert idea.item == item
    assert list(idea.topics.all()) == [robotica]
    assert list(idea.disciplines.all()) == [fisica]
    rec.refresh_from_db()
    assert rec.status == NewsRecommendation.Status.CONVERTED
    assert rec.story_idea == idea
    # Clicar de novo não cria outra.
    assert ideas.idea_from_recommendation(ana, rec) == idea
    assert StoryIdea.objects.count() == 1


def test_virar_pauta_pela_tela_com_htmx(client, ana, rec):
    client.force_login(ana)

    response = client.post(reverse("curation:suggestion_to_idea", args=[rec.pk]), **HX)

    html = response.content.decode()
    assert "Virou pauta" in html
    assert "Ver no quadro de pautas" in html
    assert StoryIdea.objects.filter(assigned_to=ana).count() == 1
    salvas = client.get("/painel/sugestoes/", {"aba": "salvas"}).content.decode()
    assert "Robô de estudantes" in salvas


def test_nao_vira_pauta_a_sugestao_de_outra_pessoa(client, rec):
    client.force_login(UserFactory())

    response = client.post(reverse("curation:suggestion_to_idea", args=[rec.pk]))

    assert response.status_code == 404
    assert not StoryIdea.objects.exists()


def test_rascunho_nasce_com_fonte_topicos_e_disciplinas(ana, rec, item, robotica, fisica):
    """Aceite da E49."""
    idea = ideas.idea_from_recommendation(ana, rec)

    article = ideas.start_draft(ana, idea)

    assert article.status == Article.Status.DRAFT
    assert article.title == "Robô de estudantes vence olimpíada"
    assert article.sources == [
        {
            "title": "Robô de estudantes vence olimpíada",
            "url": "https://noticia.exemplo.org/robo",
            "publisher": "Agência Exemplo",
        }
    ]
    assert article.origin_news_item == item
    assert list(article.topics.all()) == [robotica]
    assert list(article.disciplines.all()) == [fisica]
    assert article.contributors.get().user == ana
    idea.refresh_from_db()
    assert idea.status == Status.IN_PROGRESS
    assert idea.article == article


def test_criar_rascunho_pela_tela_abre_o_editor_com_a_dica(client, ana, rec):
    idea = ideas.idea_from_recommendation(ana, rec)
    client.force_login(ana)

    response = client.post(
        reverse("curation:story_idea_action", args=[idea.pk, "rascunho"]), follow=True
    )

    article = Article.objects.get()
    assert response.redirect_chain[-1][0] == reverse("publications:edit", args=[article.pk])
    html = response.content.decode()
    assert "Escreva com suas palavras. Cite a fonte." in html
    assert "data-origin-hint" in html


def test_checklist_exige_fonte_quando_nasce_de_noticia(ana, rec):
    article = ideas.start_draft(ana, ideas.idea_from_recommendation(ana, rec))
    codes = {c.code for c in publications.checklist(article)}
    assert "source_missing" not in codes

    article.sources = []
    article.save()

    assert "source_missing" in {c.code for c in publications.checklist(article)}


def test_publicar_conclui_a_pauta(ana, rec):
    idea = ideas.idea_from_recommendation(ana, rec)
    article = ideas.start_draft(ana, idea)
    article.type = ArticleTypeFactory()
    article.body_json = text_doc("Texto com as minhas palavras sobre o robô.")
    article.save()

    publications.publish(ana, article)

    idea.refresh_from_db()
    assert idea.status == Status.DONE
    assert idea.done_at is not None


def test_pauta_a_mao_aberta_pegar_devolver(ana, robotica):
    bruno = UserFactory(full_name="Bruno Reis")
    idea = ideas.create_idea(ana, title="  Horta   da escola ", notes="Falar com a merenda")
    assert idea.title == "Horta da escola"
    assert idea.status == Status.OPEN
    assert idea.assigned_to is None

    ideas.take(bruno, idea)
    idea.refresh_from_db()
    assert (idea.status, idea.assigned_to) == (Status.ASSIGNED, bruno)

    with pytest.raises(PermissionDenied):
        ideas.take(ana, idea)  # já tem dono
    with pytest.raises(PermissionDenied):
        ideas.release(ana, idea)  # só quem está com ela ou editor
    with pytest.raises(PermissionDenied):
        ideas.start_draft(ana, idea)

    ideas.release(bruno, idea)
    idea.refresh_from_db()
    assert (idea.status, idea.assigned_to) == (Status.OPEN, None)


def test_criar_rascunho_de_pauta_aberta_fica_com_quem_criou(ana):
    idea = ideas.create_idea(ana, title="Horta da escola")
    bruno = UserFactory()

    article = ideas.start_draft(bruno, idea)

    idea.refresh_from_db()
    assert idea.assigned_to == bruno
    assert article.sources == []
    assert article.origin_news_item is None
    # Sem notícia de origem, a checklist não pede fonte.
    assert "source_missing" not in {c.code for c in publications.checklist(article)}


def test_quadro_mostra_colunas_e_filtro_minhas(client, ana):
    bruno = UserFactory(full_name="Bruno Reis")
    ideas.create_idea(ana, title="Horta da escola")
    ideas.create_idea(bruno, title="Feira de ciências", keep=True)
    client.force_login(ana)

    html = client.get(BOARD).content.decode()
    assert "Abertas" in html
    assert "Em produção" in html
    assert "Horta da escola" in html
    assert "Feira de ciências" in html
    assert "Pegar para mim" in html

    mine = client.get(BOARD, {"minhas": "1"}).content.decode()
    assert "Horta da escola" in mine
    assert "Feira de ciências" not in mine


def test_criar_pauta_pela_tela_e_erro_sem_titulo(client, ana, robotica):
    client.force_login(ana)
    url = reverse("curation:story_idea_create")

    bad = client.post(url, {"title": "  "})
    assert bad.status_code == 400
    assert "Dê um título à pauta." in bad.content.decode()

    response = client.post(
        url, {"title": "Horta", "topics": [robotica.pk], "keep": "on"}, follow=True
    )
    assert "Pauta criada" in response.content.decode()
    idea = StoryIdea.objects.get()
    assert idea.assigned_to == ana
    assert list(idea.topics.all()) == [robotica]


def test_editar_pauta_corrige_a_classificacao_da_noticia(client, ana, rec, item, robotica):
    idea = ideas.idea_from_recommendation(ana, rec)
    cinema = Topic.objects.create(name="Cinema", keywords=[])
    client.force_login(ana)
    url = reverse("curation:story_idea_edit", args=[idea.pk])
    assert client.get(url).status_code == 200

    client.post(url, {"title": idea.title, "topics": [cinema.pk]})

    manual = NewsItemClassification.objects.filter(item=item, method=Method.MANUAL)
    assert {(c.topic, c.score) for c in manual.filter(topic__isnull=False)} == {(cinema, 1.0)}
    assert not manual.filter(discipline__isnull=False).exists()  # disciplinas desmarcadas
    # A classificação automática continua; a manual não some ao reclassificar.
    services.reclassify_items()
    assert manual.filter(topic=cinema).exists()


def test_so_quem_propoe_esta_com_ela_ou_editor_edita(client, ana):
    idea = ideas.create_idea(ana, title="Horta")
    url = reverse("curation:story_idea_edit", args=[idea.pk])

    client.force_login(UserFactory())
    assert client.get(url).status_code == 403

    client.force_login(UserFactory(editor=True))
    assert client.get(url).status_code == 200


def test_editor_atribui_a_pauta_e_a_pessoa_e_avisada(client, ana):
    editor = UserFactory(editor=True, full_name="Carla Editora")
    idea = ideas.create_idea(ana, title="Horta")
    client.force_login(editor)

    client.post(
        reverse("curation:story_idea_edit", args=[idea.pk]),
        {"title": "Horta", "assigned_to": ana.pk},
    )

    idea.refresh_from_db()
    assert (idea.status, idea.assigned_to) == (Status.ASSIGNED, ana)
    aviso = Notification.objects.get(user=ana)
    assert aviso.kind == Notification.Kind.STORY_IDEA
    assert aviso.message == "Carla Editora passou a pauta “Horta” para você"


def test_quem_nao_e_editor_nao_ve_o_campo_de_atribuir(client, ana):
    idea = ideas.create_idea(ana, title="Horta")
    client.force_login(ana)

    html = client.get(reverse("curation:story_idea_edit", args=[idea.pk])).content.decode()

    assert "Com quem está" not in html


def test_excluir_pauta_devolve_a_sugestao_para_as_salvas(client, ana, rec):
    idea = ideas.idea_from_recommendation(ana, rec)
    client.force_login(ana)

    client.post(reverse("curation:story_idea_action", args=[idea.pk, "excluir"]))

    assert not StoryIdea.objects.exists()
    rec.refresh_from_db()
    assert rec.status == NewsRecommendation.Status.SAVED


def test_nao_exclui_pauta_alheia_nem_com_rascunho(ana):
    idea = ideas.create_idea(ana, title="Horta", keep=True)
    with pytest.raises(PermissionDenied):
        ideas.delete(UserFactory(), idea)
    ideas.start_draft(ana, idea)
    idea.refresh_from_db()
    with pytest.raises(PermissionDenied):
        ideas.delete(ana, idea)
    ideas.delete(UserFactory(editor=True), idea)


def test_acao_desconhecida_e_404(client, ana):
    idea = ideas.create_idea(ana, title="Horta")
    client.force_login(ana)

    response = client.post(reverse("curation:story_idea_action", args=[idea.pk, "sumir"]))

    assert response.status_code == 404


def test_menu_conta_as_pautas_com_a_pessoa(client, ana):
    from apps.dashboard.menu import menu_items

    ideas.create_idea(ana, title="Horta", keep=True)
    ideas.create_idea(ana, title="Aberta")

    item = next(i for i in menu_items(ana, "curation:story_ideas") if i.key == "ideas")
    assert item.count == 1
    assert item.active


def test_retencao_mantem_noticia_de_pauta(ana, item):
    ideas.create_idea(ana, title="Horta")
    idea = StoryIdea.objects.get()
    idea.item = item
    idea.save()
    NewsItem.objects.filter(pk=item.pk).update(fetched_at=timezone.now() - timedelta(days=61))

    assert services.purge_old_items() == 0


def test_exportacao_inclui_pautas(ana):
    ideas.create_idea(ana, title="Horta", notes="Falar com a merenda")

    data = json.loads(privacy.export_json(ana))

    assert data["pautas"][0]["titulo"] == "Horta"
    assert data["pautas"][0]["proposta_por_mim"] is True
