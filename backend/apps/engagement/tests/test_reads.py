"""Leituras (docs/20; E39). Aceite: recarregar a página 5 vezes conta 1 leitura.

A regra de tempo e rolagem fica no navegador (frontend/src/js/read-beacon.js); aqui se testa
o que o servidor garante: uma leitura por pessoa, por publicação, por dia, só com o beacon.
"""

import re
import uuid
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from apps.core.models import SiteSetting
from apps.core.ratelimit import hit
from apps.engagement import services, visitor
from apps.engagement.models import ArticleRead
from apps.publications import services as article_services
from apps.publications.cache import public_version
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def article(author):
    item = ArticleFactory(ready=True, author=author, created_by=author, title="Horta da escola")
    article_services.publish(author, item)
    item.refresh_from_db()
    return item


def url(article: Article) -> str:
    return f"/x/articles/{article.pk}/read/"


def reads(article: Article) -> int:
    return Article.objects.values_list("reads_count", flat=True).get(pk=article.pk)


def open_and_read(client: Client, article: Article):
    """O que o navegador faz: abre a página e, depois do tempo e da rolagem, manda o beacon
    com o token do CSRF que veio na página."""
    html = client.get(article.get_absolute_url()).content.decode()
    beacon = re.search(r"<div data-read-beacon(.*?)</div>", html, re.S)
    assert beacon, "página sem o beacon de leitura"
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', beacon.group(1)).group(1)
    return client.post(url(article), {"csrfmiddlewaretoken": token})


# --- serviço ---


def test_uma_leitura_por_pessoa_por_dia(article):
    key = uuid.uuid4()
    today = timezone.localdate()

    assert services.record_read(article, anon_key=key) is True
    assert services.record_read(article, anon_key=key) is False
    assert services.record_read(article, anon_key=uuid.uuid4()) is True
    assert services.record_read(article, anon_key=key, day=today + timedelta(days=1)) is True

    assert reads(article) == 3
    assert ArticleRead.objects.count() == 3


def test_usuario_logado_conta_pela_conta(article):
    reader = UserFactory()

    assert services.record_read(article, user=reader) is True
    assert services.record_read(article, user=reader, anon_key=uuid.uuid4()) is False
    assert reads(article) == 1


def test_quem_esta_nos_creditos_nao_conta(article, author):
    assert services.record_read(article, user=author) is False
    assert reads(article) == 0


def test_rascunho_e_visitante_sem_codigo_nao_contam(article, author):
    draft = ArticleFactory(author=author, created_by=author)

    assert services.record_read(draft, anon_key=uuid.uuid4()) is False
    assert services.record_read(article, anon_key=None) is False
    assert not ArticleRead.objects.exists()


def test_chave_do_leitor_nao_guarda_o_codigo_nem_liga_os_dias(article):
    key = uuid.uuid4()
    today = timezone.localdate()

    services.record_read(article, anon_key=key)
    stored = ArticleRead.objects.get().viewer_key

    assert len(stored) == 64
    assert str(key) not in stored
    assert stored == services.viewer_key(today, anon_key=key)
    assert stored != services.viewer_key(today + timedelta(days=1), anon_key=key)


def test_leitura_nao_invalida_o_cache_publico(article):
    before = public_version()

    services.record_read(article, anon_key=uuid.uuid4())

    assert public_version() == before


def test_leituras_dos_ultimos_30_dias(article):
    today = timezone.localdate()
    for days_ago in (0, 29, 30, 60):
        services.record_read(article, anon_key=uuid.uuid4(), day=today - timedelta(days=days_ago))

    assert services.reads_since(Article.objects.filter(pk=article.pk), days=30) == 2


def test_limpeza_apaga_registros_com_mais_de_90_dias(article, capsys):
    today = timezone.localdate()
    for days_ago in (0, 90, 91, 400):
        services.record_read(article, anon_key=uuid.uuid4(), day=today - timedelta(days=days_ago))

    call_command("cleanup")

    assert sorted(ArticleRead.objects.values_list("day", flat=True)) == [
        today - timedelta(days=90),
        today,
    ]
    assert reads(article) == 4  # o total consolidado não muda
    assert "Leituras antigas apagadas: 2." in capsys.readouterr().out


# --- endpoint ---


def test_recarregar_5_vezes_conta_1(article):
    client = Client(enforce_csrf_checks=True)

    for _ in range(5):
        response = open_and_read(client, article)
        assert response.status_code == 204

    assert reads(article) == 1


def test_so_abrir_a_pagina_nao_conta(client, article):
    for _ in range(5):
        client.get(article.get_absolute_url())

    assert reads(article) == 0


def test_outro_visitante_e_usuario_logado_contam(article):
    open_and_read(Client(enforce_csrf_checks=True), article)
    open_and_read(Client(enforce_csrf_checks=True), article)
    logged = Client(enforce_csrf_checks=True)
    logged.force_login(UserFactory())
    open_and_read(logged, article)
    open_and_read(logged, article)

    assert reads(article) == 3


def test_autor_revisando_nao_conta(article, author):
    client = Client(enforce_csrf_checks=True)
    client.force_login(author)

    assert open_and_read(client, article).status_code == 204
    assert reads(article) == 0


def test_beacon_sem_cookie_e_ignorado(client, article):
    response = client.post(url(article))

    assert response.status_code == 204
    assert reads(article) == 0


def test_exige_csrf(article):
    client = Client(enforce_csrf_checks=True)
    client.get(article.get_absolute_url())

    assert client.post(url(article)).status_code == 403
    assert reads(article) == 0


def test_rascunho_e_get_nao_contam(client, author):
    draft = ArticleFactory(author=author, created_by=author)
    client.cookies[visitor.COOKIE_NAME] = str(uuid.uuid4())

    assert client.post(url(draft)).status_code == 404
    assert client.get(url(draft)).status_code == 405


def test_61o_beacon_do_mesmo_ip_no_minuto_e_bloqueado(article):
    for _ in range(60):
        client = Client()
        client.cookies[visitor.COOKIE_NAME] = str(uuid.uuid4())
        assert client.post(url(article)).status_code == 204

    client = Client()
    client.cookies[visitor.COOKIE_NAME] = str(uuid.uuid4())

    assert client.post(url(article)).status_code == 429
    assert client.post(url(article), REMOTE_ADDR="10.0.0.9").status_code == 204
    assert reads(article) == 61


# --- exibição ---


def test_beacon_na_pagina_com_tempo_da_configuracao(client, article):
    SiteSetting.objects.create(key="reads.min_seconds", value=20)

    html = client.get(article.get_absolute_url()).content.decode()

    assert f'data-url="/x/articles/{article.pk}/read/"' in html
    assert 'data-min-seconds="20"' in html
    assert "data-article-body" in html


def test_previa_nao_tem_beacon(client, author):
    draft = ArticleFactory(author=author, created_by=author)
    client.force_login(author)

    html = client.get(f"/publicacoes/previa/{draft.pk}/").content.decode()

    assert "data-read-beacon" not in html


def test_contagem_aparece_a_partir_de_10(client, article):
    Article.objects.filter(pk=article.pk).update(reads_count=9)
    assert "data-reads-count" not in client.get(article.get_absolute_url()).content.decode()

    Article.objects.filter(pk=article.pk).update(reads_count=1432)
    html = client.get(article.get_absolute_url()).content.decode()

    assert re.search(r"data-reads-count>\s*1\.432 leituras", html)


def test_autor_pode_esconder_a_contagem(client, article, author):
    Article.objects.filter(pk=article.pk).update(reads_count=50)
    author.profile.show_reads = False
    author.profile.save()

    html = client.get(article.get_absolute_url()).content.decode()

    assert "data-reads-count" not in html


def test_contagem_aparece_mesmo_com_reacoes_so_para_logados(client, article):
    SiteSetting.objects.create(key="reactions.require_login", value=True)
    Article.objects.filter(pk=article.pk).update(reads_count=12)

    html = client.get(article.get_absolute_url()).content.decode()

    assert 'id="reacoes"' not in html
    assert re.search(r"data-reads-count>\s*12 leituras", html)


def test_painel_mostra_leituras(client, article, author):
    draft = ArticleFactory(author=author, created_by=author, title="Rascunho da feira")
    Article.objects.filter(pk=article.pk).update(reads_count=7, reactions_count={"liked": 2})
    today = timezone.localdate()
    for days_ago in (0, 3, 45):
        services.record_read(article, anon_key=uuid.uuid4(), day=today - timedelta(days=days_ago))
    client.force_login(author)

    home = client.get("/painel/").content.decode()
    table = client.get("/painel/publicacoes/").content.decode()

    assert re.search(r"<span data-reads>10 leituras</span>", home)
    assert "2 reações" in home
    assert re.search(r">2</span>\s*<span[^>]*>Leituras em 30 dias<", home)
    row = table[table.index(f'data-article="{article.pk}"') :]
    assert re.search(r"data-reads>\s*10\s*<", row)
    draft_row = table[table.index(f'data-article="{draft.pk}"') :]
    assert "não publicada" in draft_row[: draft_row.index("</tr>")]


def test_numero_de_leituras_em_30_dias(article, author):
    from apps.dashboard import selectors

    today = timezone.localdate()
    for days_ago in (0, 3, 45):
        services.record_read(article, anon_key=uuid.uuid4(), day=today - timedelta(days=days_ago))
    someone = UserFactory()
    other = ArticleFactory(ready=True, author=someone, created_by=someone)
    article_services.publish(someone, other)
    services.record_read(other, anon_key=uuid.uuid4())

    assert selectors.stats(author)["reads_30d"] == 2


# --- cache compartilhado de produção ---


def test_limite_funciona_com_o_cache_no_banco():
    """Produção usa DatabaseCache (config/settings/prod.py): os limites continuam valendo."""
    database_cache = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache_teste",
        }
    }
    with override_settings(CACHES=database_cache):  # o Django troca a conexão do cache
        call_command("createcachetable", verbosity=0)
        assert [hit("teste", limit=2, period=60) for _ in range(3)] == [True, True, False]
