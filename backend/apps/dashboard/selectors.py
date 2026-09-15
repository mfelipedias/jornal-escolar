"""Consultas do painel da equipe (docs/15): início e "Minhas publicações".

"Minhas" são as publicações em que a pessoa aparece nos créditos: como autora ou coautora
em qualquer estado; em outros papéis (colaboração, edição) só depois de publicadas, porque
rascunhos e arquivados não são visíveis para quem não edita (apps/editorial/permissions.py).
Os textos em que a pessoa só revisa ficam em "Revisões" (editorial:queue, E31).
"""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Prefetch, Q, QuerySet, Sum
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.selectors import missing_profile_items
from apps.editorial.models import Notification
from apps.engagement import selectors as moderation
from apps.engagement import services as engagement
from apps.engagement.models import Comment
from apps.publications.models import Article, ArticleContributor

Role = ArticleContributor.Role
Status = Article.Status

HOME_DRAFTS = 3
HOME_PUBLISHED = 3
HOME_NOTIFICATIONS = 5

# Chips de "Minhas publicações": ?estado= → estado do modelo (docs/15).
STATUS_FILTERS: dict[str, tuple[str, str | None]] = {
    "": ("Todos", None),
    "rascunhos": ("Rascunhos", Status.DRAFT),
    "em-revisao": ("Em revisão", Status.IN_REVIEW),
    "alteracoes-sugeridas": ("Alterações sugeridas", Status.CHANGES_REQUESTED),
    "publicados": ("Publicados", Status.PUBLISHED),
    "arquivados": ("Arquivados", Status.ARCHIVED),
}


def _credit_filter(user: User) -> Q:
    editing = Q(contributors__user=user, contributors__role__in=ArticleContributor.EDITING_ROLES)
    other = Q(
        contributors__user=user,
        contributors__role__in=(Role.COLLABORATOR, Role.EDITOR),
        status=Status.PUBLISHED,
    )
    return editing | other


def my_articles(user: User, status_filter: str = "") -> QuerySet[Article]:
    """Publicações da pessoa, da atualização mais recente para a mais antiga."""
    ids = Article.objects.filter(_credit_filter(user)).values("pk")
    articles = Article.objects.filter(pk__in=ids)
    status = STATUS_FILTERS.get(status_filter, ("", None))[1]
    if status is not None:
        articles = articles.filter(status=status)
    pending = Q(comments__status=Comment.Status.PENDING)
    return (
        articles.annotate(pending_comments=Count("comments", filter=pending))
        .select_related("type")
        .prefetch_related(
            Prefetch(
                "contributors",
                queryset=ArticleContributor.objects.filter(user=user).order_by("order", "pk"),
                to_attr="my_credits",
            )
        )
        .order_by("-updated_at", "-pk")
    )


def status_counts(user: User) -> dict[str, int]:
    """Quantas publicações em cada chip, com a chave do ?estado=."""
    ids = Article.objects.filter(_credit_filter(user)).values("pk")
    totals = Article.objects.filter(pk__in=ids).aggregate(
        total=Count("pk"),
        **{key: Count("pk", filter=Q(status=status)) for key, (_, status) in _named_filters()},
    )
    return {"": totals.pop("total"), **totals}


def _named_filters():
    return [(key, value) for key, value in STATUS_FILTERS.items() if key]


def recent_drafts(user: User, limit: int = HOME_DRAFTS) -> list[Article]:
    """Continuar escrevendo: rascunhos em que a pessoa é autora ou coautora."""
    return list(my_articles(user, "rascunhos")[:limit])


def recent_published(user: User, limit: int = HOME_PUBLISHED) -> list[Article]:
    """Últimas publicadas, cada uma com `reactions_total` (soma dos tipos de reação)."""
    articles = list(my_articles(user, "publicados").order_by("-published_at", "-pk")[:limit])
    for article in articles:
        article.reactions_total = sum((article.reactions_count or {}).values())
    return articles


@dataclass(frozen=True)
class Pending:
    """Uma linha do bloco "Pendências" do início do painel."""

    kind: str
    message: str
    url: str
    when: datetime | None = None


def comment_pending_items(user: User) -> list[Pending]:
    """ "3 comentários aguardam sua aprovação" → fila de comentários (docs/15).

    A conta é das publicações que a pessoa assina; editores veem também o total do jornal.
    """
    own = moderation.own_pending_count(user)
    total = moderation.pending_count(user)
    if not total:
        return []
    url = reverse("engagement:moderation")
    if own == total:
        verb = "aguarda" if own == 1 else "aguardam"
        message = f"{_comments(own)} {verb} sua aprovação."
    else:
        verb = "aguarda" if total == 1 else "aguardam"
        message = f"{_comments(total)} {verb} aprovação no jornal"
        message += f" ({own} nas suas publicações)." if own else "."
    return [Pending(kind="comments", message=message, url=url)]


def _comments(n: int) -> str:
    return "1 comentário" if n == 1 else f"{n} comentários"


def pending_items(user: User, limit: int = HOME_NOTIFICATIONS) -> tuple[list[Pending], int]:
    """O que a pessoa precisa ver agora (docs/15, "Início do painel").

    Comentários públicos aguardando (E41) primeiro, depois os avisos não lidos (revisão,
    texto editado, publicado ou arquivado por outra pessoa) e "Complete seu perfil".
    Devolve (itens, total de avisos não lidos).
    """
    # Os avisos de comentário pendente já estão resumidos na primeira linha.
    unread = Notification.objects.filter(user=user, read_at__isnull=True).exclude(
        kind=Notification.Kind.COMMENT_PENDING
    )
    total = unread.count()
    items = comment_pending_items(user)
    items += [
        Pending(
            kind=n.kind,
            message=n.message,
            url=reverse("editorial:notification_open", args=[n.pk]),
            when=n.updated_at,
        )
        for n in unread[:limit]
    ]
    missing = missing_profile_items(user)
    if missing:
        items.append(
            Pending(
                kind="profile",
                message="Complete seu perfil: falta " + ", ".join(missing) + ".",
                url=reverse("accounts:profile_edit"),
            )
        )
    return items, total


def stats(user: User) -> dict[str, int]:
    """Números do início: publicadas, rascunhos, leituras em 30 dias e comentários aprovados
    (total nas minhas publicadas, de Article.comments_count)."""
    counts = status_counts(user)
    published = my_articles(user, "publicados").order_by()
    return {
        "published": counts["publicados"],
        "drafts": counts["rascunhos"],
        "reads_30d": engagement.reads_since(published.values("pk"), days=30),
        "comments_approved": published.aggregate(total=Sum("comments_count"))["total"] or 0,
    }
