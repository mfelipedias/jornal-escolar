import re

import pytest
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.core.middleware import HtmxMessagesMiddleware
from apps.core.templatetags.ui import elided_pages, status_badge

pytestmark = pytest.mark.django_db

URL = "/dev/components/"


# --- acesso ---


def test_url_name():
    assert reverse("core:components") == URL


def test_hidden_from_anonymous_in_production(client):
    assert client.get(URL).status_code == 404


def test_hidden_from_staff_in_production(client, staff_user):
    client.force_login(staff_user)

    assert client.get(URL).status_code == 404


def test_open_in_development(client, settings):
    settings.DEBUG = True

    assert client.get(URL).status_code == 200


# --- vitrine ---


@pytest.fixture
def page(admin_client):
    response = admin_client.get(URL)
    assert response.status_code == 200
    assert response["X-Robots-Tag"] == "noindex"
    return response.content.decode()


def test_renders_every_component(admin_client):
    response = admin_client.get(URL)

    used = {t.name for t in response.templates}
    assert {
        "components/card.html",
        "components/byline.html",
        "components/tag.html",
        "components/status_badge.html",
        "components/empty_state.html",
        "components/pagination.html",
        "components/toast.html",
    } <= used


def test_card_variants(page):
    assert page.count("Feira de Ciências reúne projetos de energia solar") == 4
    assert 'fetchpriority="high"' in page  # hero
    assert "img/demo/capa-verde.svg" in page
    assert "Por <span" in page
    assert "João Pereira, Carla Souza e Rafael S." in page
    assert "border-area-verde" in page
    assert page.count("<h1") == 1


def test_tags_and_statuses(page):
    for label in ["Ciências Humanas", "Geral", "Física", "Energia solar"]:
        assert label in page
    assert "bg-area-violeta-soft" in page
    for label in ["Rascunho", "Em revisão", "Alterações pedidas", "Aprovado", "Publicado"]:
        assert label in page


def test_empty_state_and_pagination(page):
    assert "Ainda não há publicações em Física" in page
    assert re.search(r'href="/dev/components/"[^>]*>Ver outras disciplinas', page)
    assert "Carregar mais" in page
    assert "Mostrando 5 de 120" in page
    assert 'aria-current="page"' in page
    assert 'aria-label="Página 24"' in page
    assert "…" in page


def test_pagination_keeps_other_query_params(admin_client):
    html = admin_client.get(URL + "?area=verde&page=3").content.decode()

    assert 'href="?area=verde&amp;page=4"' in html
    assert 'href="?area=verde&amp;page=2"' in html


def test_load_more_returns_items_and_next_button(admin_client):
    response = admin_client.get(URL + "?page=2", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert 'hx-swap-oob="beforeend:#demo-more-list"' in html
    assert "Item de exemplo 6" in html
    assert "page=3" in html
    assert "<html" not in html


# --- toast ---


def test_toast_region_on_every_page(client):
    html = client.get("/").content.decode()

    assert 'id="toasts"' in html
    assert 'aria-live="polite"' in html


def test_htmx_toast_comes_out_of_band(admin_client):
    response = admin_client.get(URL + "?toast=error", HTTP_HX_REQUEST="true")

    html = response.content.decode()
    assert 'hx-swap-oob="beforeend:#toasts"' in html
    assert 'data-level="error"' in html
    assert "Não foi possível salvar" in html
    # A mensagem foi consumida: não reaparece na próxima página.
    assert "Não foi possível salvar" not in admin_client.get(URL).content.decode()


def _request_with_message(rf: RequestFactory, *, htmx: bool):
    from django.contrib.messages.storage.fallback import FallbackStorage

    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = rf.get("/", **headers)
    request.session = {}
    request._messages = FallbackStorage(request)
    messages.success(request, "Salvo.")
    return request


@pytest.mark.parametrize(
    ("htmx", "response", "expected"),
    [
        (True, HttpResponse("<p>ok</p>"), True),
        (False, HttpResponse("<p>ok</p>"), False),
        (True, JsonResponse({"ok": True}), False),
        (True, HttpResponse("erro", status=400), False),
    ],
)
def test_middleware_only_touches_htmx_html(htmx, response, expected):
    request = _request_with_message(RequestFactory(), htmx=htmx)

    result = HtmxMessagesMiddleware(lambda r: response)(request)

    assert ("Salvo." in result.content.decode()) is expected


# --- filtros ---


def test_status_badge_filter():
    assert status_badge("published")["label"] == "Publicado"
    assert "text-area-verde" in status_badge("published")["classes"]
    assert status_badge("desconhecido")["label"] == "desconhecido"


def test_elided_pages():
    page = Paginator(range(100), 10).page(5)

    assert elided_pages(page) == [1, "…", 4, 5, 6, "…", 10]
