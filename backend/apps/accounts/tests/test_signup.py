"""Cadastro próprio com código por e-mail (Fase 4b, C1; docs/27 quinta rodada).

Aceite: e-mail de outro domínio é recusado; código errado 5 vezes invalida; quem já tem conta
não descobre isso pela tela.
"""

import re
from io import StringIO

import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.accounts import signup
from apps.accounts.models import EmailCode, User
from apps.core.models import AuditLog, SiteSetting
from apps.core.site_settings import clear_cache
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SIGNUP = "/cadastro/"
CONFIRM = "/cadastro/confirmar/"
EMAIL = "ana.lima@professor.educacao.sp.gov.br"
PASSWORD = "horta-da-escola-2026"


def last_code() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def start(client, email: str = EMAIL, name: str = "Ana Lima"):
    return client.post(SIGNUP, {"full_name": name, "email": email})


def confirm(client, code: str, password: str = PASSWORD):
    return client.post(
        CONFIRM, {"code": code, "new_password1": password, "new_password2": password}
    )


def test_fluxo_completo_cria_conta_pendente_e_leva_ao_assistente(client):
    response = start(client, "Ana.Lima@Professor.Educacao.SP.gov.br")
    assert response.status_code == 302
    assert response.url == CONFIRM
    [message] = mail.outbox
    assert message.to == [EMAIL]
    assert "Seu código para criar a conta" in message.subject
    code = last_code()
    assert code not in EmailCode.objects.get().code_hash  # só o hash fica no banco

    page = client.get(CONFIRM).content.decode()
    assert EMAIL in page

    response = confirm(client, code)

    assert response.status_code == 302
    assert response.url == reverse("accounts:onboarding", kwargs={"step": 1})
    user = User.objects.get(email=EMAIL)
    assert user.full_name == "Ana Lima"
    assert user.is_approved is False
    assert user.role == User.Role.STAFF
    assert user.staff_kind == User.StaffKind.TEACHER
    assert user.check_password(PASSWORD)
    assert user.profile is not None
    assert int(client.session["_auth_user_id"]) == user.pk
    assert AuditLog.objects.filter(action=AuditLog.Action.USER_SIGNED_UP).count() == 1
    # O código não serve duas vezes.
    assert EmailCode.objects.get().used_at is not None


@pytest.mark.parametrize(
    "email",
    ["ana@gmail.com", "ana@educacao.sp.gov.br", "ana@al.educacao.sp.gov.br", "ana@prof.com"],
)
def test_outros_dominios_sao_recusados(client, email):
    response = start(client, email)

    assert response.status_code == 400
    assert "Use o seu e-mail institucional" in response.content.decode()
    assert not mail.outbox


def test_dominio_prof_e_aceito(client):
    start(client, "bruno@prof.educacao.sp.gov.br")

    assert len(mail.outbox) == 1


def test_codigo_errado_cinco_vezes_invalida(client):
    start(client)
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        response = confirm(client, wrong)
        assert response.status_code == 400
        assert "Código incorreto ou vencido" in response.content.decode()

    response = confirm(client, code)  # o certo, tarde demais
    assert response.status_code == 400
    assert not User.objects.filter(email=EMAIL).exists()


def test_codigo_vencido_nao_vale(client):
    from datetime import timedelta

    from django.utils import timezone

    start(client)
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    assert confirm(client, last_code()).status_code == 400
    assert not User.objects.filter(email=EMAIL).exists()


def test_pedir_de_novo_invalida_o_codigo_anterior(client):
    start(client)
    first = last_code()
    start(client)
    second = last_code()

    if first != second:
        assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 302


def test_quem_ja_tem_conta_nao_descobre_pela_tela(client):
    UserFactory(email=EMAIL, full_name="Ana Lima")
    novo = client.post(SIGNUP, {"full_name": "X Y Z", "email": "novo@professor.educacao.sp.gov.br"})

    existente = start(client)

    # Mesma resposta nos dois casos.
    assert existente.status_code == novo.status_code == 302
    assert existente.url == novo.url == CONFIRM
    # A pessoa recebe um lembrete no e-mail, sem código.
    lembrete = mail.outbox[-1]
    assert lembrete.to == [EMAIL]
    assert "já tem conta" in lembrete.subject
    assert not re.search(r"\b\d{6}\b", lembrete.body)
    assert not EmailCode.objects.filter(email=EMAIL).exists()


def test_senha_fraca_ou_diferente_e_recusada(client):
    start(client)
    code = last_code()

    fraca = confirm(client, code, "123")
    assert fraca.status_code == 400
    diferente = client.post(
        CONFIRM, {"code": code, "new_password1": PASSWORD, "new_password2": PASSWORD + "x"}
    )
    assert diferente.status_code == 400
    assert not User.objects.filter(email=EMAIL).exists()


def test_campo_isca_finge_sucesso_e_nao_envia(client):
    response = client.post(
        SIGNUP, {"full_name": "Robô", "email": EMAIL, "website": "http://spam.example"}
    )

    assert response.status_code == 302
    assert not mail.outbox


def test_limite_de_pedidos_por_email(client):
    for _ in range(signup.CODES_PER_EMAIL_PER_HOUR):
        assert start(client).status_code == 302

    response = start(client)

    assert response.status_code == 429
    assert "Muitos pedidos seguidos" in response.content.decode()
    assert len(mail.outbox) == signup.CODES_PER_EMAIL_PER_HOUR


def test_confirmar_sem_passar_pelo_passo_1_volta_ao_inicio(client):
    response = client.get(CONFIRM)

    assert response.status_code == 302
    assert response.url == SIGNUP


def test_logado_vai_para_o_painel(client, staff_user):
    client.force_login(staff_user)

    assert client.get(SIGNUP).url == reverse("dashboard:home")


def test_cadastro_desligado_ou_sem_email_some(client, settings):
    setting = SiteSetting.objects.create(key="auth.self_signup", value=False)
    assert client.get(SIGNUP).status_code == 404
    assert "Criar conta" not in client.get("/entrar/").content.decode()

    setting.value = True
    setting.save()
    clear_cache()
    settings.EMAIL_FORCE_CONFIGURED = False
    assert client.get(SIGNUP).status_code == 404

    settings.EMAIL_FORCE_CONFIGURED = True
    assert "Criar conta" in client.get("/entrar/").content.decode()


def test_contas_criadas_pelo_admin_nascem_aprovadas():
    assert User.objects.create_user("x@escola.org").is_approved is True


def test_limpeza_apaga_codigos_vencidos(client):
    from datetime import timedelta

    from django.utils import timezone

    start(client)
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(days=8))

    assert signup.purge_old_codes() == 1


def test_comando_de_teste_do_email(settings):
    out = StringIO()
    call_command("send_test_email", "eu@exemplo.org", stdout=out)
    assert mail.outbox[-1].to == ["eu@exemplo.org"]
    assert "enviado" in out.getvalue()

    settings.EMAIL_FORCE_CONFIGURED = False
    with pytest.raises(CommandError, match="E-mail não configurado"):
        call_command("send_test_email", "eu@exemplo.org")
