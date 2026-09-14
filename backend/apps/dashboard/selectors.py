"""Consultas do painel da equipe (docs/15): início e "Minhas publicações".

"Minhas" são as publicações em que a pessoa aparece nos créditos: como autora ou coautora
em qualquer estado; em outros papéis (colaboração, edição) só depois de publicadas, porque
rascunhos e arquivados não são visíveis para quem não edita (apps/editorial/permissions.py).
Revisão fica de fora até a Fase 2 (aba "Revisando").
"""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Prefetch, Q, QuerySet
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.selectors import missing_profile_items
from apps.editorial.models import Notification
from apps.publications.models import Article, ArticleContributor

Role = ArticleContributor.Role
Status = Article.Status

HOME_DRAFTS = 3
HOME_PUBLISHED = 3
HOME_NOTIFICATIONS = 5

# Chips de "Minhas publicações": ?estado= → estado do modelo. "Em revisão" e
# "Alterações sugeridas" entram com a revisão por colega (Fase 2).
STATUS_FILTERS: dict[str, tuple[str, str | None]] = {
    "": ("Todos", None),
    "rascunhos": ("Rascunhos", Status.DRAFT),
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
    return (
        articles.select_related("type")
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
    return list(my_articles(user, "publicados").order_by("-published_at", "-pk")[:limit])


@dataclass(frozen=True)
class Pending:
    """Uma linha do bloco "Pendências" do início do painel."""

    kind: str
    message: str
    url: str
    when: datetime | None = None


def pending_items(user: User, limit: int = HOME_NOTIFICATIONS) -> tuple[list[Pending], int]:
    """O que a pessoa precisa ver agora (docs/15, "Início do painel").

    Na Fase 1: avisos não lidos (texto editado, publicado ou arquivado por outra pessoa) e
    "Complete seu perfil". Comentários e revisões entram nas Fases 2 e 3.
    Devolve (itens, total de avisos não lidos).
    """
    unread = Notification.objects.filter(user=user, read_at__isnull=True)
    total = unread.count()
    items = [
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
    """Números do início. Leituras e comentários aprovados entram com a Fase 3."""
    counts = status_counts(user)
    return {"published": counts["publicados"], "drafts": counts["rascunhos"]}
