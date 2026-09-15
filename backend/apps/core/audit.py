"""Gravação do AuditLog, a auditoria de ações sensíveis (docs/23, "Auditoria").

Uso: audit.record(AuditLog.Action.ROLE_CHANGED, actor=request.user, target=user,
changes={"role": ["staff", "editor"]}, request=request).

Regras:
- Nunca guardar nome, e-mail ou texto pessoal em changes: use ids e códigos.
- O IP é guardado como hash SHA-256 com sal mensal (SECRET_KEY + ano-mês). Dá para ver que
  duas ações do mesmo mês vieram do mesmo lugar, mas não dá para recuperar o IP nem ligar
  meses diferentes.
"""

import hashlib
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpRequest
from django.utils import timezone

from .models import AuditLog

Action = AuditLog.Action


def client_ip(request: HttpRequest | None) -> str:
    """IP de quem fez a requisição, com a mesma regra do limite de login (allauth)."""
    if request is None:
        return ""
    from allauth.account.adapter import get_adapter

    try:
        return get_adapter(request).get_client_ip(request) or ""
    except PermissionDenied:
        return ""


def hash_ip(ip: str, when: Any = None) -> str:
    if not ip:
        return ""
    month = timezone.localtime(when or timezone.now()).strftime("%Y-%m")
    return hashlib.sha256(f"{settings.SECRET_KEY}:{month}:{ip}".encode()).hexdigest()


def target_type(obj: models.Model) -> str:
    return obj._meta.label_lower


def record(
    action: str,
    *,
    actor: Any = None,
    target: models.Model | None = None,
    changes: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type(target) if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        changes=changes or {},
        ip_hash=hash_ip(client_ip(request)),
    )


def for_target(obj: models.Model):
    return AuditLog.objects.filter(target_type=target_type(obj), target_id=str(obj.pk))
