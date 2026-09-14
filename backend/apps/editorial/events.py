"""Registro e leitura de EditorialEvent, a auditoria editorial (docs/04, docs/06).

Os serviços chamam estas funções; nenhuma view grava evento diretamente.
"""

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.publications.models import Article

from .models import EditorialEvent

Kind = EditorialEvent.Kind

# Autosave salva a cada poucos segundos: edições seguidas da mesma pessoa viram um evento só.
EDIT_EVENT_WINDOW = timedelta(minutes=15)


def record(
    article: Article,
    actor: User | None,
    kind: str,
    *,
    from_status: str = "",
    to_status: str = "",
    note: str = "",
) -> EditorialEvent:
    return EditorialEvent.objects.create(
        article=article,
        actor=actor if actor is not None and actor.is_authenticated else None,
        kind=kind,
        from_status=from_status,
        to_status=to_status,
        note=note.strip(),
    )


def status_change(
    article: Article, actor: User | None, from_status: str, note: str = ""
) -> EditorialEvent | None:
    """Mudança de estado: from_status é o de antes, o novo é o atual da publicação."""
    if from_status == article.status:
        return None
    return record(
        article,
        actor,
        Kind.STATUS_CHANGE,
        from_status=from_status,
        to_status=article.status,
        note=note,
    )


def record_edit(article: Article, actor: User, kind: str) -> EditorialEvent:
    """Edição (depois de publicar ou por terceiro), no máximo um evento por pessoa na janela."""
    recent = EditorialEvent.objects.filter(
        article=article,
        actor=actor,
        kind=kind,
        created_at__gte=timezone.now() - EDIT_EVENT_WINDOW,
    ).first()
    return recent or record(article, actor, kind)


def history(article: Article) -> QuerySet[EditorialEvent]:
    """Linha do tempo da publicação, da mais antiga para a mais recente."""
    return article.events.select_related("actor").order_by("created_at", "pk")


def latest(article: Article, kind: str) -> EditorialEvent | None:
    return article.events.filter(kind=kind).select_related("actor").order_by("-created_at").first()
