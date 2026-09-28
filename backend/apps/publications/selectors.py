"""Consultas usadas pelas telas de publicações."""

from dataclasses import dataclass

from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    SearchRank,
    TrigramSimilarity,
    TrigramWordSimilarity,
)
from django.db.models import Count, F, Max, Prefetch, Q, QuerySet, Value
from django.db.models.functions import Coalesce, Greatest, NullIf
from django.utils import timezone

from apps.accounts.models import User
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea, Topic

from . import search
from .models import Article, ArticleContributor
from .search import SEARCH_CONFIG


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


# Pesos do "Leia também" (docs/11, E43): um tópico em comum vale duas disciplinas.
RELATED_TOPIC_WEIGHT = 2
RELATED_DISCIPLINE_WEIGHT = 1


def _count_common(relation: str, ids: list[int]) -> Count | Value:
    """Quantos itens da relação estão em ids (lista vazia: zero, sem IN () no SQL)."""
    if not ids:
        return Value(0)
    return Count(relation, filter=Q(**{f"{relation}__in": ids}), distinct=True)


def related_articles(article: Article, limit: int = 3) -> list[Article]:
    """Leia também (docs/11): publicadas que compartilham tópico ou disciplina.

    Pontuação: tópicos em comum valem 2, disciplinas em comum valem 1; empate vai para a mais
    recente. Se faltar, completa com as mais recentes da mesma área. Nunca inclui a própria.
    """
    discipline_ids = [d.pk for d in article.disciplines.all()]
    topic_ids = [t.pk for t in article.topics.all()]
    area_ids = {d.area_id for d in article.disciplines.all()}
    if not discipline_ids and not topic_ids:
        return []
    scored = (
        published()
        .exclude(pk=article.pk)
        .annotate(
            common_topics=_count_common("topics", topic_ids),
            common_disciplines=_count_common("disciplines", discipline_ids),
        )
        .annotate(
            score=F("common_topics") * RELATED_TOPIC_WEIGHT
            + F("common_disciplines") * RELATED_DISCIPLINE_WEIGHT
        )
        .filter(score__gt=0)
        .order_by("-score", "-published_at", "-pk")
    )
    chosen = list(for_cards(scored)[:limit])
    missing = limit - len(chosen)
    if missing > 0 and area_ids:
        same_area = Article.objects.filter(disciplines__area__in=area_ids).values("pk")
        fallback = (
            published()
            .filter(pk__in=same_area)
            .exclude(pk__in=[article.pk, *(a.pk for a in chosen)])
            .order_by("-published_at", "-pk")
        )
        chosen += list(for_cards(fallback)[:missing])
    return chosen


def public_topics(article: Article) -> list[Topic]:
    """Tópicos ativos da publicação, para as etiquetas que levam à página de tópico."""
    return [topic for topic in article.topics.all() if topic.is_active]


def topic_disciplines(topic: Topic) -> list[Discipline]:
    """Disciplinas relacionadas ao tópico: as sugeridas e as das publicações no ar com ele."""
    used = Article.objects.filter(status=Article.Status.PUBLISHED, topics=topic).values(
        "disciplines"
    )
    return list(
        Discipline.objects.filter(is_active=True, area__is_active=True)
        .filter(Q(topics=topic) | Q(pk__in=used))
        .select_related("area")
        .distinct()
    )


def published() -> QuerySet[Article]:
    return Article.objects.filter(status=Article.Status.PUBLISHED).order_by("-published_at")


# Pesos de SearchRank na ordem D, C, B, A (docs/19): título vale 10 vezes o corpo.
SEARCH_RANK_WEIGHTS = [0.1, 0.2, 0.4, 1.0]


def search_published(query: str) -> QuerySet[Article]:
    """Busca pública: só publicadas, sem acento, por radical, da mais relevante à menos.

    Aceita a sintaxe de buscador (websearch): "entre aspas" para frase e -palavra para excluir.
    Cada resultado vem com `rank`; empate vai para a publicação mais recente.
    """
    query = search.clean_query(query)
    if not query:
        return Article.objects.none()
    search_query = SearchQuery(query, config=SEARCH_CONFIG, search_type="websearch")
    return (
        Article.objects.filter(status=Article.Status.PUBLISHED, search_vector=search_query)
        .annotate(rank=SearchRank(F("search_vector"), search_query, weights=SEARCH_RANK_WEIGHTS))
        .order_by("-rank", "-published_at")
    )


# Fallback por trigramas no título (docs/19): parecido com o título inteiro (> 0.3) ou com
# algum trecho dele (> 0.5), para tolerar erro de digitação numa palavra de um título longo.
TITLE_SIMILARITY = 0.3
TITLE_WORD_SIMILARITY = 0.5


def search_published_similar_titles(query: str) -> QuerySet[Article]:
    """Publicadas com título parecido com o termo, sem acento, da mais parecida à menos."""
    words = search.plain_words(search.clean_query(query))
    if len(words) < 3:
        return Article.objects.none()
    term = search.Unaccent(Value(words))
    title = search.Unaccent("title")
    return (
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .annotate(
            title_similarity=TrigramSimilarity(title, term),
            title_word_similarity=TrigramWordSimilarity(term, title),
        )
        .filter(
            Q(title_similarity__gt=TITLE_SIMILARITY)
            | Q(title_word_similarity__gt=TITLE_WORD_SIMILARITY)
        )
        .order_by(Greatest("title_similarity", "title_word_similarity").desc(), "-published_at")
    )


def with_headlines(queryset: QuerySet[Article], query: str) -> QuerySet[Article]:
    """Acrescenta `headline`: trecho do corpo com os termos entre as marcas de search.py."""
    search_query = SearchQuery(
        search.clean_query(query), config=search.SEARCH_CONFIG, search_type="websearch"
    )
    return queryset.annotate(
        headline=SearchHeadline(
            "body_text",
            search_query,
            config=search.SEARCH_CONFIG,
            start_sel=search.MARK_START,
            stop_sel=search.MARK_STOP,
            min_words=25,
            max_words=40,
        )
    )


# Pessoas (docs/19): nome parecido (> 0.25) ou contido; apresentação curta ou disciplina que
# contenha o termo, com tolerância a erro de digitação.
PERSON_SIMILARITY = 0.25
PERSON_WORD_SIMILARITY = 0.5
PEOPLE_LIMIT = 5


def search_people(query: str, limit: int = PEOPLE_LIMIT) -> list[User]:
    """Equipe com perfil público que combina com o termo (nome, apresentação, disciplinas)."""
    words = search.plain_words(search.clean_query(query))
    if len(words) < 2:
        return []
    term = search.Unaccent(Value(words))
    name = search.Unaccent(Coalesce(NullIf("display_name", Value("")), "full_name"))
    headline = search.Unaccent(Coalesce("profile__headline", Value("")))
    by_discipline = User.objects.filter(
        profile__disciplines__is_active=True,
        profile__disciplines__name__unaccent__icontains=words,
    ).values("pk")
    people = writers(limit=None).annotate(
        name_similarity=TrigramSimilarity(name, term),
        name_word_similarity=TrigramWordSimilarity(term, name),
        headline_similarity=TrigramWordSimilarity(term, headline),
    )
    return list(
        people.filter(
            Q(name_similarity__gt=PERSON_SIMILARITY)
            | Q(name_word_similarity__gt=PERSON_WORD_SIMILARITY)
            | Q(headline_similarity__gt=PERSON_WORD_SIMILARITY)
            | Q(pk__in=by_discipline)
        ).order_by(
            Greatest("name_similarity", "name_word_similarity", "headline_similarity").desc(),
            F("last_published").desc(nulls_last=True),
            "full_name",
        )[:limit]
    )


@dataclass
class TaxonomyMatches:
    areas: list[KnowledgeArea]
    disciplines: list[Discipline]
    topics: list[Topic]

    def __bool__(self) -> bool:
        return bool(self.areas or self.disciplines or self.topics)


def search_taxonomy(query: str, limit: int = 12) -> TaxonomyMatches:
    """Áreas, disciplinas e tópicos ativos cujo nome contém o termo, sem acento (docs/19)."""
    words = search.plain_words(search.clean_query(query))
    if len(words) < 2:
        return TaxonomyMatches([], [], [])
    areas = KnowledgeArea.objects.filter(is_active=True).filter(
        Q(name__unaccent__icontains=words) | Q(short_name__unaccent__icontains=words)
    )
    disciplines = Discipline.objects.filter(
        is_active=True, area__is_active=True, name__unaccent__icontains=words
    ).select_related("area")
    topics = Topic.objects.filter(is_active=True, name__unaccent__icontains=words)
    return TaxonomyMatches(
        areas=list(areas[:limit]),
        disciplines=list(disciplines[:limit]),
        topics=list(topics[:limit]),
    )


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
    events = for_cards(published().filter(type__has_event_date=True, event_at__isnull=False))
    today = _start_of_today()
    upcoming = list(events.filter(event_at__gte=today).order_by("event_at")[:limit])
    if upcoming:
        return upcoming, False
    return list(events.filter(event_at__lt=today).order_by("-event_at")[:1]), True


def _start_of_today():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def agenda() -> tuple[QuerySet[Article], QuerySet[Article]]:
    """Página /agenda/: (próximos em ordem de data, já aconteceram do mais recente)."""
    events = for_cards(published().filter(type__has_event_date=True, event_at__isnull=False))
    today = _start_of_today()
    return (
        events.filter(event_at__gte=today).order_by("event_at"),
        events.filter(event_at__lt=today).order_by("-event_at"),
    )


def writers_about(
    area: KnowledgeArea, discipline: Discipline | None = None, limit: int | None = 12
) -> QuerySet[User]:
    """Quem escreve sobre a área (ou disciplina): pelo perfil ou por já ter publicado nela."""
    ids = writer_ids_about(area, discipline)
    return writers(limit=limit, queryset=User.objects.filter(pk__in=ids))


def writer_ids_about(area: KnowledgeArea, discipline: Discipline | None = None) -> QuerySet:
    """Ids de quem marcou a área (ou disciplina) no perfil ou já publicou nela."""
    if discipline:
        by_profile = Q(profile__disciplines=discipline)
        by_articles = Q(contributions__article__disciplines=discipline)
    else:
        by_profile = Q(profile__areas=area) | Q(profile__disciplines__area=area)
        by_articles = Q(contributions__article__disciplines__area=area)
    published_by = by_articles & Q(
        contributions__role__in=ArticleContributor.EDITING_ROLES,
        contributions__article__status=Article.Status.PUBLISHED,
    )
    return User.objects.filter(by_profile | published_by).values("pk")


def recent_for_area_strips(limit: int = 60) -> list[Article]:
    """Publicações recentes para montar as faixas por área sem uma consulta por área."""
    return list(for_cards(published())[:limit])


def writers(limit: int | None = 8, queryset: QuerySet[User] | None = None) -> QuerySet[User]:
    """Quem escreve: equipe com perfil público, quem publicou por último primeiro.

    Com limit=None devolve a consulta sem corte, para somar filtros e anotações.
    """
    base = queryset if queryset is not None else User.objects.all()
    people = (
        base.filter(is_active=True, is_approved=True, profile__is_public=True)
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
        .order_by(F("last_published").desc(nulls_last=True), "full_name")
    )
    return people if limit is None else people[:limit]


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


def chosen_featured() -> list[Article]:
    """Só os destaques marcados por editor+, na ordem da home (tela de destaques)."""
    return list(
        for_cards(
            published()
            .filter(is_featured=True)
            .order_by(F("featured_order").asc(nulls_last=True), "-published_at")
        )
    )


def featured_candidates(query: str = "", limit: int = 8) -> list[Article]:
    """Publicadas com capa que ainda não são destaque, filtradas pelo título."""
    candidates = published().filter(cover__isnull=False, is_featured=False)
    query = " ".join(query.split())
    if query:
        candidates = candidates.filter(title__icontains=query)
    return list(candidates.select_related("type", "cover")[:limit])
