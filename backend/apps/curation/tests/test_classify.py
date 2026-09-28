"""Classificação por fonte e palavras-chave (E47; docs/21, "Classificação")."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from procrastinate.contrib.django import app
from procrastinate.testing import InMemoryConnector

from apps.curation import classify, tasks
from apps.curation.models import NewsItem, NewsItemClassification
from apps.taxonomy.models import Topic
from tests.factories import DisciplineFactory

from .conftest import feed

Method = NewsItemClassification.Method
FEED = "https://ciencia.exemplo.org/feed/"


@pytest.fixture
def make_item(make_source):
    counter = iter(range(1, 10_000))

    def make(title: str, summary: str = "", source=None, **fields) -> NewsItem:
        n = next(counter)
        now = timezone.now()
        return NewsItem.objects.create(
            source=source or make_source(f"https://fonte{n}.exemplo.org/feed"),
            title=title,
            summary=summary,
            url=f"https://noticia.exemplo.org/{n}",
            canonical_url=f"https://noticia.exemplo.org/{n}",
            url_hash=f"{n:064d}",
            title_hash=f"{n:064x}",
            published_at=now,
            fetched_at=fields.pop("fetched_at", now),
            language="pt",
            **fields,
        )

    return make


def topic(name: str, keywords: list[str], disciplines=(), **fields) -> Topic:
    created = Topic.objects.create(name=name, keywords=keywords, **fields)
    created.disciplines.set(disciplines)
    return created


def scores(item: NewsItem) -> dict[str, tuple[float, str]]:
    return {
        str(c.topic or c.discipline): (c.score, c.method)
        for c in NewsItemClassification.objects.filter(item=item)
    }


@pytest.mark.parametrize(
    ("points", "expected"),
    [(0, 0.0), (1, 0.3), (2, 0.5), (3, 0.7), (4, 0.9), (9, 0.9)],
)
def test_score_de_palavra_chave_vai_de_0_3_a_0_9(points, expected):
    assert classify.keyword_score(points) == expected


@pytest.mark.django_db
def test_titulo_vale_2_resumo_vale_1_sem_acento_e_sem_maiusculas(make_item):
    robotica = topic("Robótica", ["robótica", "Arduino"])
    energia = topic("Energia", ["energia solar"])
    item = make_item(
        "ROBOTICA na escola: alunos montam carrinho",
        "Projeto usa arduino e placas de Energia  Solar.",
    )

    classify.Classifier().save(item)

    assert scores(item) == {
        "Robótica": (0.7, Method.KEYWORD),  # título (2) + resumo (1)
        "Energia": (0.3, Method.KEYWORD),  # só no resumo (1)
    }
    row = NewsItemClassification.objects.get(item=item, topic=robotica)
    assert row.matched == "robótica, Arduino"
    assert not NewsItemClassification.objects.filter(topic=energia, score__gte=0.5).exists()


@pytest.mark.django_db
def test_palavra_inteira_nao_casa_dentro_de_outra(make_item):
    topic("Arte", ["arte"])
    item = make_item("Sete partes do corpo humano explicadas", "A artéria leva sangue.")

    classify.Classifier().save(item)

    assert scores(item) == {}


@pytest.mark.django_db
def test_sigla_em_maiusculas_so_casa_em_maiusculas(make_item):
    topic("Inteligência Artificial", ["IA", "inteligência artificial"])
    topic("Saúde", ["SUS"])
    comum = make_item("Ele ia para a escola e disse sus", "Oba, que dia.")
    sigla = make_item("Escolas testam IA para corrigir redações", "Atendimento do SUS.")

    classifier = classify.Classifier()
    classifier.save(comum)
    classifier.save(sigla)

    assert scores(comum) == {}
    assert scores(sigla) == {
        "Inteligência Artificial": (0.5, Method.KEYWORD),
        "Saúde": (0.3, Method.KEYWORD),
    }


@pytest.mark.django_db
def test_padrao_da_fonte_e_disciplinas_derivadas_dos_topicos(make_source, make_item):
    fisica = DisciplineFactory(name="Física")
    geografia = DisciplineFactory(name="Geografia")
    arte = DisciplineFactory(name="Arte")
    ciencia = topic("Divulgação científica", [])
    topic("Astronomia", ["telescópio", "planeta"], disciplines=[fisica, geografia])
    source = make_source()
    source.default_topics.set([ciencia])
    source.default_disciplines.set([fisica, arte])
    item = make_item("Telescópio acha planeta parecido com a Terra", source=source)

    classify.Classifier().save(item)

    assert scores(item) == {
        "Divulgação científica": (0.4, Method.SOURCE_DEFAULT),
        "Astronomia": (0.9, Method.KEYWORD),
        "Física": (0.9, Method.KEYWORD),  # o maior entre o padrão (0,4) e o tópico
        "Geografia": (0.9, Method.KEYWORD),
        "Arte": (0.4, Method.SOURCE_DEFAULT),
    }


@pytest.mark.django_db
def test_topicos_inativos_e_disciplinas_inativas_ficam_de_fora(make_item):
    inativa = DisciplineFactory(name="Antiga", is_active=False)
    topic("Sugerido", ["robô"], is_active=False)
    topic("Robótica", ["robô"], disciplines=[inativa])
    item = make_item("Robô entrega merenda no pátio da escola")

    classify.Classifier().save(item)

    assert scores(item) == {"Robótica": (0.5, Method.KEYWORD)}


@pytest.mark.django_db
def test_classificar_de_novo_troca_automaticas_e_mantem_manuais(make_item):
    robotica = topic("Robótica", ["robô"])
    manual = topic("Esportes", [])
    item = make_item("Robô joga futebol em campeonato")
    NewsItemClassification.objects.create(item=item, topic=manual, score=1.0, method=Method.MANUAL)
    classify.Classifier().save(item)

    robotica.keywords = ["futebol", "campeonato"]
    robotica.save()
    classify.Classifier().save(item)

    assert scores(item) == {
        "Robótica": (0.9, Method.KEYWORD),
        "Esportes": (1.0, Method.MANUAL),
    }


@pytest.mark.django_db
def test_coleta_classifica_as_noticias_novas(web, make_source):
    topic("Robótica", ["Arduino", "sensor"])
    topic("Astronomia", ["eclipse", "lua"])
    web.add(FEED, feed("rss_basico.xml"))
    make_source(FEED)

    call_command("fetch_news", stdout=StringIO())

    sensor = NewsItem.objects.get(title__startswith="Pesquisadores")
    eclipse = NewsItem.objects.get(title__startswith="Eclipse")
    # "sensor" no título e no resumo (3) e "Arduino" no resumo (1)
    assert scores(sensor) == {"Robótica": (0.9, Method.KEYWORD)}
    assert scores(eclipse) == {"Astronomia": (0.9, Method.KEYWORD)}


@pytest.mark.django_db
def test_comando_classify_news_reclassifica(make_item):
    item = make_item("Robô entrega merenda no pátio")
    velha = make_item("Robô antigo", fetched_at=timezone.now() - timedelta(days=10))
    topic("Robótica", ["robô"])
    out = StringIO()

    call_command("classify_news", "--dias", "3", stdout=out)

    assert "1 notícia(s) classificada(s); 1 com tópico ou disciplina." in out.getvalue()
    assert scores(item) == {"Robótica": (0.5, Method.KEYWORD)}
    assert scores(velha) == {}


@pytest.fixture
def in_memory():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


def queued(connector: InMemoryConnector) -> list[str]:
    return [job["task_name"] for job in connector.jobs.values()]


@pytest.mark.django_db
def test_mudar_palavras_chave_no_admin_pede_reclassificacao(
    admin_client, in_memory, django_capture_on_commit_callbacks
):
    robotica = topic("Robótica", ["robô"])
    url = reverse("admin:taxonomy_topic_change", args=[robotica.pk])
    data = {"name": "Robótica", "slug": "robotica", "is_active": "on", "keywords": "robô"}

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(url, data)
    assert queued(in_memory) == []  # nada mudou

    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(url, {**data, "keywords": "robô, Arduino"}, follow=True)
        admin_client.post(url, {**data, "keywords": "robô, Arduino, sensor"})

    assert queued(in_memory) == ["reclassify_news"]  # duas mudanças, uma tarefa
    assert "classificadas de novo" in response.content.decode()


@pytest.mark.django_db
def test_mudar_padroes_da_fonte_no_admin_pede_reclassificacao(
    admin_client, in_memory, make_source, django_capture_on_commit_callbacks
):
    source = make_source()
    ciencia = topic("Ciência", [])
    url = reverse("admin:curation_newssource_change", args=[source.pk])
    data = {
        "name": source.name,
        "feed_url": source.feed_url,
        "kind": "rss",
        "language": "pt",
        "trust_level": 3,
        "is_active": "on",
        "fetch_interval_minutes": 120,
        "default_topics": [ciencia.pk],
    }

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(url, data)

    assert queued(in_memory) == ["reclassify_news"]


@pytest.mark.django_db
def test_tarefa_reclassify_news(make_item):
    item = make_item("Robô entrega merenda")
    topic("Robótica", ["robô"])

    result = tasks.reclassify_news()

    assert result == "1 notícia(s) reclassificada(s), 1 com tópico ou disciplina"
    assert scores(item) == {"Robótica": (0.5, Method.KEYWORD)}


@pytest.mark.django_db
def test_admin_da_noticia_mostra_classificacao_e_filtra_por_topico(admin_client, make_item):
    robotica = topic("Robótica", ["robô"])
    com = make_item("Robô entrega merenda no pátio")
    sem = make_item("Feira de livros começa amanhã")
    classify.classify_items([com, sem])

    page = admin_client.get(reverse("admin:curation_newsitem_change", args=[com.pk]))
    assert "Palavra-chave" in page.content.decode()

    listing = admin_client.get(
        reverse("admin:curation_newsitem_changelist"), {"topico": robotica.pk}
    ).content.decode()
    assert com.title in listing
    assert sem.title not in listing

    listing = admin_client.get(
        reverse("admin:curation_newsitem_changelist"), {"topico": "nenhum"}
    ).content.decode()
    assert sem.title in listing
    assert com.title not in listing
