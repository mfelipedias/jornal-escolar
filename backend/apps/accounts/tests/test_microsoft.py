import pytest
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from apps.accounts import adapters, services
from apps.accounts.models import User
from apps.core.models import SiteSetting
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def microsoft_configured(settings):
    settings.MICROSOFT_LOGIN_CONFIGURED = True
    settings.SOCIALACCOUNT_PROVIDERS = {
        "microsoft": {
            "TENANT": "organizations",
            "APPS": [{"client_id": "id-teste", "secret": "segredo-teste", "settings": {}}],
        }
    }
    settings.AUTH_ALLOWED_DOMAINS = ["professor.educacao.sp.gov.br", "educacao.sp.gov.br"]


@pytest.fixture
def request_():
    request = RequestFactory().get("/entrar/microsoft/login/callback/")
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    request.user = AnonymousUser()
    return request


def make_sociallogin(upn: str, mail: str | None = None, uid: str = "ms-1") -> SocialLogin:
    extra = {"userPrincipalName": upn, "mail": mail if mail is not None else upn, "id": uid}
    account = SocialAccount(provider="microsoft", uid=uid, extra_data=extra)
    return SocialLogin(user=User(email=mail or upn), account=account)


def run(request, sociallogin):
    adapters.SocialAccountAdapter().pre_social_login(request, sociallogin)


def rejected_message(request) -> str:
    return " ".join(str(m) for m in request._messages)


# --- regras de e-mail ---


def test_verified_email_uses_upn_not_mail():
    extra = {"userPrincipalName": "Ana@Professor.Educacao.SP.gov.br", "mail": "outra@x.com"}

    assert services.microsoft_verified_email(extra) == "ana@professor.educacao.sp.gov.br"


def test_guest_accounts_are_ignored():
    extra = {"userPrincipalName": "ana_gmail.com#EXT#@tenant.onmicrosoft.com"}

    assert services.microsoft_verified_email(extra) == ""


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("ana@professor.educacao.sp.gov.br", True),
        ("ANA@EDUCACAO.SP.GOV.BR", True),
        ("ana@gmail.com", False),
        ("ana@falso-professor.educacao.sp.gov.br.evil.com", False),
        ("sem-arroba", False),
    ],
)
def test_email_domain_allowed(email, allowed):
    assert services.email_domain_allowed(email) is allowed


# --- adaptador ---


def test_registered_user_is_connected(request_):
    user = UserFactory(email="ana@professor.educacao.sp.gov.br")
    sociallogin = make_sociallogin("Ana@professor.educacao.sp.gov.br")

    run(request_, sociallogin)

    assert sociallogin.user == user
    assert SocialAccount.objects.filter(user=user, provider="microsoft", uid="ms-1").exists()


def test_unregistered_user_is_rejected(request_):
    with pytest.raises(ImmediateHttpResponse) as exc:
        run(request_, make_sociallogin("novo@professor.educacao.sp.gov.br"))

    assert exc.value.response.url == "/entrar/"
    assert adapters.MSG_NOT_REGISTERED in rejected_message(request_)
    assert not User.objects.filter(email="novo@professor.educacao.sp.gov.br").exists()


def test_other_domain_is_rejected_even_if_registered(request_):
    UserFactory(email="ana@gmail.com")

    with pytest.raises(ImmediateHttpResponse):
        run(request_, make_sociallogin("ana@gmail.com"))

    assert adapters.MSG_DOMAIN in rejected_message(request_)


def test_forged_mail_attribute_cannot_take_over_account(request_):
    """Uma organização Microsoft qualquer pode pôr o e-mail de um professor no campo 'mail'."""
    UserFactory(email="ana@professor.educacao.sp.gov.br")
    forged = make_sociallogin(
        "hacker@evil.onmicrosoft.com", mail="ana@professor.educacao.sp.gov.br"
    )

    with pytest.raises(ImmediateHttpResponse):
        run(request_, forged)

    assert not SocialAccount.objects.exists()


def test_inactive_user_is_rejected(request_):
    UserFactory(email="ana@professor.educacao.sp.gov.br", is_active=False)

    with pytest.raises(ImmediateHttpResponse):
        run(request_, make_sociallogin("ana@professor.educacao.sp.gov.br"))

    assert adapters.MSG_INACTIVE in rejected_message(request_)


def test_disabled_setting_rejects(request_):
    UserFactory(email="ana@professor.educacao.sp.gov.br")
    SiteSetting.objects.create(key="auth.microsoft_enabled", value=False)

    with pytest.raises(ImmediateHttpResponse):
        run(request_, make_sociallogin("ana@professor.educacao.sp.gov.br"))

    assert adapters.MSG_DISABLED in rejected_message(request_)


def test_not_configured_rejects(request_, settings):
    settings.MICROSOFT_LOGIN_CONFIGURED = False
    UserFactory(email="ana@professor.educacao.sp.gov.br")

    with pytest.raises(ImmediateHttpResponse):
        run(request_, make_sociallogin("ana@professor.educacao.sp.gov.br"))


def test_existing_link_to_same_user_passes(request_):
    user = UserFactory(email="ana@professor.educacao.sp.gov.br")
    SocialAccount.objects.create(user=user, provider="microsoft", uid="ms-1", extra_data={})
    sociallogin = make_sociallogin("ana@professor.educacao.sp.gov.br")
    sociallogin.user = user
    sociallogin.account = SocialAccount.objects.get(uid="ms-1")
    sociallogin.account.extra_data = {"userPrincipalName": "ana@professor.educacao.sp.gov.br"}

    run(request_, sociallogin)


def test_existing_link_to_other_user_is_rejected(request_):
    ana = UserFactory(email="ana@professor.educacao.sp.gov.br")
    bruno = UserFactory(email="bruno@professor.educacao.sp.gov.br")
    SocialAccount.objects.create(user=bruno, provider="microsoft", uid="ms-9", extra_data={})
    sociallogin = make_sociallogin(ana.email, uid="ms-9")
    sociallogin.user = bruno
    sociallogin.account = SocialAccount.objects.get(uid="ms-9")
    sociallogin.account.extra_data = {"userPrincipalName": ana.email}

    with pytest.raises(ImmediateHttpResponse):
        run(request_, sociallogin)


def test_signup_is_always_closed(request_):
    assert adapters.AccountAdapter().is_open_for_signup(request_) is False
    assert adapters.SocialAccountAdapter().is_open_for_signup(request_, None) is False
