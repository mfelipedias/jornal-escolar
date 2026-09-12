from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.site_settings import get_setting

from .models import AccessLink, TeacherProfile, User, normalize_email

# --- Login Microsoft (E09) ---


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


# --- Perfil (E10) ---


def unique_profile_slug(name: str, *, exclude_pk: int | None = None) -> str:
    base = slugify(name)[:80] or "perfil"
    slug, n = base, 2
    others = TeacherProfile.objects.exclude(pk=exclude_pk)
    while others.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def ensure_profile(user: User) -> TeacherProfile:
    """Todo usuário tem um perfil; o endereço nasce do nome e não muda sozinho depois."""
    try:
        return user.profile
    except TeacherProfile.DoesNotExist:
        return TeacherProfile.objects.create(user=user, slug=unique_profile_slug(user.public_name))


# --- Links de acesso (E10) ---


class AccessLinkError(Exception):
    pass


@transaction.atomic
def create_access_link(
    user: User,
    *,
    created_by: User | None = None,
    purpose: str | None = None,
) -> AccessLink:
    """Gera um link novo e cancela os anteriores ainda não usados da mesma pessoa."""
    if not user.is_active:
        raise AccessLinkError("Conta desativada: reative antes de gerar um link.")
    if purpose is None:
        purpose = (
            AccessLink.Purpose.PASSWORD_RESET
            if user.has_usable_password()
            else AccessLink.Purpose.FIRST_ACCESS
        )
    now = timezone.now()
    AccessLink.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).update(
        revoked_at=now
    )
    return AccessLink.objects.create(user=user, purpose=purpose, created_by=created_by)


def access_link_url(link: AccessLink) -> str:
    return urljoin(settings.SITE_URL.rstrip("/") + "/", link.get_absolute_url().lstrip("/"))


@transaction.atomic
def use_access_link(link: AccessLink, raw_password: str) -> User:
    """Define a senha e invalida o link. Chamar só com a senha já validada pelo formulário."""
    link = AccessLink.objects.select_for_update().select_related("user").get(pk=link.pk)
    if not link.is_valid:
        raise AccessLinkError("Link inválido.")
    user = link.user
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    link.used_at = timezone.now()
    link.save(update_fields=["used_at"])
    return user


# --- Ativação de contas (E10) ---


def deactivate_user(user: User) -> None:
    user.is_active = False
    user.deactivated_at = timezone.now()
    user.save(update_fields=["is_active", "deactivated_at"])
    AccessLink.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).update(
        revoked_at=user.deactivated_at
    )


def reactivate_user(user: User) -> None:
    user.is_active = True
    user.deactivated_at = None
    user.save(update_fields=["is_active", "deactivated_at"])
