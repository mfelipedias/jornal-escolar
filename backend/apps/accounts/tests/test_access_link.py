from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import AccessLink
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Uma-Senha-Boa-2026"


@pytest.fixture
def newcomer():
    return UserFactory(email="nova@professor.educacao.sp.gov.br", microsoft_only=True)


@pytest.fixture
def link(newcomer, admin_user):
    return services.create_access_link(newcomer, created_by=admin_user)


def url(link: AccessLink) -> str:
    return reverse("accounts:access_link", kwargs={"token": link.pk})


# --- service ---


def test_link_expires_in_seven_days(link):
    delta = link.expires_at - timezone.now()

    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7)
    assert link.status == AccessLink.Status.VALID


def test_purpose_depends_on_existing_password(newcomer):
    assert services.create_access_link(newcomer).purpose == AccessLink.Purpose.FIRST_ACCESS
    assert services.create_access_link(UserFactory()).purpose == AccessLink.Purpose.PASSWORD_RESET


def test_new_link_revokes_previous_unused(newcomer):
    first = services.create_access_link(newcomer)
    second = services.create_access_link(newcomer)

    first.refresh_from_db()
    assert first.status == AccessLink.Status.REVOKED
    assert second.status == AccessLink.Status.VALID


def test_inactive_user_gets_no_link():
    with pytest.raises(services.AccessLinkError):
        services.create_access_link(UserFactory(is_active=False))


def test_absolute_url_uses_site_url(link, settings):
    settings.SITE_URL = "https://jornal.projetosrosa.com.br"

    assert services.access_link_url(link) == f"https://jornal.projetosrosa.com.br/acesso/{link.pk}/"


# --- página ---


def test_valid_link_shows_form(client, link):
    response = client.get(url(link))

    assert response.status_code == 200
    assert response["Referrer-Policy"] == "no-referrer"
    assert "Criar senha e entrar" in response.content.decode()


def test_setting_password_logs_in_and_uses_link(client, link, newcomer):
    response = client.post(
        url(link), {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}
    )

    assert response.status_code == 302
    assert int(client.session["_auth_user_id"]) == newcomer.pk
    newcomer.refresh_from_db()
    assert newcomer.check_password(NEW_PASSWORD)
    link.refresh_from_db()
    assert link.status == AccessLink.Status.USED


def test_link_cannot_be_used_twice(client, link):
    client.post(url(link), {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
    client.logout()

    response = client.get(url(link))

    assert response.status_code == 410


def test_weak_password_is_rejected(client, link, newcomer):
    response = client.post(url(link), {"new_password1": "123456", "new_password2": "123456"})

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    link.refresh_from_db()
    assert link.status == AccessLink.Status.VALID
    newcomer.refresh_from_db()
    assert not newcomer.has_usable_password()


def test_mismatched_passwords_are_rejected(client, link):
    response = client.post(
        url(link), {"new_password1": NEW_PASSWORD, "new_password2": "Outra-Senha-2026"}
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_expired_link_is_refused(client, link):
    AccessLink.objects.filter(pk=link.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    response = client.get(url(link))

    assert response.status_code == 410
    assert "Peça um novo link" in response.content.decode()


def test_revoked_link_is_refused(client, link, newcomer):
    services.create_access_link(newcomer)

    assert client.get(url(link)).status_code == 410


def test_link_of_deactivated_user_is_refused(client, link, newcomer):
    services.deactivate_user(newcomer)

    assert client.get(url(link)).status_code == 410
    link.refresh_from_db()
    assert link.status == AccessLink.Status.REVOKED


def test_unknown_token_is_refused(client):
    response = client.get("/acesso/00000000-0000-0000-0000-000000000000/")

    assert response.status_code == 410


def test_new_password_works_on_login_page(client, link, newcomer):
    client.post(url(link), {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
    client.logout()

    client.post("/entrar/", {"login": newcomer.email, "password": NEW_PASSWORD})

    assert int(client.session["_auth_user_id"]) == newcomer.pk


# --- admin e comando ---


def test_admin_action_generates_links(admin_client, newcomer):
    response = admin_client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "generate_access_links", "_selected_action": [newcomer.pk]},
        follow=True,
    )

    link = AccessLink.objects.get(user=newcomer)
    assert f"/acesso/{link.pk}/" in response.content.decode()


def test_admin_deactivate_and_reactivate(admin_client, admin_user, newcomer):
    changelist = reverse("admin:accounts_user_changelist")

    admin_client.post(
        changelist, {"action": "deactivate_users", "_selected_action": [newcomer.pk, admin_user.pk]}
    )
    newcomer.refresh_from_db()
    admin_user.refresh_from_db()
    assert not newcomer.is_active
    assert newcomer.deactivated_at is not None
    assert admin_user.is_active  # não desativa a si mesmo

    admin_client.post(changelist, {"action": "reactivate_users", "_selected_action": [newcomer.pk]})
    newcomer.refresh_from_db()
    assert newcomer.is_active
    assert newcomer.deactivated_at is None


def test_access_link_admin_is_read_only(admin_client, link):
    assert admin_client.get(reverse("admin:accounts_accesslink_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:accounts_accesslink_add")).status_code == 403


def test_command_prints_link(capsys, newcomer):
    call_command("access_link", "NOVA@professor.educacao.sp.gov.br")

    link = AccessLink.objects.get(user=newcomer)
    assert f"/acesso/{link.pk}/" in capsys.readouterr().out


def test_command_unknown_email():
    with pytest.raises(CommandError):
        call_command("access_link", "ninguem@escola.sp.gov.br")
