"""Deduplicação entre fontes e retenção das notícias (E46; docs/21, "Deduplicação" e "Higiene")."""

from datetime import UTC, datetime, timedelta
from io import StringIO
from xml.sax.saxutils import escape

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.core import tasks as core_tasks
from apps.curation import normalize, services
from apps.curation.models import NewsItem

A = "https://agencia-a.exemplo.org/feed"
B = "https://agencia-b.exemplo.org/feed"
TITLE = "Estudantes de Osasco vencem olimpíada de robótica"


def rss(*items: tuple[str, str, str]) -> bytes:
    """Feed RSS com itens (título, link, data RFC 822)."""
    body = "".join(
        f"<item><title>{escape(title)}</title><link>{escape(link)}</link>"
        f"<pubDate>{date}</pubDate></item>"
        for title, link, date in items
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Feed</title>'
        f"<link>https://exemplo.org/</link><description>x</description>{body}</channel></rss>"
    ).encode()


@pytest.fixture
def two_sources(make_source):
    return make_source(A, name="Agência A"), make_source(B, name="Agência B")


@pytest.mark.django_db
def test_mesmo_link_com_parametros_diferentes_em_duas_fontes_gera_um_registro(web, two_sources):
    first, second = two_sources
    date = "Thu, 17 Sep 2026 10:00:00 -0300"
    web.add(A, rss((TITLE, "https://noticia.exemplo.org/robotica/?utm_source=a", date)))
    web.add(
        B,
        rss(
            (
                "Robótica: time de Osasco é campeão",
                "https://www.noticia.exemplo.org/robotica/?fbclid=x#topo",
                date,
            )
        ),
    )

    services.fetch_source(first)
    result = services.fetch_source(second)

    assert (result.new, result.known) == (0, 1)
    item = NewsItem.objects.get()
    assert item.source == first
    assert item.canonical_url == "https://noticia.exemplo.org/robotica/"


@pytest.mark.django_db
def test_mesmo_titulo_com_links_diferentes_em_duas_fontes_gera_um_registro(web, two_sources):
    first, second = two_sources
    web.add(A, rss((TITLE, "https://a.exemplo.org/robotica", "Thu, 17 Sep 2026 10:00:00 -0300")))
    web.add(
        B,
        rss(
            (
                "ESTUDANTES DE OSASCO VENCEM OLIMPIADA DE ROBOTICA!",
                "https://b.exemplo.org/2026/09/robotica-osasco",
                "Sat, 19 Sep 2026 08:00:00 -0300",
            )
        ),
    )

    services.fetch_source(first)
    result = services.fetch_source(second)

    assert (result.new, result.known, result.repeated) == (0, 0, 1)
    assert result.describe() == "Agência B: 0 nova(s), 0 já conhecida(s), 1 com título repetido"
    assert NewsItem.objects.get().source == first
    # Descartada antes do HEAD: não gasta pedido com o link repetido.
    assert "https://b.exemplo.org/2026/09/robotica-osasco" not in web.heads()


@pytest.mark.django_db
def test_ordem_da_coleta_nao_muda_quantos_registros_ficam(web, two_sources):
    first, second = two_sources
    web.add(A, rss((TITLE, "https://a.exemplo.org/robotica", "Thu, 17 Sep 2026 10:00:00 -0300")))
    web.add(B, rss((TITLE, "https://b.exemplo.org/robotica", "Thu, 17 Sep 2026 11:00:00 -0300")))

    services.fetch_source(second)
    services.fetch_source(first)
    services.fetch_source(second)

    assert NewsItem.objects.get().source == second


@pytest.mark.django_db
def test_mesmo_titulo_repetido_no_mesmo_feed_gera_um_registro(web, make_source):
    date = "Thu, 17 Sep 2026 10:00:00 -0300"
    web.add(
        A, rss((TITLE, "https://a.exemplo.org/1", date), (TITLE, "https://a.exemplo.org/2", date))
    )

    result = services.fetch_source(make_source(A))

    assert (result.new, result.repeated) == (1, 1)


@pytest.mark.django_db
def test_mesmo_titulo_depois_de_7_dias_e_outra_noticia(web, two_sources):
    first, second = two_sources
    web.add(A, rss((TITLE, "https://a.exemplo.org/2026", "Thu, 10 Sep 2026 10:00:00 -0300")))
    web.add(B, rss((TITLE, "https://b.exemplo.org/2026", "Fri, 18 Sep 2026 10:00:00 -0300")))

    services.fetch_source(first)

    assert services.fetch_source(second).new == 1
    assert NewsItem.objects.count() == 2


@pytest.mark.django_db
def test_titulos_parecidos_de_fatos_diferentes_nao_sao_fundidos(web, two_sources):
    first, second = two_sources
    date = "Thu, 17 Sep 2026 10:00:00 -0300"
    web.add(A, rss((TITLE, "https://a.exemplo.org/robotica", date)))
    web.add(
        B,
        rss(
            ("Estudantes de Barueri vencem olimpíada de robótica", "https://b.exemplo.org/r", date)
        ),
    )

    services.fetch_source(first)

    assert services.fetch_source(second).new == 1
    assert NewsItem.objects.count() == 2


@pytest.mark.django_db
def test_titulo_curto_nao_entra_na_deduplicacao(web, two_sources):
    first, second = two_sources
    date = "Thu, 17 Sep 2026 10:00:00 -0300"
    web.add(A, rss(("Editorial", "https://a.exemplo.org/editorial", date)))
    web.add(B, rss(("Editorial", "https://b.exemplo.org/editorial", date)))

    services.fetch_source(first)

    assert services.fetch_source(second).new == 1


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Editorial", False),
        ("Podcast da semana", False),
        ("IA na escola: o que muda", True),
        ("Estudantes vencem olimpíada de robótica", True),
    ],
)
def test_titulo_marcante_tem_ao_menos_4_palavras(title, expected):
    assert normalize.is_distinctive_title(title) is expected


# --- retenção ---


def _item(source, suffix: str, fetched_at: datetime, published_at: datetime | None = None):
    return NewsItem.objects.create(
        source=source,
        title=f"Notícia {suffix}",
        url=f"https://a.exemplo.org/{suffix}",
        canonical_url=f"https://a.exemplo.org/{suffix}",
        url_hash=suffix * 64 if len(suffix) == 1 else suffix.ljust(64, "0"),
        title_hash=normalize.title_hash(f"Notícia {suffix}"),
        published_at=published_at or fetched_at,
        fetched_at=fetched_at,
        language="pt",
    )


@pytest.mark.django_db
def test_retencao_apaga_so_o_coletado_ha_mais_de_60_dias_e_pode_rodar_de_novo(make_source):
    source = make_source()
    now = datetime(2026, 11, 20, 12, tzinfo=UTC)
    _item(source, "a", fetched_at=now - timedelta(days=61))
    kept = _item(source, "b", fetched_at=now - timedelta(days=59))
    # Publicada há muito tempo, mas coletada agora: fica (senão voltaria na próxima coleta).
    old_in_feed = _item(
        source, "c", fetched_at=now - timedelta(days=1), published_at=now - timedelta(days=200)
    )

    assert services.purge_old_items(now) == 1
    assert services.purge_old_items(now) == 0
    assert set(NewsItem.objects.all()) == {kept, old_in_feed}


@pytest.mark.django_db
def test_cleanup_diario_inclui_as_noticias_antigas(make_source):
    _item(make_source(), "a", fetched_at=timezone.now() - timedelta(days=90))

    assert core_tasks.cleanup(timestamp=0)["noticias_antigas"] == 1
    out = StringIO()
    call_command("cleanup", stdout=out)
    assert "Notícias coletadas antigas apagadas: 0." in out.getvalue()
    assert not NewsItem.objects.exists()


@pytest.mark.django_db
def test_admin_apaga_as_noticias_de_uma_fonte(admin_client, make_source):
    source = make_source()
    other = make_source(B, name="Outra")
    now = timezone.now()
    _item(source, "a", fetched_at=now)
    _item(source, "b", fetched_at=now)
    kept = _item(other, "c", fetched_at=now)

    response = admin_client.post(
        reverse("admin:curation_newssource_changelist"),
        {"action": "delete_items", "_selected_action": [source.pk]},
        follow=True,
    )

    assert "2 notícia(s) apagada(s)" in response.content.decode()
    assert list(NewsItem.objects.all()) == [kept]
    source.refresh_from_db()  # a fonte continua
