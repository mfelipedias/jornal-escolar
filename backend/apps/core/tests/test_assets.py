"""Carregamento sem salto (docs/09, R1): CSS por <link> antes do JS e preload das fontes."""

import pytest
from django.template import Context, Template

from apps.core.templatetags import assets

pytestmark = pytest.mark.django_db


def test_base_carrega_css_por_link_antes_do_javascript(client):
    html = client.get("/").content.decode()
    head = html.split("</head>")[0]

    assert 'rel="stylesheet" href="http://localhost:5173/static/dist/src/css/app.css"' in head
    assert head.index('rel="stylesheet"') < head.index("src/js/app.js")


def test_base_tem_favicons_manifest_e_theme_color(client):
    head = client.get("/").content.decode().split("</head>")[0]

    assert '<meta name="theme-color" content="#FFFDF7">' in head
    assert 'href="/static/img/favicon.svg" type="image/svg+xml"' in head
    assert 'href="/static/img/favicon.ico" sizes="32x32"' in head
    assert 'rel="apple-touch-icon" href="/static/img/apple-touch-icon.png"' in head
    assert 'rel="manifest" href="/static/manifest.json"' in head


def test_font_preloads_vazio_em_dev():
    assert Template("{% load assets %}{% font_preloads %}").render(Context()) == ""


def test_font_preloads_usa_os_arquivos_do_build(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    for name in (
        "bricolage-grotesque-latin-opsz-normal-AbC123.woff2",
        "newsreader-latin-opsz-normal-XyZ789.woff2",
        "newsreader-latin-opsz-italic-Qwe456.woff2",  # itálico não entra no preload
    ):
        (dist / "assets" / name).write_bytes(b"")
    settings.DJANGO_VITE["default"]["dev_mode"] = False
    settings.DJANGO_VITE["default"]["manifest_path"] = dist / "manifest.json"
    assets._font_files.cache_clear()
    try:
        html = Template("{% load assets %}{% font_preloads %}").render(Context())
    finally:
        settings.DJANGO_VITE["default"]["dev_mode"] = True
        assets._font_files.cache_clear()

    assert html.count('<link rel="preload"') == 2
    assert 'href="/static/dist/assets/bricolage-grotesque-latin-opsz-normal-AbC123.woff2"' in html
    assert 'as="font" type="font/woff2" crossorigin' in html
    assert "italic" not in html
