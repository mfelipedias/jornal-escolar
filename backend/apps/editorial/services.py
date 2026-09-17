"""Comentários editoriais da revisão (docs/17, "Comentários editoriais").

Criar (geral ou ancorado), responder (um nível), resolver e reabrir. Cada ação grava um
EditorialEvent (os comentários ficam no histórico, docs/04) e confere a permissão em
editorial/permissions.py. As decisões da revisão ficam em publications/services.py.

No fim, o aviso diário de revisões paradas (remind_stale_reviews), rodado pelo worker (E44).
"""

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.publications.models import Article

from . import alerts, anchors, events, notifications, permissions
from .models import EditorialComment, Notification

Kind = events.Kind
Status = EditorialComment.Status

EVENT_NOTE_MAX = 200


def _clean_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"body": "Escreva o comentário."})
    if len(body) > EditorialComment.BODY_MAX:
        raise ValidationError(
            {"body": f"O comentário pode ter até {EditorialComment.BODY_MAX} caracteres."}
        )
    return body


def _excerpt(text: str, limit: int = EVENT_NOTE_MAX) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _parse_position(value: object) -> int | None:
    try:
        position = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return position if position >= 0 else None


def _anchor(article: Article, quote: str, prefix: str, suffix: str, hint: object) -> dict:
    """Confere o trecho no texto atual e devolve os campos da âncora (vazios se geral)."""
    if not quote.strip():
        return {}
    quote = quote.strip()
    if len(quote) > EditorialComment.ANCHOR_MAX:
        raise ValidationError(
            {
                "anchor_text": (
                    f"Selecione um trecho menor (até {EditorialComment.ANCHOR_MAX} caracteres)."
                )
            }
        )
    text = anchors.document_text(article.body_json)
    found = anchors.locate(
        text,
        quote,
        prefix[-anchors.CONTEXT_MAX :],
        suffix[: anchors.CONTEXT_MAX],
        _parse_position(hint),
    )
    if found is None:
        raise ValidationError(
            {
                "anchor_text": (
                    "O trecho selecionado não está mais no texto. "
                    "Recarregue a página e selecione de novo."
                )
            }
        )
    start, end = found
    prefix, suffix = anchors.context(text, start, end)
    return {
        "anchor_text": quote,
        "anchor_prefix": prefix,
        "anchor_suffix": suffix,
        "anchor_from": start,
        "anchor_to": end,
    }


def _create(user: User, article: Article, body: str, **fields: object) -> EditorialComment:
    return EditorialComment.objects.create(article=article, author=user, body=body, **fields)


@transaction.atomic
def add_comment(
    user: User,
    article: Article,
    body: str,
    *,
    anchor_text: str = "",
    anchor_prefix: str = "",
    anchor_suffix: str = "",
    anchor_from: object = None,
) -> EditorialComment:
    """Novo comentário: geral (sem trecho) ou ancorado no trecho selecionado."""
    if not permissions.can_comment_on_review(user, article):
        raise PermissionDenied
    body = _clean_body(body)
    anchor = _anchor(article, anchor_text, anchor_prefix, anchor_suffix, anchor_from)
    comment = _create(user, article, body, **anchor)
    note = _excerpt(body)
    if comment.is_anchored:
        note = _excerpt(f"“{_excerpt(comment.anchor_text, 60)}”: {body}")
    events.record(article, user, Kind.COMMENT_ADDED, note=note)
    notifications.review_comment_added(article, user, comment)
    return comment


def add_note_comment(user: User, article: Article, note: str) -> EditorialComment:
    """A nota de "Sugerir alterações" vira um comentário geral aberto.

    Quem chama (publications.services.request_changes) já conferiu a permissão e registra a
    nota no evento da mudança de estado; por isso aqui não há evento nem aviso próprios.
    """
    return _create(user, article, _clean_body(note))


@transaction.atomic
def reply(user: User, parent: EditorialComment, body: str) -> EditorialComment:
    """Resposta a um comentário principal. Respostas têm um nível só."""
    article = parent.article
    if not permissions.can_comment_on_review(user, article):
        raise PermissionDenied
    if parent.parent_id is not None:
        raise ValidationError("Responda ao comentário principal.")
    comment = _create(user, article, _clean_body(body), parent=parent)
    events.record(article, user, Kind.COMMENT_REPLIED, note=_excerpt(comment.body))
    notifications.review_comment_replied(article, user, parent)
    return comment


def _set_status(user: User, comment: EditorialComment, status: str) -> EditorialComment:
    if not permissions.can_resolve_comment(user, comment.article):
        raise PermissionDenied
    if comment.parent_id is not None:
        raise ValidationError("Só o comentário principal é resolvido.")
    if comment.status == status:
        return comment
    comment.status = status
    resolved = status == Status.RESOLVED
    comment.resolved_by = user if resolved else None
    comment.resolved_at = timezone.now() if resolved else None
    comment.save(update_fields=["status", "resolved_by", "resolved_at", "updated_at"])
    kind = Kind.COMMENT_RESOLVED if resolved else Kind.COMMENT_REOPENED
    events.record(comment.article, user, kind, note=_excerpt(comment.body, 80))
    return comment


@transaction.atomic
def resolve(user: User, comment: EditorialComment) -> EditorialComment:
    return _set_status(user, comment, Status.RESOLVED)


@transaction.atomic
def reopen(user: User, comment: EditorialComment) -> EditorialComment:
    return _set_status(user, comment, Status.OPEN)


# --- aviso de revisão parada (docs/04, "Notificações"; E44) ---


def remind_stale_reviews(now: datetime | None = None) -> int:
    """Avisa revisor e autores das revisões sem movimento há mais de 5 dias.

    Usa o mesmo critério do alerta do painel editorial (alerts.stale_reviews). Quem já recebeu
    (ou teve atualizado) o aviso dessa publicação depois que ela ficou parada não recebe outro:
    rodar várias vezes não repete avisos, e um novo aviso só sai se a revisão andar e parar de
    novo. Devolve quantos avisos foram criados ou atualizados.
    """
    now = now or timezone.now()
    days = alerts.STALE_REVIEW_DAYS
    sent = 0
    for alert in alerts.stale_reviews(now).items:
        article = alert.article
        stale_since = alert.since + timedelta(days=days)
        already = set(
            Notification.objects.filter(
                kind=Notification.Kind.REVIEW_STALE,
                article=article,
                updated_at__gte=stale_since,
            ).values_list("user_id", flat=True)
        )
        people = list(notifications.article_team(article))
        credit = permissions.reviewer_credit(article)
        if credit is not None and credit.user.is_active:
            people.append(credit.user)
        targets = {user.pk: user for user in people if user.pk not in already}
        idle = max((now - alert.since).days, days)
        sent += notifications.review_stale(article, idle, targets.values())
    return sent
