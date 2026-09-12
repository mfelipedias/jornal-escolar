"""Consultas usadas pelas telas de publicações."""

from django.db.models import F, Max, Prefetch, Q, QuerySet
from django.utils import timezone

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


def _credited_contributors() -> Prefetch:
    return Prefetch(
        "contributors",
        queryset=ArticleContributor.objects.filter(show_in_credits=True)
        .select_related("user", "user__profile", "user__avatar")
        .order_by("order", "pk"),
    )


def _with_disciplines() -> Prefetch:
    return Prefetch("disciplines", queryset=Discipline.objects.select_related("area"))


def for_cards(queryset: QuerySet[Article]) -> QuerySet[Article]:
    """Carrega o que presentation.card() usa, para listas sem uma consulta por card."""
    return queryset.select_related("type", "cover").prefetch_related(
        _with_disciplines(), _credited_contributors()
    )


def article_for_page(**lookup) -> Article | None:
    """Publicação com tudo que a página pública precisa, em poucas consultas."""
    return (
        Article.objects.select_related("type", "cover")
        .prefetch_related(_with_disciplines(), "topics", _credited_contributors())
        .filter(**lookup)
        .first()
    )


def related_articles(article: Article, limit: int = 3) -> list[Article]:
    """Leia também: publicadas que compartilham disciplina ou tópico, mais recentes (docs/11)."""
    discipline_ids = [d.pk for d in article.disciplines.all()]
    topic_ids = [t.pk for t in article.topics.all()]
    if not discipline_ids and not topic_ids:
        return []
    related = (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .filter(Q(disciplines__in=discipline_ids) | Q(topics__in=topic_ids))
        .exclude(pk=article.pk)
        .distinct()
        .order_by("-published_at")
    )
    return list(for_cards(related)[:limit])


def published() -> QuerySet[Article]:
    return Article.objects.filter(status=Article.Status.PUBLISHED).order_by("-published_at")


def featured_articles(limit: int = 3) -> list[Article]:
    """Destaque da home: marcadas por editor+, completadas pelas mais recentes (docs/10)."""
    chosen = list(
        for_cards(
            published()
            .filter(is_featured=True)
            .order_by(F("featured_order").asc(nulls_last=True), "-published_at")
        )[:limit]
    )
    if len(chosen) < limit:
        recent = for_cards(published().exclude(pk__in=[a.pk for a in chosen]))
        chosen += list(recent[: limit - len(chosen)])
    return chosen


def latest_articles(exclude_ids: list[int]) -> QuerySet[Article]:
    return for_cards(published().exclude(pk__in=exclude_ids))


def upcoming_events(limit: int = 4) -> tuple[list[Article], bool]:
    """Agenda: eventos a partir de hoje; sem nenhum, o último que já aconteceu.

    Devolve (eventos, já_aconteceu).
    """
    events = published().filter(type__has_event_date=True, event_at__isnull=False)
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    upcoming = list(events.filter(event_at__gte=today).order_by("event_at")[:limit])
    if upcoming:
        return upcoming, False
    return list(events.filter(event_at__lt=today).order_by("-event_at")[:1]), True


def recent_for_area_strips(limit: int = 60) -> list[Article]:
    """Publicações recentes para montar as faixas por área sem uma consulta por área."""
    return list(for_cards(published())[:limit])


def writers(limit: int = 8) -> QuerySet[User]:
    """Quem escreve: equipe com perfil público, quem publicou por último primeiro."""
    return (
        User.objects.filter(is_active=True, profile__is_public=True)
        .select_related("profile", "avatar")
        .annotate(
            last_published=Max(
                "contributions__article__published_at",
                filter=Q(
                    contributions__role__in=ArticleContributor.EDITING_ROLES,
                    contributions__article__status=Article.Status.PUBLISHED,
                ),
            )
        )
        .order_by(F("last_published").desc(nulls_last=True), "full_name")[:limit]
    )


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
