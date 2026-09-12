"""Consultas usadas pelas telas de publicações."""

from django.db.models import Prefetch, Q, QuerySet

from apps.accounts.models import User
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea, Topic

from .models import Article, ArticleContributor


def active_types() -> QuerySet[ArticleType]:
    return ArticleType.objects.filter(is_active=True)


def areas_with_disciplines() -> QuerySet[KnowledgeArea]:
    return KnowledgeArea.objects.filter(is_active=True).prefetch_related(
        Prefetch("disciplines", queryset=Discipline.objects.filter(is_active=True))
    )


def active_topics() -> QuerySet[Topic]:
    return Topic.objects.filter(is_active=True)


def contributors(article: Article) -> QuerySet[ArticleContributor]:
    return article.contributors.select_related("user").order_by("order", "pk")


def search_staff_for_credit(article: Article, query: str, limit: int = 8) -> QuerySet[User]:
    """Colegas ativos pelo nome ou e-mail, sem quem já está creditado nesta publicação."""
    query = " ".join(query.split())
    if len(query) < 2:
        return User.objects.none()
    already = article.contributors.filter(user__isnull=False).values_list("user_id", flat=True)
    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(full_name__icontains=query)
            | Q(display_name__icontains=query)
            | Q(email__icontains=query)
        )
        .exclude(pk__in=already)
        .order_by("full_name")[:limit]
    )
