"""Comentários editoriais da revisão (docs/17, "Comentários editoriais").

Criar (geral ou ancorado), responder (um nível), resolver e reabrir. Cada ação grava um
EditorialEvent (os comentários ficam no histórico, docs/04) e confere a permissão em
editorial/permissions.py. As decisões da revisão ficam em publications/services.py.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.publications.models import Article

from . import anchors, events, notifications, permissions
from .models import EditorialComment

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
