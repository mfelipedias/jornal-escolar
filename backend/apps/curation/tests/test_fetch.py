"""Coleta de uma fonte (docs/21, "Pipeline de coleta" e "Higiene"), sem rede."""

import socket
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from django.utils import timezone

from apps.curation import services
from apps.curation.models import NewsItem

from .conftest import feed

FEED = "https://ciencia.exemplo.org/feed/"


@pytest.mark.django_db
def test_coleta_rss_normaliza_e_grava_so_metadados(web, make_source):
    web.add(FEED, feed("rss_basico.xml"), content_type="application/rss+xml", etag='"v1"')
    source = make_source()

    result = services.fetch_source(source)

    assert result.ok
    assert (result.new, result.known, result.skipped) == (2, 0, 1)
    sensor = NewsItem.objects.get(title__startswith="Pesquisadores")
    assert sensor.title == "Pesquisadores criam sensor de baixo custo para medir o ar"
    assert sensor.url.startswith("https://ciencia.exemplo.org/sensor-ar/?utm_source=rss")
    assert sensor.canonical_url == "https://ciencia.exemplo.org/sensor-ar/"
    assert (
        sensor.summary
        == "Um sensor feito com Arduino mede partículas. O projeto começou numa escola."
    )
    assert sensor.image_url == "https://ciencia.exemplo.org/img/sensor.jpg"
    assert sensor.published_at == datetime(2026, 9, 17, 13, 30, tzinfo=UTC)
    assert sensor.language == "pt"
    assert len(sensor.url_hash) == len(sensor.title_hash) == 64

    eclipse = NewsItem.objects.get(title__startswith="Eclipse")
    assert eclipse.title == "Eclipse & lua: o que ver no céu em outubro"
    assert eclipse.summary == "Guia do céu."
    assert eclipse.published_at == source.last_fetched_at  # sem data no feed

    source.refresh_from_db()
    assert source.last_success_at is not None
    assert source.etag == '"v1"'
    assert source.consecutive_failures == 0


@pytest.mark.django_db
def test_coleta_atom_em_ingles(web, make_source):
    web.add("https://tech.example.com/feed", feed("atom.xml"))
    source = make_source("https://tech.example.com/feed", name="Tech Example", language="en")

    assert services.fetch_source(source).new == 1
    item = NewsItem.objects.get()
    assert item.title == "Robots learn to sort recycling"
    assert item.summary == "Machine learning helps."
    assert item.image_url == "https://tech.example.com/robots.png"
    assert item.language == "en"


@pytest.mark.django_db
def test_coleta_feed_em_latin1(web, make_source):
    web.add("https://educa.exemplo.org/rss", feed("latin1.xml"), content_type="text/xml")
    source = make_source("https://educa.exemplo.org/rss", name="Educação")

    assert services.fetch_source(source).new == 1
    item = NewsItem.objects.get()
    assert item.title == "Matrículas abertas para o ensino médio"
    assert item.summary == "Inscrições vão até sexta."


@pytest.mark.django_db
def test_coletar_de_novo_nao_duplica_nem_repete_head(web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    source = make_source()
    services.fetch_source(source)
    heads = len(web.heads())

    again = services.fetch_source(source)

    assert (again.new, again.known) == (0, 2)
    assert NewsItem.objects.count() == 2
    assert len(web.heads()) == heads


@pytest.mark.django_db
def test_link_que_redireciona_guarda_o_endereco_final(web, make_source):
    body = feed("atom.xml").replace(b'https://tech.example.com/robots"', b'https://t.co/abc"')
    web.add("https://tech.example.com/feed", body)
    web.redirect("https://t.co/abc", "https://tech.example.com/robots?utm_source=twitter")
    web.add("https://tech.example.com/robots?utm_source=twitter")
    source = make_source("https://tech.example.com/feed", name="Tech")

    services.fetch_source(source)

    item = NewsItem.objects.get()
    assert item.url == "https://t.co/abc"
    assert item.canonical_url == "https://tech.example.com/robots"


@pytest.mark.django_db
def test_mesma_url_em_duas_fontes_gera_um_item(web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    web.add("https://espelho.exemplo.org/feed", feed("rss_basico.xml"))
    first = make_source()
    second = make_source("https://espelho.exemplo.org/feed", name="Espelho")

    services.fetch_source(first)
    result = services.fetch_source(second)

    assert result.new == 0
    assert NewsItem.objects.count() == 2


@pytest.mark.django_db
def test_envia_etag_e_304_nao_e_erro(web, make_source):
    source = make_source(etag='"v1"', last_modified="Wed, 16 Sep 2026 10:00:00 GMT")
    web.add(FEED, status=304)

    result = services.fetch_source(source)

    assert result.ok
    assert result.not_modified
    request = web.requests[0]
    assert request.headers["If-None-Match"] == '"v1"'
    assert request.headers["If-Modified-Since"] == "Wed, 16 Sep 2026 10:00:00 GMT"
    assert "JornalEscolar/" in request.headers["User-Agent"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("setup", "message"),
    [
        (lambda web: web.add(FEED, status=500), "código 500"),
        (lambda web: web.add(FEED, b"<html><body>Nada aqui</body></html>"), "não é um feed"),
        (lambda web: web.add(FEED, b"<rss><channel><title>x"), "não é um feed"),
        (lambda web: None, "código 404"),
    ],
)
def test_falhas_ficam_registradas_na_fonte(web, make_source, setup, message):
    setup(web)
    source = make_source(consecutive_failures=4)

    result = services.fetch_source(source)

    assert not result.ok
    assert message in result.error
    source.refresh_from_db()
    assert message in source.last_error
    assert source.consecutive_failures == 5
    assert source.needs_attention
    assert source.last_error_at is not None
    assert source.is_active  # não desativa sozinha


@pytest.mark.django_db
def test_timeout_nao_derruba_as_outras_fontes(web, make_source):
    def slow(request):
        raise httpx.ReadTimeout("lento", request=request)

    web.routes["https://lenta.exemplo.org/feed"] = slow
    web.add(FEED, feed("rss_basico.xml"))
    slow_source = make_source("https://lenta.exemplo.org/feed", name="Lenta")
    good_source = make_source()

    results = services.fetch_sources([slow_source, good_source])

    assert results[0].error == "Tempo esgotado ao buscar o feed."
    assert results[1].ok
    assert results[1].new == 2


@pytest.mark.django_db
def test_sucesso_zera_falhas(web, make_source):
    web.add(FEED, feed("rss_basico.xml"))
    source = make_source(consecutive_failures=7, last_error="antigo")

    services.fetch_source(source)

    source.refresh_from_db()
    assert source.consecutive_failures == 0
    assert source.last_error == ""


@pytest.mark.django_db
def test_feed_grande_demais(web, make_source, monkeypatch):
    monkeypatch.setattr(services, "MAX_FEED_BYTES", 100)
    web.add(FEED, feed("rss_basico.xml"))

    result = services.fetch_source(make_source())

    assert "5 MB" in result.error


@pytest.mark.django_db
def test_recusa_endereco_de_rede_interna(web, make_source, settings, monkeypatch):
    settings.CURATION_BLOCK_PRIVATE_HOSTS = True
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(socket.AF_INET, 1, 6, "", ("127.0.0.1", 0))]
    )
    web.add("http://localhost:8000/admin/", b"segredo")

    result = services.fetch_source(make_source("http://localhost:8000/admin/"))

    assert "rede interna" in result.error
    assert web.requests == []


@pytest.mark.django_db
def test_erro_inesperado_vira_erro_da_fonte(web, make_source, monkeypatch):
    web.add(FEED, feed("rss_basico.xml"))

    def boom(*args):
        raise RuntimeError("bug")

    monkeypatch.setattr(services, "_store_entries", boom)
    result = services.fetch_source(make_source())

    assert "Erro inesperado" in result.error


@pytest.mark.django_db
def test_fontes_vencidas_respeitam_intervalo_e_ativas(make_source):
    now = timezone.now()
    never = make_source("https://a.org/feed", name="Nunca")
    recent = make_source("https://b.org/feed", name="Recente", last_fetched_at=now)
    old = make_source(
        "https://c.org/feed", name="Antiga", last_fetched_at=now - timedelta(minutes=115)
    )
    make_source("https://d.org/feed", name="Desativada", is_active=False)

    assert set(services.due_sources(now)) == {never, old}
    assert recent.is_due(now + timedelta(hours=2))
