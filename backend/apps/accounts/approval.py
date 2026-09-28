"""Aprovação das contas do cadastro próprio (Fase 4b, C2; docs/27 quinta rodada).

- Ao se cadastrar, editores e admin recebem um aviso no sino.
- Aprovar: a conta passa a escrever e publicar; a pessoa recebe aviso no sino e e-mail.
- Recusar: a conta é apagada (ainda não tem nada no jornal) e o e-mail fica livre para um
  cadastro futuro. A auditoria guarda só o id e o domínio.
"""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from apps.core import audit
from apps.editorial import permissions

from . import services
from .models import User

logger = logging.getLogger(__name__)


def pending_accounts() -> QuerySet[User]:
    return (
        User.objects.filter(is_approved=False, is_active=True)
        .select_related("profile")
        .prefetch_related("profile__disciplines", "profile__areas")
        .order_by("date_joined")
    )


def pending_count() -> int:
    return User.objects.filter(is_approved=False, is_active=True).count()


def queue_url() -> str:
    return reverse("editorial:accounts")


def approvers() -> QuerySet[User]:
    return User.objects.filter(
        is_active=True, is_approved=True, role__in=(User.Role.EDITOR, User.Role.ADMIN)
    )


def notify_new_signup(person: User) -> int:
    from apps.editorial.models import Notification
    from apps.editorial.notifications import notify

    message = f"{person.public_name} ({person.email}) criou uma conta e aguarda aprovação"
    sent = 0
    for editor in approvers():
        notify(
            editor,
            Notification.Kind.ACCOUNT_PENDING,
            message,
            actor=person,
            url=f"{queue_url()}#conta-{person.pk}",
        )
        sent += 1
    return sent


def _close_pending_notices(person: User) -> None:
    """O aviso "aguarda aprovação" some do sino de todo mundo depois da decisão."""
    from apps.editorial.models import Notification

    Notification.objects.filter(
        kind=Notification.Kind.ACCOUNT_PENDING, actor=person, read_at__isnull=True
    ).update(read_at=timezone.now())


@transaction.atomic
def approve(actor: User, person: User, request: HttpRequest | None = None) -> User:
    from apps.editorial.models import Notification
    from apps.editorial.notifications import notify

    from .signup import absolute_url, send_email

    if not permissions.can_approve_accounts(actor):
        raise PermissionDenied
    person = User.objects.select_for_update().get(pk=person.pk)
    if person.is_approved:
        raise ValidationError("Esta conta já foi aprovada.")
    person.is_approved = True
    person.save(update_fields=["is_approved"])
    _close_pending_notices(person)
    audit.record(audit.Action.USER_APPROVED, actor=actor, target=person, request=request)
    notify(
        person,
        Notification.Kind.ACCOUNT_APPROVED,
        "Sua conta foi aprovada. Você já pode escrever e publicar no jornal.",
        actor=actor,
        url=reverse("dashboard:home"),
    )
    login_url = absolute_url("accounts:login")

    def send() -> None:
        try:
            send_email(
                person.email,
                "account_approved",
                {"name": person.public_name, "login_url": login_url},
            )
        except Exception:  # o aviso no sino já basta; o e-mail é cortesia
            logger.exception("Falha ao avisar por e-mail a aprovação da conta %s", person.pk)

    transaction.on_commit(send)
    return person


@transaction.atomic
def reject(actor: User, person: User, request: HttpRequest | None = None) -> None:
    if not permissions.can_approve_accounts(actor):
        raise PermissionDenied
    person = User.objects.select_for_update().get(pk=person.pk)
    if person.is_approved:
        raise ValidationError("Contas aprovadas não são recusadas: desative no Django Admin.")
    _close_pending_notices(person)
    audit.record(
        audit.Action.USER_REJECTED,
        actor=actor,
        target=person,
        changes={"dominio": person.email.rpartition("@")[2]},
        request=request,
    )
    services.remove_avatar(person)
    person.delete()
