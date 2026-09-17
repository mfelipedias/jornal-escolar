"""Normalização dos itens de feed (docs/21, "Normalização")."""

import time
from datetime import UTC, datetime

import pytest

from apps.curation import normalize

NOW = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://site.org/a/?utm_source=rss&utm_medium=feed", "https://site.org/a/"),
        ("https://site.org/a?id=3&fbclid=XYZ&gclid=1", "https://site.org/a?id=3"),
        ("https://site.org/a#comentarios", "https://site.org/a"),
        ("HTTPS://Site.ORG:443/Caminho", "https://site.org/Caminho"),
        ("http://site.org:80/a", "http://site.org/a"),
        ("http://site.org:8080/a", "http://site.org:8080/a"),
        ("https://site.org", "https://site.org/"),
        ("https://site.org/a?pagina=2&mc_cid=abc&UTM_Campaign=x", "https://site.org/a?pagina=2"),
        ("https://site.org/a?", "https://site.org/a"),
    ],
)
def test_canonicaliza_url(url, expected):
    assert normalize.canonicalize_url(url) == expected


def test_url_hash_ignora_esquema_e_www():
    a = normalize.url_hash("http://www.site.org/noticia")
    b = normalize.url_hash("https://site.org/noticia")
    c = normalize.url_hash("https://site.org/outra")
    assert a == b != c


def test_title_hash_ignora_caixa_acentos_e_pontuacao():
    assert normalize.title_hash("Física: nova  descoberta!") == normalize.title_hash(
        "fisica nova descoberta"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sensor mede o ar - Ciência Exemplo", "Sensor mede o ar"),
        ("Sensor mede o ar | CIENCIA EXEMPLO", "Sensor mede o ar"),
        ("Sensor mede o ar – Revista", "Sensor mede o ar"),  # noqa: RUF001
        ("Entrevista - parte 2", "Entrevista - parte 2"),
        ("  <b>Título</b>\n com   espaços &amp; entidade ", "Título com espaços & entidade"),
    ],
)
def test_limpa_titulo(raw, expected):
    assert normalize.clean_title(raw, ("Ciência Exemplo", "Revista")) == expected


def test_resumo_sem_html_e_sem_script():
    raw = "<p>Um <strong>sensor</strong> mede.</p><p>Começou numa escola.</p><script>x()</script>"
    assert normalize.clean_summary(raw) == "Um sensor mede. Começou numa escola."


def test_resumo_sem_rodape_do_wordpress():
    assert normalize.clean_summary("Texto. The post X appeared first on Blog.") == "Texto."
    assert normalize.clean_summary("O post Um título apareceu primeiro em PORVIR. Texto.") == (
        "Texto."
    )
    assert normalize.clean_summary("Texto longo [&#8230;]") == "Texto longo"


def test_resumo_com_html_escapado_duas_vezes():
    raw = "&lt;_cdata&gt;&lt;p&gt;A saúde &amp;amp; o SUS.&lt;/p&gt;"
    assert normalize.clean_summary(raw) == "A saúde & o SUS."


def test_resumo_longo_termina_na_ultima_frase_completa():
    text = ("Frase completa número um. " * 30).strip()
    summary = normalize.clean_summary(text)
    assert len(summary) <= 600
    assert summary.endswith("um.")


def test_resumo_longo_sem_ponto_corta_na_palavra_com_reticencias():
    summary = normalize.clean_summary("palavra " * 200)
    assert len(summary) <= 600
    assert summary.endswith("palavra…")


def test_data_publicada_senao_atualizada_senao_agora():
    published = time.strptime("2026-09-16 10:00", "%Y-%m-%d %H:%M")
    updated = time.strptime("2026-09-15 10:00", "%Y-%m-%d %H:%M")
    assert normalize.entry_datetime({"published_parsed": published}, NOW) == datetime(
        2026, 9, 16, 10, 0, tzinfo=UTC
    )
    assert normalize.entry_datetime({"updated_parsed": updated}, NOW) == datetime(
        2026, 9, 15, 10, 0, tzinfo=UTC
    )
    assert normalize.entry_datetime({}, NOW) == NOW


def test_data_no_futuro_vira_hora_da_coleta():
    future = time.strptime("2027-01-01 10:00", "%Y-%m-%d %H:%M")
    assert normalize.entry_datetime({"published_parsed": future}, NOW) == NOW


def test_imagem_so_endereco_web():
    assert normalize.entry_image_url({"media_thumbnail": [{"url": "https://a.org/i.jpg"}]}) == (
        "https://a.org/i.jpg"
    )
    assert normalize.entry_image_url({"media_thumbnail": [{"url": "javascript:x"}]}) == ""
    enclosure = {"rel": "enclosure", "type": "image/png", "href": "https://a.org/i.png"}
    assert normalize.entry_image_url({"links": [enclosure]}) == "https://a.org/i.png"
