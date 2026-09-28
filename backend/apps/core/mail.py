"""Envio de e-mail com a configuração do Django Admin ou do .env (Fase 4b, C1b; docs/35).

Ordem: a tela "E-mail de envio" do Django Admin, se estiver completa (servidor, porta, usuário
e senha); senão, as variáveis EMAIL_HOST_USER e EMAIL_HOST_PASSWORD do .env. Sem nenhuma das
duas, email_configured() é falso e o cadastro próprio some; no desenvolvimento os e-mails vão
para o terminal (EMAIL_FALLBACK_CONSOLE).

A senha da tela é cifrada com Fernet (AES + HMAC) usando uma chave derivada do SECRET_KEY. Se
o SECRET_KEY mudar (ex.: backup restaurado em outro servidor), a senha não abre mais e precisa
ser digitada de novo; o envio passa a usar o .env até lá.
"""

import base64
import hashlib
import logging
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

logger = logging.getLogger(__name__)

CACHE_KEY = "core:email-settings"


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"jornal-email:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(password: str) -> str:
    return _fernet().encrypt(password.encode()).decode() if password else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning("A senha do e-mail no admin não abre com o SECRET_KEY atual.")
        return ""


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool
    use_ssl: bool
    from_name: str
    source: str  # "admin" ou "env"

    @property
    def from_address(self) -> str:
        from .site_settings import get_setting

        name = (self.from_name or get_setting("site.name")).replace('"', "")
        return f'"{name}" <{self.username}>'


def clear_cache() -> None:
    cache.delete(CACHE_KEY)


def _from_admin() -> SMTPConfig | None:
    from .models import EmailSettings

    row = EmailSettings.objects.filter(pk=1).first()
    if row is None or not row.is_complete:
        return None
    password = decrypt(row.password_encrypted)
    if not password:
        return None
    return SMTPConfig(
        host=row.host,
        port=row.port,
        username=row.username,
        password=password,
        use_tls=row.security == row.Security.TLS,
        use_ssl=row.security == row.Security.SSL,
        from_name=row.from_name,
        source="admin",
    )


def _from_env() -> SMTPConfig | None:
    if not (settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD):
        return None
    return SMTPConfig(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=True,
        use_ssl=False,
        from_name="",
        source="env",
    )


def active_config() -> SMTPConfig | None:
    """A configuração em uso agora (a do admin tem prioridade), com cache."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached or None
    config = _from_admin() or _from_env()
    cache.set(CACHE_KEY, config or False, 300)
    return config


def email_configured() -> bool:
    """Há como mandar e-mail (inclui o console do desenvolvimento e o outbox dos testes)."""
    return bool(settings.EMAIL_FORCE_CONFIGURED or active_config())


def from_address() -> str:
    config = active_config()
    return config.from_address if config else settings.DEFAULT_FROM_EMAIL


class ConfiguredEmailBackend(BaseEmailBackend):
    """EMAIL_BACKEND de produção: abre a conexão SMTP com active_config() a cada envio, então
    uma mudança na tela vale sem reiniciar o site."""

    def __init__(self, fail_silently: bool = False, **kwargs) -> None:
        super().__init__(fail_silently=fail_silently)
        self.config = active_config()
        if self.config is None and settings.EMAIL_FALLBACK_CONSOLE:
            self.inner = get_connection(
                "django.core.mail.backends.console.EmailBackend", fail_silently=fail_silently
            )
        elif self.config is None:
            self.inner = None
        else:
            self.inner = smtp_backend(self.config, fail_silently=fail_silently)

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        if self.inner is None:
            if not self.fail_silently:
                raise RuntimeError("E-mail de envio não configurado (docs/35).")
            return 0
        if self.config is not None:
            for message in email_messages:
                if message.from_email in (None, settings.DEFAULT_FROM_EMAIL):
                    message.from_email = self.config.from_address
        return self.inner.send_messages(email_messages)


def smtp_backend(config: SMTPConfig, fail_silently: bool = False) -> SMTPBackend:
    return SMTPBackend(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        use_tls=config.use_tls,
        use_ssl=config.use_ssl,
        timeout=settings.EMAIL_TIMEOUT,
        fail_silently=fail_silently,
    )


def send_test(config: SMTPConfig, to: str) -> None:
    """Manda um e-mail de teste com a configuração dada. Levanta a exceção do servidor."""
    message = EmailMessage(
        "Teste do Jornal Escolar",
        "Se você recebeu este e-mail, o envio de códigos do jornal está funcionando.\n",
        config.from_address,
        [to],
        connection=smtp_backend(config),
    )
    message.send()
