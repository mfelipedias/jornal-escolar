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
    users: Iterable[User],
    kind: str,
    message: str,
    article: Article,
    actor: User,
    url: str = "",
) -> int:
    """Avisa cada pessoa. Sem url, o aviso abre o editor da publicação."""
    url = url or reverse("publications:edit", args=[article.pk])
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


# --- revisão por colega (docs/04, "Notificações") ---


def _review_url(article: Article) -> str:
    """Avisos sobre a leitura do texto abrem a tela de revisão (docs/17)."""
    return reverse("editorial:review", args=[article.pk])


def _with_note(message: str, note: str, label: str = "Nota") -> str:
    note = " ".join(note.split())
    return f"{message} {label}: {note}" if note else message


def review_requested(article: Article, actor: User, reviewer: User, note: str = "") -> int:
    if reviewer.pk == actor.pk or not reviewer.is_active:
        return 0
    message = _with_note(f"{actor.public_name} pediu que você revise “{article.title}”.", note)
    return _notify_many(
        [reviewer],
        Notification.Kind.REVIEW_REQUESTED,
        message,
        article,
        actor,
        _review_url(article),
    )


def review_cancelled(article: Article, actor: User, reviewer: User) -> int:
    if reviewer.pk == actor.pk or not reviewer.is_active:
        return 0
    message = f"{actor.public_name} cancelou o pedido de revisão de “{article.title}”."
    # O colega sai da revisão e perde o acesso ao texto: o aviso abre a lista de revisões.
    return _notify_many(
        [reviewer], Notification.Kind.SYSTEM, message, article, actor, reverse("editorial:queue")
    )


def edited_during_review(article: Article, actor: User, reviewer: User) -> int:
    """O autor continua editando durante a revisão; o revisor fica sabendo (docs/16)."""
    if reviewer.pk == actor.pk or not reviewer.is_active:
        return 0
    message = f"{actor.public_name} alterou “{article.title}” durante a revisão."
    return _notify_many(
        [reviewer],
        Notification.Kind.EDITED_BY_OTHER,
        message,
        article,
        actor,
        _review_url(article),
    )


def changes_requested(article: Article, actor: User, note: str, open_comments: int = 0) -> int:
    """Aos autores, com quantos comentários abertos esperam por eles (docs/17)."""
    message = f"{actor.public_name} sugeriu alterações em “{article.title}”."
    if open_comments:
        plural = "comentário aberto" if open_comments == 1 else "comentários abertos"
        message = f"{message[:-1]}: {open_comments} {plural}."
    message = _with_note(message, note)
    return _notify_many(
        article_team(article, exclude=actor),
        Notification.Kind.CHANGES_REQUESTED,
        message,
        article,
        actor,
        _review_url(article),
    )


def review_approved(article: Article, actor: User, note: str = "") -> int:
    message = _with_note(
        f"{actor.public_name} revisou “{article.title}” e aprovou. Publique quando quiser.", note
    )
    return _notify_many(
        article_team(article, exclude=actor), Notification.Kind.APPROVED, message, article, actor
    )


def review_declined(article: Article, actor: User, note: str = "") -> int:
    message = _with_note(
        f"{actor.public_name} não pôde revisar “{article.title}”. Escolha outro colega.",
        note,
        "Motivo",
    )
    return _notify_many(
        article_team(article, exclude=actor), Notification.Kind.SYSTEM, message, article, actor
    )


def _comment_url(article: Article, comment_pk: int) -> str:
    return f"{_review_url(article)}#comentario-{comment_pk}"


def review_comment_added(article: Article, actor: User, comment) -> int:
    """Comentário novo na revisão.

    Autor comentando avisa o revisor designado. Revisor ou editor comentando avisa os autores
    só fora de "em revisão": durante a leitura, os autores recebem tudo junto ao "Sugerir
    alterações" (um aviso por comentário atrapalharia quem ainda está sendo revisado).
    """
    title = article.title
    if article_team(article).filter(pk=actor.pk).exists():
        reviewer = _reviewer_user(article)
        if reviewer is None or reviewer.pk == actor.pk or not reviewer.is_active:
            return 0
        users: Iterable[User] = [reviewer]
    elif article.status == Article.Status.IN_REVIEW:
        return 0
    else:
        users = article_team(article, exclude=actor)
    message = f"{actor.public_name} comentou “{title}”."
    return _notify_many(
        users,
        Notification.Kind.REVIEW_COMMENT,
        message,
        article,
        actor,
        _comment_url(article, comment.pk),
    )


def review_comment_replied(article: Article, actor: User, parent) -> int:
    """Resposta: avisa quem já escreveu na conversa (quem abriu e quem respondeu)."""
    ids = {parent.author_id, *parent.replies.values_list("author_id", flat=True)}
    ids.discard(None)
    ids.discard(actor.pk)
    users = User.objects.filter(pk__in=ids, is_active=True)
    message = f"{actor.public_name} respondeu a um comentário em “{article.title}”."
    return _notify_many(
        users,
        Notification.Kind.REVIEW_COMMENT,
        message,
        article,
        actor,
        _comment_url(article, parent.pk),
    )


def _reviewer_user(article: Article) -> User | None:
    credit = article.contributors.filter(
        role=ArticleContributor.Role.REVIEWER, user__isnull=False
    ).first()
    return credit.user if credit is not None else None


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
