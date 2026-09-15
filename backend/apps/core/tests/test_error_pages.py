"""Páginas de erro no visual novo (docs/09, "Feedback e erros"; R4)."""

from unittest import mock

import pytest
from django.template.loader import render_to_string


def test_500_renders_without_request_or_database():
    """O Django renderiza o 500 sem context processors. Sem a marca django_db, qualquer
    consulta ao banco faria o teste falhar."""
    html = render_to_string("500.html")

    assert "Algo deu errado" in html
    assert html.count("<h1") == 1
    assert 'rel="stylesheet"' in html


def test_500_survives_broken_build():
    with mock.patch(
        "django_vite.templatetags.django_vite.vite_asset_url", side_effect=RuntimeError("manifest")
    ):
        html = render_to_string("500.html")

    assert "Algo deu errado" in html
    assert 'rel="stylesheet"' not in html


@pytest.mark.django_db
def test_404_has_search_and_decorative_code(client):
    html = client.get("/nao-existe-mesmo/").content.decode()

    assert '<p class="status-code" aria-hidden="true">404</p>' in html
    assert 'role="search"' in html
    assert html.count("<h1") == 1
