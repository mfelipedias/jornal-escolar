from typing import Any

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User, dispatch_uid="accounts_create_profile")
def create_profile(sender: type[User], instance: User, created: bool, **kwargs: Any) -> None:
    """Cria o perfil junto com a conta, venha ela do admin, do createsuperuser ou de testes."""
    if created and not kwargs.get("raw"):
        from .services import ensure_profile

        ensure_profile(instance)


@receiver(user_logged_in, dispatch_uid="accounts_audit_login")
def audit_login(sender: Any, request: Any, user: User, **kwargs: Any) -> None:
    """Toda entrada (senha, Microsoft ou link de acesso) vai para a auditoria (docs/23)."""
    from apps.core import audit

    audit.record(audit.Action.LOGIN, actor=user, target=user, request=request)
