"""Consultas da revisão por colega usadas pelo editor e pelo painel (docs/04, docs/16)."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.publications.models import Article, ArticleContributor

from . import permissions
from .models import EditorialEvent

Kind = EditorialEvent.Kind


@dataclass(frozen=True)
class ReviewSummary:
    """O que o painel lateral do editor mostra sobre a revisão."""

    reviewer: ArticleContributor | None
    requested_by: User | None
    requested_at: datetime | None
    request_note: str
    changes_by: User | None
    changes_note: str
    approved_by: User | None
    approved_at: datetime | None

    @property
    def is_empty(self) -> bool:
        return not (self.reviewer or self.approved_by)


def _last_status_change(article: Article, to_status: str) -> EditorialEvent | None:
    return (
        article.events.filter(kind=Kind.STATUS_CHANGE, to_status=to_status)
        .select_related("actor")
        .order_by("-created_at", "-pk")
        .first()
    )


def review_summary(article: Article) -> ReviewSummary:
    request = _last_status_change(article, Article.Status.IN_REVIEW)
    changes = None
    if article.status == Article.Status.CHANGES_REQUESTED:
        changes = _last_status_change(article, Article.Status.CHANGES_REQUESTED)
    approval = (
        article.events.filter(kind=Kind.APPROVED)
        .select_related("actor")
        .order_by("-created_at", "-pk")
        .first()
    )
    # O selo "revisado" vale para a última rodada: some quando o texto volta à revisão.
    if approval and request and approval.created_at < request.created_at:
        approval = None
    return ReviewSummary(
        reviewer=permissions.reviewer_credit(article),
        requested_by=request.actor if request else None,
        requested_at=request.created_at if request else None,
        request_note=request.note if request else "",
        changes_by=changes.actor if changes else None,
        changes_note=changes.note if changes else "",
        approved_by=approval.actor if approval else None,
        approved_at=approval.created_at if approval else None,
    )


def reviewer_candidates(article: Article, user: User) -> QuerySet[User]:
    """Colegas que podem revisar: ativos, sem quem pede e sem quem assina o texto."""
    authors = article.contributors.filter(
        user__isnull=False, role__in=ArticleContributor.EDITING_ROLES
    ).values_list("user_id", flat=True)
    return (
        User.objects.filter(is_active=True)
        .exclude(pk=user.pk)
        .exclude(pk__in=authors)
        .order_by("full_name")
    )
