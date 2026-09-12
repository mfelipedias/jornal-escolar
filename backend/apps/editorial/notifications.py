"""Criação e leitura de notificações do painel (docs/04 "Notificações", docs/15)."""

from collections.abc import Iterable

from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.publications.models import Article, ArticleContributor

from .models import Notification

LIST_LIMIT = 20


def notify(
    user: User,
    kind: str,
    message: str,
    *,
    article: Article | None = None,
    actor: User | None = None,
    url: str = "",
) -> Notification:
    """Cria um aviso. Se já existe um igual ainda não lido (mesmo tipo, publicação e autor da
    ação), atualiza a mensagem em vez de criar outro: o editor salva a cada poucos segundos."""
    existing = Notification.objects.filter(
        user=user, kind=kind, article=article, actor=actor, read_at__isnull=True
    ).first()
    if existing is not None:
        existing.message = message[:200]
        existing.url = url[:300]
        existing.save(update_fields=["message", "url", "updated_at"])
        return existing
    return Notification.objects.create(
        user=user, kind=kind, article=article, actor=actor, message=message[:200], url=url[:300]
    )


def article_team(article: Article, exclude: User | None = None) -> QuerySet[User]:
    """Autores e coautores da equipe, ativos, sem quem fez a ação."""
    users = User.objects.filter(
        is_active=True,
        contributions__article=article,
        contributions__role__in=ArticleContributor.EDITING_ROLES,
    ).distinct()
    return users.exclude(pk=exclude.pk) if exclude is not None else users


def _notify_many(
    users: Iterable[User], kind: str, message: str, article: Article, actor: User
) -> int:
    url = reverse("publications:edit", args=[article.pk])
    count = 0
    for user in users:
        notify(user, kind, message, article=article, actor=actor, url=url)
        count += 1
    return count


def article_published(article: Article, actor: User) -> int:
    message = f"{actor.public_name} publicou “{article.title}”."
    return _notify_many(
        article_team(article, exclude=actor),
        Notification.Kind.PUBLISHED_BY_OTHER,
        message,
        article,
        actor,
    )


def article_edited_by_other(article: Article, actor: User) -> int:
    """Só quando quem editou não é autor nem coautor (editor ou admin mexendo em texto alheio)."""
    if article_team(article).filter(pk=actor.pk).exists():
        return 0
    message = f"{actor.public_name} editou “{article.title}”."
    return _notify_many(
        article_team(article), Notification.Kind.EDITED_BY_OTHER, message, article, actor
    )


def article_archived(article: Article, actor: User, note: str = "") -> int:
    if article_team(article).filter(pk=actor.pk).exists():
        return 0
    message = f"{actor.public_name} arquivou “{article.title}”."
    if note.strip():
        message = f"{message} Motivo: {note.strip()}"
    return _notify_many(
        article_team(article), Notification.Kind.ARCHIVED_BY_OTHER, message, article, actor
    )


# --- leitura ---


def unread_count(user: User) -> int:
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def recent(user: User, limit: int = LIST_LIMIT) -> QuerySet[Notification]:
    return Notification.objects.filter(user=user).select_related("actor")[:limit]


def mark_all_read(user: User) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def mark_read(notification: Notification) -> None:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
