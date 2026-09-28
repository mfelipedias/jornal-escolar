"""Cadastro próprio com código por e-mail (Fase 4b, C1; docs/27 quinta rodada, docs/23).

1. A pessoa informa nome e e-mail institucional (só SIGNUP_ALLOWED_DOMAINS).
2. Recebe um código de 6 dígitos, que vale 15 minutos e aceita 5 tentativas erradas.
3. Digita o código e cria a senha: a conta nasce "aguardando aprovação" (is_approved=False)
   e a pessoa entra direto no assistente de primeiro acesso.

A tela responde sempre a mesma coisa depois do passo 1, exista ou não conta com aquele e-mail:
quem já tem conta recebe no e-mail um lembrete para usar "Esqueci minha senha", e ninguém
descobre pela tela quem está cadastrado.

Guardamos só o hash do código (HMAC com o SECRET_KEY), nunca o código.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.core import audit, mail
from apps.core.ratelimit import hit
from apps.core.site_settings import get_setting

from . import services
from .models import EmailCode, User, normalize_email

Purpose = EmailCode.Purpose

# Limites de pedidos de código (docs/23): por e-mail e por IP, a cada hora.
CODES_PER_EMAIL_PER_HOUR = 3
CODES_PER_IP_PER_HOUR = 10
# Tentativas de digitar o código por IP, a cada 15 minutos (além das 5 por código).
CHECKS_PER_IP = 30
CODE_DIGITS = 6

MSG_DOMAIN = "Use o seu e-mail institucional (@{domains})."
MSG_WRONG_CODE = "Código incorreto ou vencido. Confira o e-mail mais recente ou peça outro."
MSG_TOO_MANY = "Muitos pedidos seguidos. Espere alguns minutos e tente de novo."


class RateLimited(Exception):
    pass


def signup_available() -> bool:
    """O cadastro só aparece com e-mail configurado e ligado nas configurações."""
    return mail.email_configured() and bool(get_setting("auth.self_signup"))


def password_reset_available() -> bool:
    return mail.email_configured()


def domain_allowed(email: str) -> bool:
    _, _, domain = normalize_email(email).rpartition("@")
    return bool(domain) and domain in settings.SIGNUP_ALLOWED_DOMAINS


def domain_message() -> str:
    return MSG_DOMAIN.format(domains=" ou @".join(settings.SIGNUP_ALLOWED_DOMAINS))


def _hash(email: str, purpose: str, code: str) -> str:
    message = f"{purpose}:{normalize_email(email)}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def _limit(request: HttpRequest | None, email: str, purpose: str) -> None:
    ip = audit.client_ip(request) or "sem-ip"
    per_email = hit(f"code:{purpose}:{email}", limit=CODES_PER_EMAIL_PER_HOUR, period=3600)
    per_ip = hit(f"code-ip:{ip}", limit=CODES_PER_IP_PER_HOUR, period=3600)
    if not (per_email and per_ip):
        raise RateLimited(MSG_TOO_MANY)


def issue_code(email: str, purpose: str, full_name: str = "") -> str:
    """Cria um código novo e invalida os anteriores do mesmo e-mail e finalidade."""
    email = normalize_email(email)
    now = timezone.now()
    EmailCode.objects.filter(email=email, purpose=purpose, used_at__isnull=True).update(used_at=now)
    code = _new_code()
    EmailCode.objects.create(
        email=email,
        purpose=purpose,
        full_name=full_name[:150],
        code_hash=_hash(email, purpose, code),
    )
    return code


def send_email(to: str, template: str, context: dict) -> None:
    """E-mail em texto simples. Primeira linha do template = assunto."""
    context = {
        "site_name": get_setting("site.name"),
        "site_url": settings.SITE_URL,
        **context,
    }
    subject, _, body = render_to_string(f"emails/{template}.txt", context).partition("\n")
    send_mail(subject.strip(), body.strip() + "\n", mail.from_address(), [to])


def request_signup(email: str, full_name: str, request: HttpRequest | None = None) -> None:
    """Passo 1. Levanta ValidationError (domínio) ou RateLimited; senão, sempre "enviado"."""
    email = normalize_email(email)
    full_name = " ".join(full_name.split())
    if not domain_allowed(email):
        raise ValidationError({"email": domain_message()})
    _limit(request, email, Purpose.SIGNUP)
    existing = User.objects.filter(email=email).first()
    if existing is not None:
        if existing.is_active:
            send_email(
                email,
                "account_exists",
                {"name": existing.public_name, "login_url": _absolute("accounts:login")},
            )
        return
    code = issue_code(email, Purpose.SIGNUP, full_name)
    send_email(email, "signup_code", {"name": full_name, "code": code, "minutes": 15})


def _absolute(name: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{reverse(name)}"


def check_code(
    email: str, purpose: str, code: str, request: HttpRequest | None = None
) -> EmailCode:
    """Confere o código mais recente. Cada erro gasta uma tentativa; 5 erros invalidam."""
    email = normalize_email(email)
    ip = audit.client_ip(request) or "sem-ip"
    if not hit(f"code-check:{ip}", limit=CHECKS_PER_IP, period=900):
        raise RateLimited(MSG_TOO_MANY)
    record = EmailCode.objects.filter(email=email, purpose=purpose).first()
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if record is None or not record.is_valid:
        raise ValidationError({"code": MSG_WRONG_CODE})
    if not hmac.compare_digest(record.code_hash, _hash(email, purpose, code)):
        EmailCode.objects.filter(pk=record.pk).update(attempts=record.attempts + 1)
        raise ValidationError({"code": MSG_WRONG_CODE})
    return record


def provisional_user(email: str, full_name: str = "") -> User:
    """Usuário não salvo, só para os validadores de senha (similaridade com nome e e-mail)."""
    return User(email=normalize_email(email), full_name=full_name)


def complete_signup(
    email: str, code: str, password: str, request: HttpRequest | None = None
) -> User:
    """Passo 3: confere o código, cria a conta aguardando aprovação e o perfil.

    A conferência fica fora da transação: a tentativa errada precisa ficar gravada mesmo
    quando o erro sobe (senão o limite de 5 tentativas nunca valeria)."""
    record = check_code(email, Purpose.SIGNUP, code, request)
    validate_password(password, provisional_user(record.email, record.full_name))
    with transaction.atomic():
        record = EmailCode.objects.select_for_update().get(pk=record.pk)
        if not record.is_valid:
            raise ValidationError({"code": MSG_WRONG_CODE})
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    record.email,
                    password,
                    full_name=record.full_name or record.email.split("@")[0],
                    staff_kind=User.StaffKind.TEACHER,
                    is_approved=False,
                )
        except IntegrityError as exc:  # alguém criou a mesma conta no meio do caminho
            raise ValidationError({"code": MSG_WRONG_CODE}) from exc
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        services.ensure_profile(user)
        audit.record(
            audit.Action.USER_SIGNED_UP,
            actor=None,
            target=user,
            changes={"dominio": user.email.rpartition("@")[2]},
            request=request,
        )
    return user


def purge_old_codes(days: int = 7) -> int:
    """Códigos usados ou vencidos há mais de uma semana somem (entra no cleanup diário)."""
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = EmailCode.objects.filter(expires_at__lt=cutoff).delete()
    return deleted
