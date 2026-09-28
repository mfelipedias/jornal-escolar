"""E-mail de envio configurado no Django Admin (Fase 4b, C1b; docs/35)."""

import smtplib

import pytest
from django.core import mail as django_mail
from django.core.mail import send_mail
from django.urls import reverse

from apps.core import mail
from apps.core.models import AuditLog, EmailSettings

pytestmark = pytest.mark.django_db

CHANGE = "/admin/core/emailsettings/1/change/"


def form_data(**overrides) -> dict:
    data = {
        "host": "smtp.gmail.com",
        "port": 587,
        "security": "tls",
        "username": "jornal.escola@gmail.com",
        "password": "abcd efgh ijkl mnop",
        "from_name": "",
    }
    data.update(overrides)
    return data


@pytest.fixture
def no_env(settings):
    settings.EMAIL_HOST_USER = ""
    settings.EMAIL_HOST_PASSWORD = ""
    settings.EMAIL_FORCE_CONFIGURED = False


def test_lista_abre_direto_a_tela_de_edicao(admin_client):
    response = admin_client.get(reverse("admin:core_emailsettings_changelist"))

    assert response.status_code == 302
    assert response.url == CHANGE
    page = admin_client.get(CHANGE).content.decode()
    assert "smtp.gmail.com" in page
    assert "Enviar e-mail de teste" in page


def test_salvar_cifra_a_senha_e_nunca_a_mostra(admin_client, no_env):
    admin_client.get(reverse("admin:core_emailsettings_changelist"))

    admin_client.post(CHANGE, form_data())

    row = EmailSettings.objects.get()
    assert row.password_encrypted
    assert "abcd" not in row.password_encrypted
    assert mail.decrypt(row.password_encrypted) == "abcdefghijklmnop"  # sem os espaços
    page = admin_client.get(CHANGE).content.decode()
    assert "abcdefghijklmnop" not in page
    assert "sim (escondida)" in page
    assert "Esta tela (jornal.escola@gmail.com)" in page
    log = AuditLog.objects.get(action=AuditLog.Action.SETTING_CHANGED)
    assert "senha trocada" in log.changes["campos"]
    assert "abcd" not in str(log.changes)


def test_senha_vazia_mantem_a_atual_e_apagar_desliga(admin_client, no_env):
    admin_client.get(reverse("admin:core_emailsettings_changelist"))
    admin_client.post(CHANGE, form_data())

    admin_client.post(CHANGE, form_data(password="", from_name="Jornal da Escola"))
    row = EmailSettings.objects.get()
    assert mail.decrypt(row.password_encrypted) == "abcdefghijklmnop"
    assert mail.active_config().from_address == '"Jornal da Escola" <jornal.escola@gmail.com>'

    admin_client.post(CHANGE, form_data(password="", clear_password="on"))
    assert EmailSettings.objects.get().password_encrypted == ""
    assert mail.active_config() is None
    assert mail.email_configured() is False


def test_tela_tem_prioridade_sobre_o_env(settings, no_env):
    settings.EMAIL_HOST_USER = "env@gmail.com"
    settings.EMAIL_HOST_PASSWORD = "senha-do-env"
    assert mail.active_config().source == "env"

    EmailSettings.objects.create(
        host="smtp.exemplo.org",
        port=465,
        security=EmailSettings.Security.SSL,
        username="tela@exemplo.org",
        password_encrypted=mail.encrypt("senha-da-tela"),
    )

    config = mail.active_config()
    assert config.source == "admin"
    assert (config.host, config.port, config.use_ssl, config.use_tls) == (
        "smtp.exemplo.org",
        465,
        True,
        False,
    )


def test_senha_cifrada_com_outro_secret_key_nao_abre(settings, no_env):
    EmailSettings.objects.create(username="a@b.org", password_encrypted=mail.encrypt("x"))
    settings.SECRET_KEY = "outro-secret-key-de-outro-servidor-1234567890"
    mail.clear_cache()

    assert mail.active_config() is None


def test_backend_usa_a_configuracao_da_tela(settings, monkeypatch, no_env):
    settings.EMAIL_BACKEND = "apps.core.mail.ConfiguredEmailBackend"
    EmailSettings.objects.create(
        username="tela@exemplo.org", password_encrypted=mail.encrypt("segredo")
    )
    sent = []

    class FakeSMTP:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def send_messages(self, messages):
            sent.append((self.kwargs, messages))
            return len(messages)

    monkeypatch.setattr(mail, "SMTPBackend", FakeSMTP)

    send_mail("Assunto", "Corpo", None, ["x@exemplo.org"])

    [(kwargs, [message])] = sent
    assert kwargs["username"] == "tela@exemplo.org"
    assert kwargs["password"] == "segredo"
    assert kwargs["use_tls"] is True
    assert message.from_email == '"Jornal Escolar" <tela@exemplo.org>'


def test_sem_configuracao_o_backend_recusa_ou_usa_o_console(settings, no_env):
    settings.EMAIL_BACKEND = "apps.core.mail.ConfiguredEmailBackend"
    with pytest.raises(RuntimeError, match="não configurado"):
        send_mail("A", "B", None, ["x@exemplo.org"])

    settings.EMAIL_FALLBACK_CONSOLE = True
    assert send_mail("A", "B", None, ["x@exemplo.org"]) == 1


def test_botao_de_teste_mostra_sucesso_ou_erro(admin_client, monkeypatch, no_env):
    admin_client.get(reverse("admin:core_emailsettings_changelist"))
    url = reverse("admin:core_emailsettings_test", args=[1])

    response = admin_client.post(url, follow=True)
    assert "Salve servidor, usuário e senha antes de testar" in response.content.decode()

    admin_client.post(CHANGE, form_data())
    calls = []
    monkeypatch.setattr(mail, "send_test", lambda config, to: calls.append(to))
    response = admin_client.post(url, {"to": "eu@exemplo.org"}, follow=True)
    assert calls == ["eu@exemplo.org"]
    assert "E-mail de teste enviado para eu@exemplo.org" in response.content.decode()

    def falha(config, to):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    monkeypatch.setattr(mail, "send_test", falha)
    response = admin_client.post(url, follow=True)
    assert "Username and Password not accepted" in response.content.decode()


def test_so_admin_mexe(client, editor_user):
    client.force_login(editor_user)

    assert client.get(CHANGE).status_code == 302  # vai para o login do admin


def test_cadastro_aparece_quando_a_tela_e_preenchida(client, no_env):
    assert "Criar conta" not in client.get("/entrar/").content.decode()

    EmailSettings.objects.create(username="a@b.org", password_encrypted=mail.encrypt("x"))

    assert "Criar conta" in client.get("/entrar/").content.decode()
    assert len(django_mail.outbox) == 0
