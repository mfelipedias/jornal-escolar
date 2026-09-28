"""Contas do cadastro próprio aguardando aprovação (Fase 4b, C2).

Aceite: conta pendente não cria rascunho; aprovada passa a criar.
"""

import re

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts import approval
from apps.accounts.models import User
from apps.accounts.services import ensure_profile
from apps.core.models import AuditLog
from apps.dashboard.menu import menu_items
from apps.editorial import permissions
from apps.editorial.models import Notification
from apps.publications.models import Article
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def pending():
    user = UserFactory(full_name="Ana Lima", email="ana@professor.educacao.sp.gov.br")
    user.is_approved = False
    user.save()
    ensure_profile(user)
    return user


@pytest.fixture
def editor():
    return UserFactory(editor=True, full_name="Carla Editora")


def test_conta_pendente_nao_cria_rascunho_e_aprovada_cria(client, pending, editor):
    """Aceite da C2."""
    client.force_login(pending)
    assert not permissions.can_create_article(pending)

    response = client.post(reverse("publications:create"), {"title": "Oi"})
    assert response.status_code == 403
    assert not Article.objects.exists()

    approval.approve(editor, pending)
    pending.refresh_from_db()

    assert permissions.can_create_article(pending)
    assert client.get(reverse("publications:create")).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "/painel/",
        "/painel/publicacoes/",
        "/painel/sugestoes/",
        "/painel/pautas/",
        "/painel/revisao/",
    ],
)
def test_painel_leva_a_tela_de_espera(client, pending, url):
    client.force_login(pending)

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("accounts:pending")


def test_pedido_htmx_ou_post_do_painel_recebe_403(client, pending):
    client.force_login(pending)

    assert client.get("/x/users/search/?q=an", **HX).status_code == 403
    assert client.post("/x/media/").status_code == 403


def test_pendente_usa_perfil_conta_avisos_e_o_site(client, pending):
    client.force_login(pending)

    for name in ("accounts:profile_edit", "accounts:account_settings", "accounts:pending"):
        assert client.get(reverse(name)).status_code == 200
    assert client.get(reverse("accounts:onboarding", kwargs={"step": 1})).status_code == 200
    assert client.get(reverse("editorial:notifications")).status_code == 200
    assert client.get("/").status_code == 200
    html = client.get(reverse("accounts:pending")).content.decode()
    assert "aguardando a aprovação" in html
    assert "Escrever" not in html


def test_menu_da_conta_pendente_so_tem_o_que_ela_usa(pending):
    keys = [item.key for item in menu_items(pending)]

    assert keys == ["home", "profile", "account", "site"]


def test_fim_do_assistente_leva_a_tela_de_espera(client, pending):
    client.force_login(pending)

    response = client.post(reverse("accounts:onboarding_done"))

    assert response.url == reverse("accounts:pending")


def test_perfil_da_conta_pendente_nao_aparece_no_site(client, pending):
    slug = pending.profile.slug

    assert client.get(f"/professores/{slug}/").status_code == 404
    assert pending.full_name not in client.get("/professores/").content.decode()

    pending.is_approved = True
    pending.save()
    assert client.get(f"/professores/{slug}/").status_code == 200


def test_cadastro_avisa_editores_e_admin(client, editor):
    admin = UserFactory(admin=True)
    staff = UserFactory()
    client.post("/cadastro/", {"full_name": "Bruno Reis", "email": "bruno@prof.educacao.sp.gov.br"})
    code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
    client.post(
        "/cadastro/confirmar/",
        {"code": code, "new_password1": "horta-2026-escola", "new_password2": "horta-2026-escola"},
    )

    notices = Notification.objects.filter(kind=Notification.Kind.ACCOUNT_PENDING)
    assert {n.user for n in notices} == {editor, admin}
    assert not notices.filter(user=staff).exists()
    assert "Bruno Reis (bruno@prof.educacao.sp.gov.br) criou uma conta" in notices.first().message


def test_editor_aprova_pela_fila_e_a_pessoa_e_avisada(client, pending, editor):
    approval.notify_new_signup(pending)
    client.force_login(editor)
    page = client.get(reverse("editorial:accounts")).content.decode()
    assert "ana@professor.educacao.sp.gov.br" in page

    response = client.post(
        reverse("editorial:account_action", args=[pending.pk, "aprovar"]), follow=True
    )

    assert "Conta de Ana Lima aprovada" in response.content.decode()
    pending.refresh_from_db()
    assert pending.is_approved
    assert Notification.objects.filter(
        user=pending, kind=Notification.Kind.ACCOUNT_APPROVED
    ).exists()
    # O aviso "aguarda aprovação" sai do sino do editor.
    assert not Notification.objects.filter(
        user=editor, kind=Notification.Kind.ACCOUNT_PENDING, read_at__isnull=True
    ).exists()
    assert AuditLog.objects.filter(action=AuditLog.Action.USER_APPROVED).count() == 1


def test_aprovar_manda_email(pending, editor, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        approval.approve(editor, pending)

    [message] = mail.outbox
    assert message.to == [pending.email]
    assert "foi aprovada" in message.subject


def test_recusar_apaga_a_conta_e_libera_o_email(client, pending, editor):
    client.force_login(editor)

    client.post(reverse("editorial:account_action", args=[pending.pk, "recusar"]))

    assert not User.objects.filter(email="ana@professor.educacao.sp.gov.br").exists()
    log = AuditLog.objects.get(action=AuditLog.Action.USER_REJECTED)
    assert log.changes == {"dominio": "professor.educacao.sp.gov.br"}


def test_so_editor_e_admin_aprovam(client, pending):
    staff = UserFactory()
    client.force_login(staff)

    assert client.get(reverse("editorial:accounts")).status_code == 403
    with pytest.raises(PermissionDenied):
        approval.approve(staff, pending)
    with pytest.raises(PermissionDenied):
        approval.reject(pending, pending)


def test_menu_e_visao_geral_mostram_contas_esperando(client, pending, editor):
    item = next(i for i in menu_items(editor) if i.key == "editorial")
    assert item.count == 1

    client.force_login(editor)
    html = client.get(reverse("editorial:overview")).content.decode()
    assert "1 conta nova aguardando aprovação" in html


def test_admin_aprova_pela_acao_do_django_admin(admin_client, pending):
    admin_client.post(
        reverse("admin:accounts_user_changelist"),
        {"action": "approve_users", "_selected_action": [pending.pk]},
    )

    pending.refresh_from_db()
    assert pending.is_approved
