"""'Esqueci minha senha' com código por e-mail (Fase 4b, C3).

Aceite: código de outra pessoa ou vencido não troca a senha.
"""

import re
from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailCode
from apps.core.models import AuditLog
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

START = "/entrar/esqueci/"
CONFIRM = "/entrar/esqueci/confirmar/"
NEW = "nova-senha-da-horta-2026"


@pytest.fixture
def ana():
    user = UserFactory(email="ana@professor.educacao.sp.gov.br", full_name="Ana Lima")
    user.set_password("senha-antiga-da-ana-1")
    user.save()
    return user


def last_code() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def confirm(client, code: str, password: str = NEW):
    return client.post(
        CONFIRM, {"code": code, "new_password1": password, "new_password2": password}
    )


def test_fluxo_completo_troca_a_senha_e_entra(client, ana):
    response = client.post(START, {"email": "ANA@professor.educacao.sp.gov.br"})
    assert response.url == CONFIRM
    assert "nova senha" in mail.outbox[-1].subject

    response = confirm(client, last_code())

    assert response.url == reverse("dashboard:home")
    ana.refresh_from_db()
    assert ana.check_password(NEW)
    assert int(client.session["_auth_user_id"]) == ana.pk
    assert AuditLog.objects.filter(action=AuditLog.Action.PASSWORD_RESET).count() == 1
    # O código foi gasto e não serve de novo.
    assert EmailCode.objects.get().used_at is not None


def test_email_sem_conta_tem_a_mesma_resposta_e_nao_recebe_nada(client):
    response = client.post(START, {"email": "ninguem@professor.educacao.sp.gov.br"})

    assert response.status_code == 302
    assert response.url == CONFIRM
    assert not mail.outbox


def test_conta_desativada_nao_recebe_codigo(client, ana):
    ana.is_active = False
    ana.save()

    client.post(START, {"email": ana.email})

    assert not mail.outbox


def test_codigo_de_outra_pessoa_nao_troca_a_senha(client, ana):
    """Aceite da C3."""
    bruno = UserFactory(email="bruno@prof.educacao.sp.gov.br")
    other = Client()
    other.post(START, {"email": bruno.email})
    bruno_code = last_code()

    client.post(START, {"email": ana.email})
    ana_code = last_code()
    if bruno_code != ana_code:
        assert confirm(client, bruno_code).status_code == 400
        ana.refresh_from_db()
        assert ana.check_password("senha-antiga-da-ana-1")


def test_codigo_vencido_nao_troca_a_senha(client, ana):
    """Aceite da C3."""
    client.post(START, {"email": ana.email})
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    response = confirm(client, last_code())

    assert response.status_code == 400
    ana.refresh_from_db()
    assert ana.check_password("senha-antiga-da-ana-1")


def test_cinco_erros_invalidam_o_codigo(client, ana):
    client.post(START, {"email": ana.email})
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        confirm(client, wrong)

    assert confirm(client, code).status_code == 400
    ana.refresh_from_db()
    assert ana.check_password("senha-antiga-da-ana-1")


def test_trocar_a_senha_derruba_as_outras_sessoes(client, ana):
    elsewhere = Client()
    elsewhere.force_login(ana)
    assert Session.objects.count() == 1

    client.post(START, {"email": ana.email})
    confirm(client, last_code())

    assert elsewhere.get(reverse("dashboard:home")).status_code == 302  # foi para o login


def test_senha_parecida_com_o_email_e_recusada(client, ana):
    client.post(START, {"email": ana.email})

    response = confirm(client, "ana@professor.educacao.sp.gov.br")

    assert response.status_code == 400


def test_confirmar_sem_o_passo_1_volta(client):
    assert client.get(CONFIRM).url == START


def test_tela_de_entrar_mostra_o_link_quando_ha_email(client, settings):
    assert "Esqueci minha senha" in client.get("/entrar/").content.decode()

    settings.EMAIL_FORCE_CONFIGURED = False
    settings.EMAIL_HOST_USER = ""
    html = client.get("/entrar/").content.decode()
    assert "Esqueci minha senha" not in html
    assert "Fale com o administrador" in html
    assert client.get(START).status_code == 404
