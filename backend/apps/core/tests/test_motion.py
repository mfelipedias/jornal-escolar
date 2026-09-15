"""Carregamento e movimento (docs/09, "Movimento", R5): o que depende do servidor."""

import re

import pytest

from apps.publications import services
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

# Atributo style ou bloco <style>/<script> inline no HTML: a CSP bloquearia (docs/23).
INLINE_STYLE = re.compile(r"<[a-z][^>]*\sstyle=", re.IGNORECASE)
INLINE_STYLE_BLOCK = re.compile(r"<style[\s>]", re.IGNORECASE)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc=)(?![^>]*type=\"application/ld\+json\")[^>]*>")


@pytest.fixture
def article():
    author = UserFactory()
    article = ArticleFactory(ready=True, author=author, created_by=author)
    services.publish(author, article)
    return article


def pages(client, article):
    urls = ["/", "/publicacoes/", "/agenda/", "/busca/?q=feira", article.get_absolute_url()]
    return {url: client.get(url).content.decode() for url in urls}


def test_barra_de_carregamento_em_todas_as_paginas(client, article, staff_user):
    for url, html in pages(client, article).items():
        assert html.count('class="page-progress"') == 1, url

    client.force_login(staff_user)
    assert 'class="page-progress"' in client.get("/painel/").content.decode()


def test_barra_fica_escondida_para_leitores_de_tela(client):
    html = client.get("/").content.decode()

    assert '<div class="page-progress" aria-hidden="true"></div>' in html


def test_paginas_publicas_sem_estilo_nem_script_inline(client, article):
    for url, html in pages(client, article).items():
        assert not INLINE_STYLE.search(html), url
        assert not INLINE_STYLE_BLOCK.search(html), url
        assert not INLINE_SCRIPT.search(html), url


def test_linha_da_data_marcada_para_encolher_ao_rolar(client):
    html = client.get("/").content.decode()
    masthead = html[html.index("<header") : html.index("</header>")]

    assert 'class="masthead ' in masthead
    assert "masthead-dateline" in masthead


def test_exportacao_de_dados_nao_prende_a_barra(client, staff_user):
    """O download não troca de página: a barra não pode ficar ligada esperando."""
    client.force_login(staff_user)

    html = client.get("/painel/conta/").content.decode()

    assert "data-export data-no-progress" in html
