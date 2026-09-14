"""Consultas da revisão por colega: editor, tela de revisão e aba "Revisões" (docs/04, 15-17)."""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.publications.models import Article, ArticleContributor

from . import events, permissions
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


# --- tela de revisão e aba "Revisões" (docs/15, docs/17) ---

Status = Article.Status

# ?aba= → rótulo. "todas" só aparece para editores (permissions.is_editor).
QUEUE_TABS: dict[str, str] = {
    "pedidas-a-mim": "Pedidas a mim",
    "que-eu-pedi": "Que eu pedi",
    "todas": "Todas em revisão",
}
DEFAULT_TAB = "pedidas-a-mim"


def queue_tabs(user: User) -> list[str]:
    tabs = ["pedidas-a-mim", "que-eu-pedi"]
    if permissions.is_editor(user):
        tabs.append("todas")
    return tabs


def review_queue(user: User, tab: str = DEFAULT_TAB) -> QuerySet[Article]:
    """Publicações em revisão de uma aba, do pedido mais antigo para o mais recente.

    Sem fila geral: "Pedidas a mim" são os textos em que a pessoa é o revisor designado;
    "Que eu pedi", os textos em revisão que ela assina; "Todas", tudo em revisão (editores).
    """
    articles = Article.objects.filter(status=Status.IN_REVIEW)
    if tab == "pedidas-a-mim":
        articles = articles.filter(
            contributors__user=user, contributors__role=ArticleContributor.Role.REVIEWER
        )
    elif tab == "que-eu-pedi":
        articles = articles.filter(
            contributors__user=user, contributors__role__in=ArticleContributor.EDITING_ROLES
        )
    elif tab != "todas" or not permissions.is_editor(user):
        return Article.objects.none()
    return (
        articles.distinct()
        .select_related("type")
        .prefetch_related("contributors")
        .order_by("submitted_at", "pk")
    )


def pending_review_count(user: User) -> int:
    """Contador do menu: revisões esperando a decisão da pessoa."""
    if not permissions.is_staff_member(user):
        return 0
    return review_queue(user, "pedidas-a-mim").count()


@dataclass(frozen=True)
class HistoryEntry:
    """Uma linha do histórico da tela de revisão."""

    when: datetime
    actor: str
    text: str
    note: str


# (estado anterior, estado novo) → o que aconteceu. None vale para qualquer estado anterior.
STATUS_TEXTS: dict[tuple[str | None, str], str] = {
    (Status.CHANGES_REQUESTED, Status.IN_REVIEW): "reenviou para revisão",
    (None, Status.IN_REVIEW): "pediu revisão",
    (None, Status.CHANGES_REQUESTED): "sugeriu alterações",
    (None, Status.PUBLISHED): "publicou",
    (None, Status.ARCHIVED): "arquivou",
    (Status.ARCHIVED, Status.DRAFT): "restaurou como rascunho",
    (None, Status.DRAFT): "voltou o texto a rascunho",
}

KIND_TEXTS: dict[str, str] = {
    Kind.REVIEWER_ASSIGNED: "escolheu quem revisa",
    Kind.REVIEWER_REMOVED: "tirou o revisor",
    Kind.APPROVED: "aprovou a revisão",
    Kind.CONTRIBUTOR_CHANGED: "alterou os créditos",
    Kind.EDITED_AFTER_PUBLISH: "editou depois de publicar",
    Kind.EDITED_BY_THIRD_PARTY: "editou o texto",
    Kind.CREDIT_ANONYMIZED: "anonimizou um crédito",
}


def describe(event: EditorialEvent) -> str:
    if event.kind != Kind.STATUS_CHANGE:
        return KIND_TEXTS.get(event.kind, event.get_kind_display().lower())
    text = STATUS_TEXTS.get((event.from_status, event.to_status)) or STATUS_TEXTS.get(
        (None, event.to_status)
    )
    return text or f"mudou o estado para {Status(event.to_status).label.lower()}"


def history_entries(article: Article) -> list[HistoryEntry]:
    """Linha do tempo legível (events.history), da mais antiga para a mais recente."""
    return [
        HistoryEntry(
            when=event.created_at,
            actor=event.actor.public_name if event.actor else "Sistema",
            text=describe(event),
            note=event.note,
        )
        for event in events.history(article)
    ]
