from typing import Any

from django.conf import settings

from apps.core.site_settings import get_setting

from .models import User, normalize_email


def microsoft_login_enabled() -> bool:
    """Botão da Microsoft disponível: credenciais no servidor e configuração ligada."""
    return settings.MICROSOFT_LOGIN_CONFIGURED and bool(get_setting("auth.microsoft_enabled"))


def email_domain_allowed(email: str) -> bool:
    _, _, domain = normalize_email(email).rpartition("@")
    return bool(domain) and domain in settings.AUTH_ALLOWED_DOMAINS


def microsoft_verified_email(extra_data: dict[str, Any]) -> str:
    """E-mail confiável de uma conta Microsoft: o userPrincipalName.

    O campo "mail" pode ser preenchido livremente pelo administrador de qualquer
    organização Microsoft; o userPrincipalName só aceita domínios verificados da
    organização da conta. Por isso nunca usamos "mail" para achar o usuário.
    Contas convidadas ("#EXT#") não servem.
    """
    upn = normalize_email(str(extra_data.get("userPrincipalName") or ""))
    if "#ext#" in upn:
        return ""
    return upn


def find_staff_account(email: str) -> User | None:
    """Conta pré-cadastrada pelo admin para este e-mail, se existir."""
    if not email:
        return None
    return User.objects.filter(email=normalize_email(email)).first()
