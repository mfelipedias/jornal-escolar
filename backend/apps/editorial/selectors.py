"""Consultas da revisão por colega (editor, tela de revisão, aba "Revisões"; docs/04, 15-17) e
do painel editorial (visão geral e todas as publicações; docs/18). Alertas em alerts.py."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.engagement.models import Comment
from apps.publications.models import Article, ArticleContributor

from . import anchors, events, permissions
from .models import EditorialComment, EditorialEvent

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
    open_comments: int = 0

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
        open_comments=open_comment_count(article),
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
    Kind.COMMENT_ADDED: "comentou",
    Kind.COMMENT_REPLIED: "respondeu a um comentário",
    Kind.COMMENT_RESOLVED: "resolveu um comentário",
    Kind.COMMENT_REOPENED: "reabriu um comentário",
}


def describe(event: EditorialEvent) -> str:
    if event.kind != Kind.STATUS_CHANGE:
        return KIND_TEXTS.get(event.kind, event.get_kind_display().lower())
    text = STATUS_TEXTS.get((event.from_status, event.to_status)) or STATUS_TEXTS.get(
        (None, event.to_status)
    )
    return text or f"mudou o estado para {Status(event.to_status).label.lower()}"


# --- comentários editoriais (docs/17) ---


def open_comment_count(article: Article) -> int:
    """Comentários principais abertos (respostas não contam)."""
    return article.editorial_comments.filter(
        parent__isnull=True, status=EditorialComment.Status.OPEN
    ).count()


@dataclass(frozen=True)
class CommentThread:
    """Um comentário principal com as respostas e onde o trecho está agora."""

    comment: EditorialComment
    replies: list[EditorialComment]
    # "general" (sem trecho), "found" (trecho reencontrado) ou "changed" (trecho alterado).
    anchor_state: str
    anchor_start: int | None = None
    anchor_end: int | None = None

    @property
    def is_changed(self) -> bool:
        return self.anchor_state == "changed"


@dataclass(frozen=True)
class CommentBoard:
    open: list[CommentThread]
    resolved: list[CommentThread]

    @property
    def open_count(self) -> int:
        return len(self.open)


def comment_board(article: Article) -> CommentBoard:
    """Conversas da tela de revisão: abertas primeiro, na ordem do texto (gerais no fim)."""
    comments = list(
        article.editorial_comments.select_related("author", "resolved_by").order_by(
            "created_at", "pk"
        )
    )
    replies: dict[int, list[EditorialComment]] = {}
    for comment in comments:
        if comment.parent_id is not None:
            replies.setdefault(comment.parent_id, []).append(comment)
    text = anchors.document_text(article.body_json)
    threads = []
    for comment in comments:
        if comment.parent_id is not None:
            continue
        found = None
        if comment.is_anchored:
            found = anchors.locate(
                text,
                comment.anchor_text,
                comment.anchor_prefix,
                comment.anchor_suffix,
                comment.anchor_from,
            )
        state = "general" if not comment.is_anchored else ("found" if found else "changed")
        threads.append(
            CommentThread(
                comment=comment,
                replies=replies.get(comment.pk, []),
                anchor_state=state,
                anchor_start=found[0] if found else None,
                anchor_end=found[1] if found else None,
            )
        )

    def order(thread: CommentThread) -> int:
        # Trecho alterado e comentário geral vão depois dos ancorados (ordem de criação).
        return thread.anchor_start if thread.anchor_start is not None else len(text) + 1

    open_threads = sorted((t for t in threads if t.comment.is_open), key=order)
    resolved = sorted(
        (t for t in threads if not t.comment.is_open),
        key=lambda t: t.comment.resolved_at or t.comment.created_at,
        reverse=True,
    )
    return CommentBoard(open=open_threads, resolved=resolved)


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


# --- painel editorial: visão geral e todas as publicações (docs/18, E33) ---

RECENT_PUBLISHED_DAYS = 30
DRAFT_AUTHORS_LIMIT = 6

# ?estado= → estado do modelo. Mesmas chaves de "Minhas publicações" (dashboard).
EDITORIAL_STATUS: dict[str, str] = {
    "rascunhos": Status.DRAFT,
    "em-revisao": Status.IN_REVIEW,
    "alteracoes-sugeridas": Status.CHANGES_REQUESTED,
    "publicados": Status.PUBLISHED,
    "arquivados": Status.ARCHIVED,
}

# ?periodo= → dias desde a última atualização.
PERIODS: dict[str, tuple[str, int]] = {
    "7": ("Últimos 7 dias", 7),
    "30": ("Últimos 30 dias", 30),
    "90": ("Últimos 90 dias", 90),
    "365": ("Último ano", 365),
}


def editorial_counts(now: datetime | None = None) -> dict[str, int]:
    """Contadores da visão geral: um por estado, publicados nos últimos 30 dias, comentários
    da revisão abertos (fora dos arquivados) e comentários de leitores pendentes (E41)."""
    now = now or timezone.now()
    recent = now - timedelta(days=RECENT_PUBLISHED_DAYS)
    counts = Article.objects.aggregate(
        drafts=Count("pk", filter=Q(status=Status.DRAFT)),
        in_review=Count("pk", filter=Q(status=Status.IN_REVIEW)),
        changes_requested=Count("pk", filter=Q(status=Status.CHANGES_REQUESTED)),
        published_recent=Count("pk", filter=Q(status=Status.PUBLISHED, published_at__gte=recent)),
        archived=Count("pk", filter=Q(status=Status.ARCHIVED)),
    )
    counts["pending_public_comments"] = Comment.objects.filter(
        status=Comment.Status.PENDING
    ).count()
    counts["open_comments"] = (
        EditorialComment.objects.filter(parent__isnull=True, status=EditorialComment.Status.OPEN)
        .exclude(article__status=Status.ARCHIVED)
        .count()
    )
    return counts


def draft_authors(limit: int = DRAFT_AUTHORS_LIMIT) -> list[User]:
    """Quem tem rascunhos, com a quantidade em .drafts (mais rascunhos primeiro)."""
    return list(
        User.objects.filter(
            contributions__article__status=Status.DRAFT,
            contributions__role__in=ArticleContributor.EDITING_ROLES,
        )
        .annotate(drafts=Count("contributions__article", distinct=True))
        .order_by("-drafts", "full_name")[:limit]
    )


@dataclass(frozen=True)
class ArticleFilters:
    """Filtros de "Todas as publicações", já validados a partir do ?querystring."""

    estado: str = ""
    tipo: str = ""
    area: str = ""
    autor: int | None = None
    revisor: int | None = None
    periodo: str = ""
    q: str = ""

    @property
    def active(self) -> bool:
        return any(
            (self.estado, self.tipo, self.area, self.autor, self.revisor, self.periodo, self.q)
        )


def _int_or_none(value: str | None) -> int | None:
    try:
        number = int(value or "")
    except ValueError:
        return None
    return number if number > 0 else None


def parse_article_filters(params) -> ArticleFilters:
    estado = params.get("estado", "")
    periodo = params.get("periodo", "")
    return ArticleFilters(
        estado=estado if estado in EDITORIAL_STATUS else "",
        tipo=(params.get("tipo") or "")[:140],
        area=(params.get("area") or "")[:140],
        autor=_int_or_none(params.get("autor")),
        revisor=_int_or_none(params.get("revisor")),
        periodo=periodo if periodo in PERIODS else "",
        q=" ".join((params.get("q") or "").split())[:100],
    )


def all_articles(filters: ArticleFilters, now: datetime | None = None) -> QuerySet[Article]:
    """Todas as publicações do jornal, filtradas, da atualização mais recente para a mais antiga."""
    articles = Article.objects.all()
    if filters.estado:
        articles = articles.filter(status=EDITORIAL_STATUS[filters.estado])
    if filters.tipo:
        articles = articles.filter(type__slug=filters.tipo)
    if filters.periodo:
        since = (now or timezone.now()) - timedelta(days=PERIODS[filters.periodo][1])
        articles = articles.filter(updated_at__gte=since)
    if filters.q:
        articles = articles.filter(title__icontains=filters.q)
    # Filtros por relações de muitos: subconsulta por pk, sem linhas repetidas.
    if filters.area:
        articles = articles.filter(
            pk__in=Article.objects.filter(disciplines__area__slug=filters.area).values("pk")
        )
    if filters.autor:
        articles = articles.filter(
            pk__in=ArticleContributor.objects.filter(
                user_id=filters.autor, role__in=ArticleContributor.EDITING_ROLES
            ).values("article_id")
        )
    if filters.revisor:
        articles = articles.filter(
            pk__in=ArticleContributor.objects.filter(
                user_id=filters.revisor, role=ArticleContributor.Role.REVIEWER
            ).values("article_id")
        )
    return (
        articles.select_related("type")
        .prefetch_related("contributors")
        .order_by("-updated_at", "-pk")
    )


def filter_people() -> tuple[QuerySet[User], QuerySet[User]]:
    """Opções dos filtros "Autor" e "Revisor": quem já assinou ou revisou algum texto."""
    authors = (
        User.objects.filter(contributions__role__in=ArticleContributor.EDITING_ROLES)
        .distinct()
        .order_by("full_name")
    )
    reviewers = (
        User.objects.filter(contributions__role=ArticleContributor.Role.REVIEWER)
        .distinct()
        .order_by("full_name")
    )
    return authors, reviewers
