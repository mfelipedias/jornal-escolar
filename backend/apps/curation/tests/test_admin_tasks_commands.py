"""Admin ("Buscar agora"), tarefas do worker e comandos da curadoria (E45)."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from procrastinate.contrib.django import app
from procrastinate.testing import InMemoryConnector

from apps.curation import tasks
from apps.curation.models import NewsItem, NewsSource
from apps.curation.seed_data import SOURCES

from .conftest import feed

FEED = "https://ciencia.exemplo.org/feed/"


@pytest.mark.django_db
def test_acao_buscar_agora_mostra_resultado(admin_client, web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    good = make_source()
    bad = make_source("https://quebrada.exemplo.org/feed", name="Quebrada")

    response = admin_client.post(
        reverse("admin:curation_newssource_changelist"),
        {"action": "fetch_now", "_selected_action": [good.pk, bad.pk]},
        follow=True,
    )

    text = response.content.decode()
    assert "Ciência Exemplo: 2 nova(s), 0 já conhecida(s)" in text
    assert "Quebrada: erro — O site respondeu com o código 404." in text
    assert NewsItem.objects.count() == 2


@pytest.mark.django_db
def test_botao_buscar_agora_na_pagina_da_fonte(admin_client, web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    source = make_source()
    change_url = reverse("admin:curation_newssource_change", args=[source.pk])

    page = admin_client.get(change_url)
    fetch_url = reverse("admin:curation_newssource_fetch", args=[source.pk])
    assert fetch_url in page.content.decode()
    assert admin_client.get(fetch_url).status_code == 405

    response = admin_client.post(fetch_url, follow=True)

    assert response.redirect_chain[-1][0] == change_url
    assert "2 nova(s)" in response.content.decode()


@pytest.mark.django_db
def test_botao_exige_admin(client, staff_user, make_source):
    source = make_source()
    client.force_login(staff_user)

    response = client.post(reverse("admin:curation_newssource_fetch", args=[source.pk]))

    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.django_db
def test_listas_do_admin_abrem_e_itens_sao_so_leitura(admin_client, web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    make_source()
    call_command("fetch_news", stdout=StringIO())
    item = NewsItem.objects.first()

    assert admin_client.get(reverse("admin:curation_newssource_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:curation_newsitem_changelist")).status_code == 200
    detail = admin_client.get(reverse("admin:curation_newsitem_change", args=[item.pk]))
    assert detail.status_code == 200
    assert 'name="title"' not in detail.content.decode()

    admin_client.post(
        reverse("admin:curation_newsitem_changelist"),
        {"action": "hide", "_selected_action": [item.pk]},
    )
    item.refresh_from_db()
    assert item.is_hidden


@pytest.mark.django_db
def test_admin_marca_fonte_em_alerta(admin_client, make_source):
    make_source(consecutive_failures=5)

    response = admin_client.get(
        reverse("admin:curation_newssource_changelist"), {"situacao": "alerta"}
    )

    assert "5 falhas seguidas" in response.content.decode()


@pytest.mark.django_db
def test_seed_cria_fontes_uma_vez():
    out = StringIO()
    call_command("seed_news_sources", stdout=out)
    call_command("seed_news_sources", stdout=out)

    assert NewsSource.objects.count() == len(SOURCES) >= 5
    assert f"0 criadas, {len(SOURCES)} já existiam" in out.getvalue()
    assert NewsSource.objects.filter(language="en").exists()
    assert not any("rosa" in source["name"].lower() for source in SOURCES)


@pytest.mark.django_db
def test_comando_fetch_news(web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    source = make_source()
    make_source("https://desligada.org/feed", name="Desligada", is_active=False)
    out = StringIO()

    call_command("fetch_news", "--fonte", str(source.pk), stdout=out)

    assert "1 fonte(s), 2 notícia(s) nova(s), 0 com erro." in out.getvalue()
    assert web.gets() == [FEED]


# --- worker ---


@pytest.mark.django_db
def test_tarefa_de_fonte_chama_a_coleta(web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    source = make_source()

    assert tasks.fetch_news_source(source_id=source.pk).startswith("Ciência Exemplo: 2 nova(s)")
    assert tasks.fetch_news_source(source_id=999999) == "fonte inexistente ou desativada"


def test_agendador_roda_a_cada_meia_hora():
    crons = {name: task.cron for (name, _), task in app.periodic_registry.periodic_tasks.items()}
    assert crons["fetch_news"] == "5,35 * * * *"


@pytest.fixture
def in_memory():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


@pytest.mark.django_db
def test_agendador_enfileira_uma_tarefa_por_fonte_vencida(in_memory, make_source):
    from django.utils import timezone

    due = make_source("https://a.org/feed", name="A")
    make_source("https://b.org/feed", name="B", last_fetched_at=timezone.now())

    assert tasks.fetch_news(timestamp=0) == 1
    assert tasks.fetch_news(timestamp=0) == 0  # já está na fila: não empilha

    jobs = list(in_memory.jobs.values())
    assert [(job["task_name"], job["args"]) for job in jobs] == [
        ("fetch_news_source", {"source_id": due.pk})
    ]
