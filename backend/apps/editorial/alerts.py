"""Alertas do painel editorial (docs/18, "Visão geral"; E33).

Cada fonte é uma função sem argumentos obrigatórios que devolve um AlertGroup. A visão geral
mostra só os grupos com itens. Alertas de recursos futuros (comentários públicos pendentes,
curadoria, falha de backup) entram acrescentando a função em SOURCES quando a etapa chegar.

Os alertas são calculados na hora, a partir do estado atual: quando a condição deixa de valer
(o revisor comenta, alguém responde, a autorização é marcada), o alerta some sozinho.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from apps.publications import rendering
from apps.publications.models import Article, ArticleContributor, MediaAsset

from . import permissions
from .models import EditorialComment

Status = Article.Status

STALE_REVIEW_DAYS = 5
STALE_COMMENT_DAYS = 3


@dataclass(frozen=True)
class Alert:
    """Uma publicação que precisa da atenção de um editor."""

    article: Article
    message: str
    url: str
    action: str
    since: datetime | None = None
    # Créditos de aluno envolvidos (só no alerta de autorização): o admin anonimiza daqui.
    credits: tuple[ArticleContributor, ...] = ()


@dataclass(frozen=True)
class AlertGroup:
    key: str
    title: str
    help: str
    level: str  # "warn" (atraso) ou "danger" (dado que não deveria existir)
    items: list[Alert] = field(default_factory=list)


def _days(since: datetime, now: datetime) -> int:
    return max((now - since).days, 0)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def stale_reviews(now: datetime | None = None) -> AlertGroup:
    """Em revisão há mais de 5 dias sem nenhum evento (comentário, edição, troca de revisor)."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=STALE_REVIEW_DAYS)
    articles = (
        Article.objects.filter(status=Status.IN_REVIEW, submitted_at__lt=cutoff)
        .annotate(last_event=Max("events__created_at"))
        .filter(Q(last_event__isnull=True) | Q(last_event__lt=cutoff))
        .order_by("submitted_at", "pk")
    )
    items = []
    for article in articles:
        since = max(filter(None, (article.submitted_at, article.last_event)))
        credit = permissions.reviewer_credit(article)
        who = f"com {credit.display_name}" if credit else "sem revisor"
        items.append(
            Alert(
                article=article,
                message=f"Em revisão {who}, sem movimento há {_days(since, now)} dias.",
                url=reverse("editorial:review", args=[article.pk]),
                action="Abrir revisão",
                since=since,
            )
        )
    return AlertGroup(
        key="revisoes-paradas",
        title="Revisões paradas",
        help=f"Em revisão há mais de {STALE_REVIEW_DAYS} dias sem comentário, edição ou decisão."
        " Dá para trocar o revisor em “Todas as publicações”.",
        level="warn",
        items=items,
    )


def stale_comments(now: datetime | None = None) -> AlertGroup:
    """Comentários da revisão abertos há mais de 3 dias sem resposta, em textos ainda em
    andamento (em revisão ou com alterações sugeridas).

    Substitui, até a Fase 3, o alerta de comentários públicos pendentes do docs/18.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(days=STALE_COMMENT_DAYS)
    comments = (
        EditorialComment.objects.filter(
            parent__isnull=True,
            status=EditorialComment.Status.OPEN,
            article__status__in=(Status.IN_REVIEW, Status.CHANGES_REQUESTED),
            created_at__lt=cutoff,
        )
        .annotate(last_reply=Max("replies__created_at"))
        .filter(Q(last_reply__isnull=True) | Q(last_reply__lt=cutoff))
        .select_related("article")
        .order_by("created_at", "pk")
    )
    by_article: dict[int, list[EditorialComment]] = {}
    for comment in comments:
        by_article.setdefault(comment.article_id, []).append(comment)
    items = []
    for group in by_article.values():
        article = group[0].article
        since = min(max(filter(None, (c.created_at, c.last_reply))) for c in group)
        count = _plural(len(group), "comentário aberto", "comentários abertos")
        items.append(
            Alert(
                article=article,
                message=f"{count} sem resposta há {_days(since, now)} dias"
                f" ({Status(article.status).label.lower()}).",
                url=reverse("editorial:review", args=[article.pk]),
                action="Ver comentários",
                since=since,
            )
        )
    return AlertGroup(
        key="comentarios-parados",
        title="Comentários da revisão sem resposta",
        help=f"Abertos há mais de {STALE_COMMENT_DAYS} dias em textos em revisão ou com"
        " alterações sugeridas, sem nenhuma resposta nesse período.",
        level="warn",
        items=items,
    )


def student_consent(now: datetime | None = None) -> AlertGroup:
    """Publicadas com crédito de aluno sem autorização: a checklist impede, então é dado antigo
    ou alterado por fora do fluxo."""
    credits = ArticleContributor.objects.filter(
        article__status=Status.PUBLISHED,
        is_student=True,
        consent_ok=False,
        anonymized_at__isnull=True,
    ).select_related("article")
    by_article: dict[int, list[ArticleContributor]] = {}
    for credit in credits.order_by("article__published_at", "article_id"):
        by_article.setdefault(credit.article_id, []).append(credit)
    items = [
        Alert(
            article=group[0].article,
            message="Publicada com "
            + _plural(len(group), "crédito de aluno", "créditos de alunos")
            + " sem autorização marcada.",
            url=reverse("publications:edit", args=[group[0].article_id]),
            action="Abrir no editor",
            credits=tuple(group),
        )
        for group in by_article.values()
    ]
    return AlertGroup(
        key="alunos-sem-autorizacao",
        title="Alunos sem autorização",
        help="Não deveria existir: a publicação exige a autorização de todos os alunos"
        " creditados. Confira com a família ou anonimize o crédito.",
        level="danger",
        items=items,
    )


def image_consent(now: datetime | None = None) -> AlertGroup:
    """Publicadas com imagem de pessoas sem autorização (na capa ou no corpo)."""
    flagged = MediaAsset.objects.filter(has_people=True, consent_ok=False)
    flagged_ids = set(flagged.values_list("pk", flat=True))
    items = []
    if flagged_ids:
        candidates = (
            Article.objects.filter(status=Status.PUBLISHED)
            .filter(Q(cover__in=flagged) | Q(media_assets__in=flagged))
            .distinct()
            .order_by("published_at", "pk")
        )
        for article in candidates:
            used = rendering.collect_asset_ids(rendering.normalize(article.body_json))
            if article.cover_id:
                used.add(article.cover_id)
            count = len(used & flagged_ids)
            if count:
                items.append(
                    Alert(
                        article=article,
                        message="Publicada com "
                        + _plural(count, "imagem de pessoas", "imagens de pessoas")
                        + " sem autorização marcada.",
                        url=reverse("publications:edit", args=[article.pk]),
                        action="Abrir no editor",
                    )
                )
    return AlertGroup(
        key="imagens-sem-autorizacao",
        title="Imagens sem autorização",
        help="Não deveria existir: a publicação exige autorização para imagens em que"
        " aparecem pessoas. Marque a autorização ou troque a imagem.",
        level="danger",
        items=items,
    )


# Ordem de exibição: primeiro o que não deveria existir, depois os atrasos.
SOURCES: list[Callable[..., AlertGroup]] = [
    student_consent,
    image_consent,
    stale_reviews,
    stale_comments,
]


def editorial_alerts(now: datetime | None = None) -> list[AlertGroup]:
    """Grupos com ao menos um alerta, na ordem de SOURCES."""
    now = now or timezone.now()
    return [group for group in (source(now) for source in SOURCES) if group.items]


def alert_count(groups: list[AlertGroup]) -> int:
    return sum(len(group.items) for group in groups)
