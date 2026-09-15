import pytest
from django.urls import reverse

from apps.accounts.services import complete_onboarding
from apps.core.models import SiteSetting
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

LOGIN_URL = "/entrar/"


@pytest.fixture
def microsoft_configured(settings):
    settings.MICROSOFT_LOGIN_CONFIGURED = True
    settings.SOCIALACCOUNT_PROVIDERS = {
        "microsoft": {
            "TENANT": "organizations",
            "APPS": [
                {
                    "client_id": "id-teste",
                    "secret": "segredo-teste",
                    "settings": {"tenant": "organizations"},
                }
            ],
        }
    }


def test_urls():
    assert reverse("accounts:login") == "/entrar/"
    assert reverse("accounts:logout") == "/sair/"


def test_login_page_without_microsoft(client):
    html = client.get(LOGIN_URL).content.decode()

    # O allauth põe "site" no contexto; a identidade do jornal não pode ser sobrescrita.
    assert '<span class="wordmark-accent">Escolar</span>' in html
    assert "<title>Entrar · Jornal Escolar</title>" in html
    assert "Entrar com senha" in html
    assert "Entrar com a conta da escola" not in html
    assert html.count("<h1") == 1


def test_login_page_with_microsoft(client, microsoft_configured):
    html = client.get(LOGIN_URL).content.decode()

    assert "Entrar com a conta da escola" in html
    assert 'action="/entrar/microsoft/login/' in html


def test_microsoft_button_can_be_turned_off(client, microsoft_configured):
    SiteSetting.objects.create(key="auth.microsoft_enabled", value=False)

    html = client.get(LOGIN_URL).content.decode()

    assert "Entrar com a conta da escola" not in html


def test_password_login_success(client):
    user = UserFactory(email="ana@escola.sp.gov.br")
    complete_onboarding(user)  # o primeiro login vai ao assistente (test_onboarding.py)

    response = client.post(
        LOGIN_URL, {"login": "ANA@Escola.sp.gov.br", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 302
    assert response.url == "/"
    assert int(client.session["_auth_user_id"]) == user.pk


def test_password_login_respects_next(client):
    UserFactory(email="ana@escola.sp.gov.br")

    response = client.post(
        f"{LOGIN_URL}?next=/sobre/",
        {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD, "next": "/sobre/"},
    )

    assert response.url == "/sobre/"


def test_wrong_password_shows_error(client):
    UserFactory(email="ana@escola.sp.gov.br")

    response = client.post(LOGIN_URL, {"login": "ana@escola.sp.gov.br", "password": "errada"})

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert 'role="alert"' in response.content.decode()


def test_inactive_user_cannot_log_in(client):
    UserFactory(email="ana@escola.sp.gov.br", is_active=False)

    response = client.post(
        LOGIN_URL, {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD}
    )

    assert "_auth_user_id" not in client.session
    assert response.status_code in (200, 302)


def test_microsoft_only_account_cannot_use_password(client):
    UserFactory(email="ms@escola.sp.gov.br", microsoft_only=True)

    client.post(LOGIN_URL, {"login": "ms@escola.sp.gov.br", "password": ""})
    client.post(LOGIN_URL, {"login": "ms@escola.sp.gov.br", "password": DEFAULT_PASSWORD})

    assert "_auth_user_id" not in client.session


def test_rate_limit_blocks_even_correct_password_after_five_failures(client):
    UserFactory(email="ana@escola.sp.gov.br")
    wrong = {"login": "ana@escola.sp.gov.br", "password": "errada"}
    for _ in range(5):
        client.post(LOGIN_URL, wrong)

    response = client.post(
        LOGIN_URL, {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD}
    )

    assert "_auth_user_id" not in client.session
    assert 'role="alert"' in response.content.decode()


def test_rate_limit_is_per_email(client):
    UserFactory(email="ana@escola.sp.gov.br")
    UserFactory(email="bruno@escola.sp.gov.br")
    for _ in range(5):
        client.post(LOGIN_URL, {"login": "ana@escola.sp.gov.br", "password": "errada"})

    client.post(LOGIN_URL, {"login": "bruno@escola.sp.gov.br", "password": DEFAULT_PASSWORD})

    assert "_auth_user_id" in client.session


@pytest.mark.parametrize(
    "url",
    [
        "/entrar/signup/",
        "/entrar/password/reset/",
        "/entrar/password/reset/done/",
        "/entrar/email/",
        "/entrar/3rdparty/",
        "/entrar/3rdparty/signup/",
        "/entrar/reauthenticate/",
    ],
)
def test_unused_allauth_pages_are_blocked(client, url):
    assert client.get(url).status_code == 404


def test_allauth_login_url_redirects_to_ours(client):
    response = client.get("/entrar/login/?next=/sobre/")

    assert response.status_code == 302
    assert response.url == "/entrar/?next=%2Fsobre%2F"


def test_admin_login_uses_our_login_page(client):
    response = client.get("/admin/", follow=False)
    assert response.status_code == 302

    response = client.get("/admin/login/?next=/admin/")

    assert response.url == "/entrar/?next=%2Fadmin%2F"


def test_logout_requires_post(client, staff_user):
    client.force_login(staff_user)

    get = client.get("/sair/")
    assert get.status_code == 200
    assert "_auth_user_id" in client.session

    post = client.post("/sair/")
    assert post.status_code == 302
    assert "_auth_user_id" not in client.session


def test_masthead_shows_enter_or_user(client, staff_user):
    anonymous = client.get("/").content.decode()
    assert 'href="/entrar/"' in anonymous

    client.force_login(staff_user)
    logged = client.get("/").content.decode()
    assert staff_user.public_name in logged
    assert 'action="/sair/"' in logged
    assert 'href="/admin/"' not in logged


def test_masthead_shows_admin_link_for_admin(admin_client):
    assert 'href="/admin/"' in admin_client.get("/").content.decode()


def test_session_settings(settings):
    assert settings.SESSION_COOKIE_AGE == 14 * 24 * 60 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
