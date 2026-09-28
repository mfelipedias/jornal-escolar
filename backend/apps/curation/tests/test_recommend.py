"""Sugestões de notícias por professor e tela de sugestões (E48; docs/21, "Recomendação").

Aceite: ignorar reduz as sugestões do tópico.
"""

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts import privacy
from apps.accounts.services import ensure_profile, save_profile
from apps.curation import recommend, selectors, services, tasks
from apps.curation.models import NewsItem, NewsItemClassification, NewsRecommendation
from apps.dashboard.menu import menu_items
from apps.editorial.models import Notification
from apps.taxonomy.models import Topic
from tests.factories import DisciplineFactory, UserFactory

pytestmark = pytest.mark.django_db

Status = NewsRecommendation.Status
Method = NewsItemClassification.Method
HX = {"HTTP_HX_REQUEST": "true"}
PAGE = "/painel/sugestoes/"


@pytest.fixture
def robotica():
    return Topic.objects.create(name="Robótica", keywords=["robô"])


@pytest.fixture
def cinema():
    return Topic.objects.create(name="Cinema", keywords=["filme"])


@pytest.fixture
def teacher(robotica):
    user = UserFactory(full_name="Ana Lima")
    ensure_profile(user).topics.set([robotica])
    return user


@pytest.fixture
def news(make_source):
    """Notícia já classificada: news(topics={topic: score}, disciplines=..., days=idade)."""
    sources = {}
    counter = iter(range(1, 10_000))

    def make(
        topics=None,
        disciplines=None,
        days: float = 0,
        trust: int = 5,
        language: str = "pt",
        title: str = "",
        **fields,
    ) -> NewsItem:
        key = (trust, language)
        if key not in sources:
            sources[key] = make_source(
                f"https://fonte-{trust}-{language}.exemplo.org/feed",
                name=f"Fonte {trust} {language}",
                trust_level=trust,
                language=language,
            )
        n = next(counter)
        now = timezone.now()
        item = NewsItem.objects.create(
            source=sources[key],
            title=title or f"Notícia {n}",
            url=f"https://noticia.exemplo.org/{n}",
            canonical_url=f"https://noticia.exemplo.org/{n}",
            url_hash=f"{n:064d}",
            title_hash=f"{n:064x}",
            published_at=now - timedelta(days=days),
            fetched_at=fields.pop("fetched_at", now),
            language=language,
            **fields,
        )
        for topic, score in (topics or {}).items():
            NewsItemClassification.objects.create(
                item=item, topic=topic, score=score, method=Method.KEYWORD
            )
        for discipline, score in (disciplines or {}).items():
            NewsItemClassification.objects.create(
                item=item, discipline=discipline, score=score, method=Method.SOURCE_DEFAULT
            )
        return item

    return make


def suggested(user) -> list[NewsItem]:
    return [
        rec.item
        for rec in NewsRecommendation.objects.filter(user=user, status=Status.SUGGESTED)
        .select_related("item")
        .order_by("item_id")
    ]


def score_of(user, item) -> float:
    interests = recommend.interests_for(user)
    [feat] = recommend.features([item])
    return recommend.score(interests, feat, timezone.now())


# --- fórmula ---


def test_formula_do_docs_21(teacher, robotica, news):
    fisica = DisciplineFactory(name="Física")
    ensure_profile(teacher).disciplines.set([fisica])

    hoje = news({robotica: 0.9}, {fisica: 0.4})
    assert score_of(teacher, hoje) == pytest.approx(0.5 * 0.9 + 0.2 + 0.2 + 0.1)

    semana = news({robotica: 0.5}, days=7, trust=3)
    assert score_of(teacher, semana) == pytest.approx(0.25 + 0.1 + 0.06, abs=0.002)

    velha = news({robotica: 0.5}, days=20)
    assert score_of(teacher, velha) == pytest.approx(0.25 + 0.1)

    # Disciplina com score abaixo de 0,4 (palavra só no resumo) não conta.
    fraca = news(disciplines={fisica: 0.3})
    assert score_of(teacher, fraca) == pytest.approx(0.2 + 0.1)


def test_sugere_a_partir_de_0_45_e_nao_sugere_abaixo(teacher, robotica, cinema, news):
    boa = news({robotica: 0.5})  # 0,25 + 0,2 + 0,1 = 0,55
    fora_do_perfil = news({cinema: 0.9})  # 0,3
    antiga = news({robotica: 0.5}, days=10)  # 0,25 + 0,057 + 0,1 = 0,41

    created = recommend.recommend_for_user(teacher)

    assert created == 1
    assert suggested(teacher) == [boa]
    assert not NewsRecommendation.objects.filter(item__in=[fora_do_perfil, antiga]).exists()


def test_quem_nao_tem_interesses_nao_recebe_nada(robotica, news):
    user = UserFactory()
    ensure_profile(user)
    news({robotica: 0.9})

    assert recommend.recommend_for_user(user) == 0
    assert recommend.recipients() == []


def test_ingles_so_para_quem_aceita(teacher, robotica, news):
    item = news({robotica: 0.9}, language="en")
    profile = teacher.profile
    profile.accepts_english = False
    profile.save()

    recommend.recommend_for_user(teacher)
    assert suggested(teacher) == []

    profile.accepts_english = True
    profile.save()
    recommend.recommend_for_user(teacher)
    assert suggested(teacher) == [item]


def test_fontes_de_menor_confianca_so_para_quem_pede(teacher, robotica, news):
    item = news({robotica: 0.9}, trust=2)

    recommend.recommend_for_user(teacher)
    assert suggested(teacher) == []

    profile = teacher.profile
    profile.include_low_trust = True
    profile.save()
    recommend.recommend_for_user(teacher)
    assert suggested(teacher) == [item]


def test_noticias_ocultas_nao_sao_sugeridas(teacher, robotica, news):
    news({robotica: 0.9}, is_hidden=True)

    assert recommend.recommend_for_user(teacher) == 0


def test_ignorar_tres_do_mesmo_topico_reduz_sugestoes_do_topico(teacher, robotica, news):
    """Aceite da E48."""
    first = [news({robotica: 0.5}) for _ in range(3)]
    recommend.recommend_for_user(teacher)
    novo = news({robotica: 0.5})
    before = score_of(teacher, novo)

    for item in first:
        rec = NewsRecommendation.objects.get(user=teacher, item=item)
        recommend.act(teacher, rec, "ignorar")

    assert score_of(teacher, novo) == pytest.approx(before - 0.3)
    recommend.recommend_for_user(teacher)
    assert novo not in suggested(teacher)


def test_duas_ignoradas_ainda_nao_penalizam(teacher, robotica, news):
    items = [news({robotica: 0.5}) for _ in range(2)]
    recommend.recommend_for_user(teacher)
    novo = news({robotica: 0.5})
    before = score_of(teacher, novo)

    for item in items:
        recommend.act(teacher, NewsRecommendation.objects.get(item=item), "ignorar")

    assert score_of(teacher, novo) == before


def test_interessante_aumenta_peso_do_topico_e_da_fonte(teacher, robotica, cinema, news):
    fisica = DisciplineFactory(name="Física")
    ensure_profile(teacher).disciplines.set([fisica])
    marcada = news({robotica: 0.5, cinema: 0.9}, {fisica: 0.4})
    recommend.recommend_for_user(teacher)
    outra = news({cinema: 0.9}, {fisica: 0.4}, trust=4)
    mesma_fonte = news({cinema: 0.5}, {fisica: 0.4})
    before = score_of(teacher, outra), score_of(teacher, mesma_fonte)

    rec = NewsRecommendation.objects.get(item=marcada)
    recommend.act(teacher, rec, "interessante")

    assert score_of(teacher, outra) == pytest.approx(before[0] + 0.1)
    assert score_of(teacher, mesma_fonte) == pytest.approx(before[1] + 0.1 + 0.05)


def test_no_maximo_30_ativas_e_as_mais_antigas_expiram_em_silencio(teacher, robotica, news):
    items = [news({robotica: 0.9}, days=i * 0.1) for i in range(32)]

    recommend.recommend_for_user(teacher)

    assert len(suggested(teacher)) == 30
    expired = NewsRecommendation.objects.filter(user=teacher, status=Status.IGNORED)
    assert {rec.item for rec in expired} == set(items[-2:])
    assert all(rec.acted_at is None for rec in expired)
    # Expirar não é ignorar: nem aba Ignoradas, nem penalidade.
    assert selectors.tab_counts(teacher, selectors.Filters())["ignoradas"] == 0
    assert recommend.interests_for(teacher).ignored_topics == set()


def test_sugestao_de_noticia_com_mais_de_14_dias_expira(teacher, robotica, news):
    item = news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    NewsItem.objects.filter(pk=item.pk).update(published_at=timezone.now() - timedelta(days=15))

    assert recommend.expire(teacher) == 1
    assert suggested(teacher) == []


def test_mudar_o_perfil_refaz_so_as_sugestoes_nao_mexidas(teacher, robotica, cinema, news):
    salva = news({robotica: 0.9})
    solta = news({robotica: 0.9})
    filme = news({cinema: 0.9})
    recommend.recommend_for_user(teacher)
    recommend.act(teacher, NewsRecommendation.objects.get(item=salva), "salvar")

    save_profile(teacher, topics=[cinema])

    assert suggested(teacher) == [filme]
    assert not NewsRecommendation.objects.filter(item=solta).exists()
    assert NewsRecommendation.objects.get(item=salva).status == Status.SAVED


def test_coleta_gera_sugestoes_das_noticias_novas(web, make_source, teacher, robotica):
    robotica.keywords = ["Arduino", "sensor"]
    robotica.save()
    source = make_source("https://ciencia.exemplo.org/feed/")
    from .conftest import feed

    web.add(source.feed_url, feed("rss_basico.xml"))

    result = services.fetch_source(source)

    assert result.new == 2
    [item] = suggested(teacher)
    assert item.title.startswith("Pesquisadores criam sensor")


def test_reclassificar_recalcula_sugestoes(teacher, robotica, make_source):
    source = make_source()
    item = NewsItem.objects.create(
        source=source,
        title="Robô entrega merenda no pátio",
        url="https://x.exemplo.org/1",
        canonical_url="https://x.exemplo.org/1",
        url_hash="1" * 64,
        title_hash="1" * 64,
        published_at=timezone.now(),
        fetched_at=timezone.now(),
        language="pt",
    )
    assert suggested(teacher) == []

    call_command("classify_news", stdout=StringIO())

    assert suggested(teacher) == [item]


def test_retencao_mantem_as_salvas_interessantes_e_pautas(teacher, robotica, news):
    old = timezone.now() - timedelta(days=61)
    salva, interessante, ignorada, solta = (news({robotica: 0.9}, fetched_at=old) for _ in range(4))
    for item, status in (
        (salva, Status.SAVED),
        (interessante, Status.INTERESTING),
        (ignorada, Status.IGNORED),
    ):
        NewsRecommendation.objects.create(user=teacher, item=item, score=0.9, status=status)

    assert services.purge_old_items() == 2
    assert set(NewsItem.objects.all()) == {salva, interessante}
    assert solta.pk not in NewsItem.objects.values_list("pk", flat=True)


# --- tela ---


@pytest.fixture
def logged(client, teacher):
    client.force_login(teacher)
    return client


def test_tela_exige_login(client):
    response = client.get(PAGE)
    assert response.status_code == 302
    assert "/entrar/" in response.url


def test_tela_lista_sugestoes_com_card_completo(logged, teacher, robotica, news):
    fisica = DisciplineFactory(name="Física")
    item = news(
        {robotica: 0.9},
        {fisica: 0.9},
        title="Robô entrega merenda",
        summary="Resumo do feed.",
    )
    news({robotica: 0.3}, title="Fraco")  # tópico abaixo de 0,5 não vira etiqueta
    recommend.recommend_for_user(teacher)

    html = logged.get(PAGE).content.decode()

    assert "Robô entrega merenda" in html
    assert item.canonical_url in html
    assert 'rel="noopener noreferrer"' in html
    assert "Resumo do feed." in html
    assert "Robótica" in html
    assert "Física" in html
    assert "Confiança 5 de 5" in html
    assert "As notícias pertencem às fontes" in html


def test_acao_htmx_troca_o_card(logged, teacher, robotica, news):
    item = news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    rec = NewsRecommendation.objects.get(item=item)
    url = reverse("curation:suggestion_action", args=[rec.pk, "salvar"])

    response = logged.post(url, {"next": PAGE}, **HX)

    assert response.status_code == 200
    html = response.content.decode()
    assert f'id="sugestao-{rec.pk}"' in html
    assert "Salva. Está na aba Salvas." in html
    assert "Tirar das salvas" in html
    rec.refresh_from_db()
    assert rec.status == Status.SAVED
    assert rec.acted_at is not None


def test_acao_sem_javascript_volta_para_a_tela(logged, teacher, robotica, news):
    item = news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    rec = NewsRecommendation.objects.get(item=item)

    response = logged.post(
        reverse("curation:suggestion_action", args=[rec.pk, "ignorar"]),
        {"next": f"{PAGE}?aba=para-voce"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == f"{PAGE}?aba=para-voce"
    assert "Ignorada." in response.content.decode()
    ignored = logged.get(PAGE, {"aba": "ignoradas"}).content.decode()
    assert "Voltar para sugestões" in ignored


def test_nao_age_na_sugestao_de_outra_pessoa(client, teacher, robotica, news):
    item = news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    rec = NewsRecommendation.objects.get(item=item)
    client.force_login(UserFactory())

    response = client.post(reverse("curation:suggestion_action", args=[rec.pk, "salvar"]))

    assert response.status_code == 404
    rec.refresh_from_db()
    assert rec.status == Status.SUGGESTED


def test_acao_desconhecida_e_404(logged, teacher, robotica, news):
    item = news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    rec = NewsRecommendation.objects.get(item=item)

    response = logged.post(reverse("curation:suggestion_action", args=[rec.pk, "apagar"]))

    assert response.status_code == 404


def test_filtros_por_topico_fonte_e_idioma(logged, teacher, robotica, cinema, news):
    ensure_profile(teacher).topics.add(cinema)
    robo = news({robotica: 0.9}, title="Robô no pátio")
    filme = news({cinema: 0.9}, title="Filme na escola", language="en", trust=4)
    recommend.recommend_for_user(teacher)

    def titles(**params) -> set[str]:
        html = logged.get(PAGE, params).content.decode()
        return {t for t in ("Robô no pátio", "Filme na escola") if t in html}

    assert titles() == {"Robô no pátio", "Filme na escola"}
    assert titles(topico=robotica.slug) == {"Robô no pátio"}
    assert titles(fonte=filme.source_id) == {"Filme na escola"}
    assert titles(idioma="pt") == {"Robô no pátio"}
    assert titles(idioma="xx", fonte="abc", topico="nao-existe") == {
        "Robô no pátio",
        "Filme na escola",
    }
    assert robo.source_id != filme.source_id


def test_estado_vazio_pede_para_preencher_o_perfil(client):
    user = UserFactory()
    ensure_profile(user)
    client.force_login(user)

    html = client.get(PAGE).content.decode()

    assert "Marque disciplinas e tópicos no seu perfil" in html


def test_menu_com_contador_e_bloco_no_inicio(logged, teacher, robotica, news):
    news({robotica: 0.9}, title="Robô joga xadrez")
    recommend.recommend_for_user(teacher)

    item = next(i for i in menu_items(teacher, "curation:suggestions") if i.key == "suggestions")
    assert item.count == 1
    assert item.active

    html = logged.get(reverse("dashboard:home")).content.decode()
    assert "Sugestões para você" in html
    assert "Robô joga xadrez" in html


def test_editor_ve_quantos_colegas_acharam_interessante(client, robotica, news):
    item = news({robotica: 0.9})
    editor = UserFactory(editor=True)
    ensure_profile(editor).topics.set([robotica])
    colegas = [UserFactory() for _ in range(2)]
    for colega in colegas:
        ensure_profile(colega).topics.set([robotica])
    recommend.recommend_items()
    for colega in colegas:
        rec = NewsRecommendation.objects.get(user=colega, item=item)
        recommend.act(colega, rec, "interessante")
    client.force_login(editor)

    html = client.get(PAGE).content.decode()

    assert "2 colegas" in html


# --- aviso semanal, privacidade ---


def test_aviso_semanal_de_sugestoes_novas(teacher, robotica, news):
    for _ in range(3):
        news({robotica: 0.9})
    recommend.recommend_for_user(teacher)

    assert tasks.notify_new_suggestions(timestamp=0) == 1
    [aviso] = Notification.objects.filter(user=teacher)
    assert aviso.message == "3 sugestões novas de pauta para você"
    assert aviso.url == PAGE

    tasks.notify_new_suggestions(timestamp=0)  # não repete enquanto não for lido
    assert Notification.objects.filter(user=teacher).count() == 1


def test_exportar_e_anonimizar(teacher, robotica, news, admin_user):
    item = news({robotica: 0.9}, title="Robô joga xadrez")
    news({robotica: 0.9})
    recommend.recommend_for_user(teacher)
    recommend.act(teacher, NewsRecommendation.objects.get(item=item), "salvar")

    data = json.loads(privacy.export_json(teacher))
    assert [row["noticia"] for row in data["sugestoes_de_pauta"]] == ["Robô joga xadrez"]
    assert data["perfil"]["inclui_fontes_de_menor_confianca"] is False

    privacy.anonymize_user(admin_user, teacher)
    assert not NewsRecommendation.objects.filter(user=teacher).exists()
