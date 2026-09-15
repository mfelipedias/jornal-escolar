"""Reações (docs/20; E38). Aceite: a 31ª reação no mesmo minuto, do mesmo IP, é bloqueada.

Os limites usam o cache do Django; o conftest limpa o cache antes de cada teste.
"""

import re
import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts import privacy
from apps.core.models import SiteSetting
from apps.engagement import services, visitor
from apps.engagement.models import Reaction
from apps.publications import services as article_services
from apps.publications.cache import public_version
from apps.publications.models import Article
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def article():
    author = UserFactory()
    item = ArticleFactory(ready=True, author=author, created_by=author, title="Horta da escola")
    article_services.publish(author, item)
    item.refresh_from_db()
    return item


def url(article: Article) -> str:
    return f"/x/articles/{article.pk}/react/"


def visitor_client(key: uuid.UUID | None = None) -> Client:
    client = Client()
    client.cookies[visitor.COOKIE_NAME] = str(key or uuid.uuid4())
    return client


# --- serviço ---


def test_toggle_cria_troca_e_remove(article):
    key = uuid.uuid4()

    assert services.toggle_reaction(article, "liked", anon_key=key) == "liked"
    assert article.reactions_count == {"liked": 1}
    assert services.toggle_reaction(article, "learned", anon_key=key) == "learned"
    assert article.reactions_count == {"learned": 1}
    assert services.toggle_reaction(article, "learned", anon_key=key) is None
    assert article.reactions_count == {}

    article.refresh_from_db()
    assert article.reactions_count == {}
    assert not Reaction.objects.exists()


def test_contagem_por_tipo_com_usuarios_e_visitantes(article):
    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())
    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())
    services.toggle_reaction(article, "congrats", user=UserFactory())

    article.refresh_from_db()
    assert article.reactions_count == {"liked": 2, "congrats": 1}


def test_uma_reacao_por_pessoa_no_banco(article):
    key = uuid.uuid4()
    Reaction.objects.create(article=article, anon_key=key, kind="liked")
    with pytest.raises(IntegrityError):
        Reaction.objects.create(article=article, anon_key=key, kind="learned")


def test_reacao_precisa_de_usuario_ou_codigo(article):
    with pytest.raises(IntegrityError):
        Reaction.objects.create(article=article, kind="liked")


def test_tipo_invalido_e_rascunho_sao_recusados(article):
    with pytest.raises(ValidationError):
        services.toggle_reaction(article, "odiei", anon_key=uuid.uuid4())
    draft = ArticleFactory()
    with pytest.raises(PermissionDenied):
        services.toggle_reaction(draft, "liked", anon_key=uuid.uuid4())


def test_reagir_nao_invalida_o_cache_publico(article):
    before = public_version()

    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())

    assert public_version() == before


def test_configuracao_so_com_login(article):
    SiteSetting.objects.create(key="reactions.require_login", value=True)

    from apps.editorial import permissions

    assert not permissions.can_react(AnonymousUser(), article)
    assert permissions.can_react(UserFactory(), article)
    response = visitor_client().post(url(article), {"kind": "liked"}, **HX)
    assert response.status_code == 403


def test_conta_apagada_refaz_o_total(article, django_capture_on_commit_callbacks):
    user = UserFactory()
    services.toggle_reaction(article, "liked", user=user)
    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())

    with django_capture_on_commit_callbacks(execute=True):
        user.delete()

    article.refresh_from_db()
    assert article.reactions_count == {"liked": 1}


# --- página da publicação ---


def test_pagina_emite_cookie_anonimo(client, article):
    response = client.get(article.get_absolute_url())

    cookie = response.cookies[visitor.COOKIE_NAME]
    assert uuid.UUID(cookie.value).version == 4
    assert cookie["max-age"] == 60 * 60 * 24 * 365
    assert cookie["samesite"] == "Lax"
    assert cookie["httponly"]


def test_pagina_mantem_cookie_existente_e_nao_emite_para_logado(client, article):
    client.cookies[visitor.COOKIE_NAME] = str(uuid.uuid4())
    assert visitor.COOKIE_NAME not in client.get(article.get_absolute_url()).cookies

    other = Client()
    other.force_login(UserFactory())
    assert visitor.COOKIE_NAME not in other.get(article.get_absolute_url()).cookies


def test_cookie_seguro_em_producao(client, article, settings):
    settings.SESSION_COOKIE_SECURE = True
    response = client.get(article.get_absolute_url())
    assert response.cookies[visitor.COOKIE_NAME]["secure"]


def test_barra_na_pagina_sem_numeros_quando_zero(client, article):
    html = client.get(article.get_absolute_url()).content.decode()

    assert 'id="reacoes"' in html
    assert f'action="/x/articles/{article.pk}/react/"' in html
    assert html.count('aria-pressed="false"') == 4
    for label in ("Interessante", "Aprendi algo", "Gostei", "Parabéns"):
        assert label in html
    assert "reaction-count" not in html


def test_barra_mostra_contagem_e_estado_do_visitante(article):
    key = uuid.uuid4()
    services.toggle_reaction(article, "liked", anon_key=key)
    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())

    html = visitor_client(key).get(article.get_absolute_url()).content.decode()

    pressed = re.search(r'<button[^>]*aria-pressed="true"[^>]*>', html).group(0)
    assert 'value="liked"' in pressed
    assert '2 <span class="sr-only">reações</span>' in html


def test_previa_nao_tem_barra(client):
    author = UserFactory()
    draft = ArticleFactory(author=author, created_by=author)
    client.force_login(author)

    html = client.get(f"/publicacoes/previa/{draft.pk}/").content.decode()

    assert 'id="reacoes"' not in html


# --- endpoint ---


def test_htmx_devolve_fragmento_com_botao_marcado(article):
    client = visitor_client()

    response = client.post(url(article), {"kind": "learned"}, **HX)

    html = response.content.decode()
    assert response.status_code == 200
    assert 'id="reacoes"' in html
    assert "<html" not in html
    assert re.search(r'value="learned"\s+aria-pressed="true"', html)
    assert "no-cache" in response["Cache-Control"]


def test_mesmo_tipo_remove_e_outro_troca(article):
    client = visitor_client()

    client.post(url(article), {"kind": "liked"}, **HX)
    client.post(url(article), {"kind": "congrats"}, **HX)
    article.refresh_from_db()
    assert article.reactions_count == {"congrats": 1}

    client.post(url(article), {"kind": "congrats"}, **HX)
    article.refresh_from_db()
    assert article.reactions_count == {}


def test_sem_javascript_redireciona_para_a_barra(article):
    response = visitor_client().post(url(article), {"kind": "liked"})

    assert response.status_code == 302
    assert response["Location"] == f"{article.get_absolute_url()}#reacoes"
    assert Reaction.objects.filter(article=article, kind="liked").count() == 1


def test_usuario_logado_reage_com_a_conta(client, article):
    user = UserFactory()
    client.force_login(user)

    client.post(url(article), {"kind": "liked"}, **HX)

    reaction = Reaction.objects.get()
    assert reaction.user == user
    assert reaction.anon_key is None


def test_visitante_sem_cookie_e_ignorado(client, article):
    response = client.post(url(article), {"kind": "liked"}, **HX)

    assert response.status_code == 200
    assert not Reaction.objects.exists()
    assert "Tente de novo" in response.content.decode()
    assert visitor.COOKIE_NAME in response.cookies  # a próxima tentativa funciona


def test_cookie_invalido_e_ignorado(article):
    client = Client()
    client.cookies[visitor.COOKIE_NAME] = "nao-e-uuid"

    client.post(url(article), {"kind": "liked"}, **HX)

    assert not Reaction.objects.exists()


def test_tipo_invalido_devolve_400(article):
    response = visitor_client().post(url(article), {"kind": "odiei"}, **HX)

    assert response.status_code == 400
    assert "Reação inválida" in response.content.decode()


def test_rascunho_e_get_nao_reagem(article):
    draft = ArticleFactory()
    client = visitor_client()

    assert client.post(url(draft), {"kind": "liked"}, **HX).status_code == 404
    assert client.get(url(article)).status_code == 405
    assert client.post("/x/articles/999999/react/", {"kind": "liked"}).status_code == 404


def test_exige_csrf(article):
    client = Client(enforce_csrf_checks=True)
    client.get(article.get_absolute_url())  # recebe os cookies jv e csrftoken

    assert client.post(url(article), {"kind": "liked"}, **HX).status_code == 403
    token = client.cookies["csrftoken"].value
    response = client.post(url(article), {"kind": "liked", "csrfmiddlewaretoken": token}, **HX)
    assert response.status_code == 200
    assert Reaction.objects.count() == 1


# --- limites ---


def test_31a_reacao_do_mesmo_ip_no_minuto_e_bloqueada(article):
    for _ in range(30):
        response = visitor_client().post(url(article), {"kind": "liked"}, **HX)
        assert response.status_code == 200

    response = visitor_client().post(url(article), {"kind": "liked"}, **HX)

    assert response.status_code == 429
    assert "Muitas reações em pouco tempo" in response.content.decode()
    article.refresh_from_db()
    assert article.reactions_count == {"liked": 30}


def test_outro_ip_nao_e_afetado(article):
    for _ in range(31):
        visitor_client().post(url(article), {"kind": "liked"}, **HX)

    response = visitor_client().post(url(article), {"kind": "liked"}, REMOTE_ADDR="10.0.0.9", **HX)

    assert response.status_code == 200


def test_11a_reacao_da_mesma_pessoa_no_minuto_e_bloqueada(article):
    client = visitor_client()
    for _ in range(10):
        assert client.post(url(article), {"kind": "liked"}, **HX).status_code == 200

    assert client.post(url(article), {"kind": "liked"}, **HX).status_code == 429


def test_limite_sem_javascript_mostra_pagina(article, settings):
    settings.REACTIONS_PER_MINUTE_PER_IP = 1
    visitor_client().post(url(article), {"kind": "liked"})

    response = visitor_client().post(url(article), {"kind": "liked"})

    assert response.status_code == 429
    html = response.content.decode()
    assert "Reação não registrada" in html
    assert f'href="{article.get_absolute_url()}#reacoes"' in html


# --- exportação de dados ---


def test_exportacao_inclui_so_reacoes_da_conta(article):
    user = UserFactory()
    services.toggle_reaction(article, "learned", user=user)
    services.toggle_reaction(article, "liked", anon_key=uuid.uuid4())

    data = privacy.export_user_data(user)

    assert data["reacoes"] == [
        {
            "publicacao": {"id": article.pk, "titulo": "Horta da escola", "estado": "Publicado"},
            "reacao": "Aprendi algo",
            "quando": data["reacoes"][0]["quando"],
        }
    ]
