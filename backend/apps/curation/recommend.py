"""Sugestões de notícias para cada professor (E48; docs/21, "Recomendação").

Para cada pessoa da equipe com tópicos ou disciplinas no perfil, cada notícia recebe:

    score = 0,5 * maior score da notícia entre os tópicos que a pessoa marcou
          + 0,2 se a notícia tem uma disciplina da pessoa (score 0,4 ou mais)
          + 0,2 * recência (1 hoje → 0 em 14 dias, linear)
          + 0,1 * confiança da fonte / 5
          - 0,3 se a pessoa ignorou 3 ou mais notícias desse tópico nos últimos 30 dias
          + 0,1 se marcou como interessante uma notícia de um desses tópicos (30 dias)
          + 0,05 se marcou como interessante uma notícia dessa fonte (30 dias)
          - 1,0 se a notícia é em inglês e a pessoa não aceita inglês

"Desse tópico" é o tópico dominante (o de maior score) da notícia. Com score 0,45 ou mais,
a notícia vira sugestão. Fontes com confiança 2 ou menos só entram para quem ligou "incluir
fontes de menor confiança". Notícias ocultas no admin não entram.

No máximo 30 sugestões ativas por pessoa: as de notícias mais antigas, e as de notícias com
mais de 14 dias, expiram para "ignorada" sem a pessoa ter feito nada (acted_at vazio), e isso
não conta como ignorar.

Quando roda: depois de cada coleta, para as notícias novas; ao salvar o perfil, para a pessoa;
depois de reclassificar, para todo mundo. Recalcular atualiza o score das sugestões em que a
pessoa ainda não mexeu e apaga as que ficaram abaixo do corte (se o perfil mudou, por
exemplo); as que ela salvou, ignorou ou marcou nunca mudam.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import TeacherProfile, User

from .models import NewsItem, NewsItemClassification, NewsRecommendation, NewsSource

Status = NewsRecommendation.Status

THRESHOLD = 0.45
MAX_ACTIVE = 30
RECENCY_DAYS = 14
FEEDBACK_DAYS = 30
IGNORE_LIMIT = 3
LOW_TRUST_MAX = 2
DISCIPLINE_MIN_SCORE = 0.4

TOPIC_WEIGHT = 0.5
DISCIPLINE_WEIGHT = 0.2
RECENCY_WEIGHT = 0.2
TRUST_WEIGHT = 0.1
IGNORE_PENALTY = 0.3
INTEREST_TOPIC_BONUS = 0.1
INTEREST_SOURCE_BONUS = 0.05
LANGUAGE_PENALTY = 1.0


@dataclass
class ItemFeatures:
    """O que a fórmula precisa saber de uma notícia."""

    item: NewsItem
    topics: dict[int, float] = field(default_factory=dict)
    disciplines: dict[int, float] = field(default_factory=dict)

    @property
    def dominant_topic(self) -> int | None:
        if not self.topics:
            return None
        return max(self.topics.items(), key=lambda pair: (pair[1], -pair[0]))[0]


def features(items: Iterable[NewsItem]) -> list[ItemFeatures]:
    """Score de cada tópico e disciplina (o maior entre os métodos) das notícias dadas."""
    result = {item.pk: ItemFeatures(item) for item in items}
    rows = NewsItemClassification.objects.filter(item_id__in=list(result)).values_list(
        "item_id", "topic_id", "discipline_id", "score"
    )
    for item_id, topic_id, discipline_id, score in rows:
        feat = result[item_id]
        target = feat.topics if topic_id else feat.disciplines
        key = topic_id or discipline_id
        target[key] = max(score, target.get(key, 0.0))
    return list(result.values())


@dataclass
class Interests:
    """O perfil e o histórico de uma pessoa, carregados uma vez."""

    user: User
    topics: set[int]
    disciplines: set[int]
    accepts_english: bool
    include_low_trust: bool
    ignored_topics: set[int] = field(default_factory=set)
    interesting_topics: set[int] = field(default_factory=set)
    interesting_sources: set[int] = field(default_factory=set)

    @property
    def has_interests(self) -> bool:
        return bool(self.topics or self.disciplines)


def interests_for(user: User, now: datetime | None = None) -> Interests | None:
    now = now or timezone.now()
    profile = TeacherProfile.objects.filter(user=user).first()
    if profile is None or not user.is_active:
        return None
    interests = Interests(
        user=user,
        topics=set(profile.topics.filter(is_active=True).values_list("pk", flat=True)),
        disciplines=set(profile.disciplines.filter(is_active=True).values_list("pk", flat=True)),
        accepts_english=profile.accepts_english,
        include_low_trust=profile.include_low_trust,
    )
    recent = (
        NewsRecommendation.objects.filter(
            user=user, acted_at__gte=now - timedelta(days=FEEDBACK_DAYS)
        )
        .filter(status__in=(Status.IGNORED, Status.INTERESTING))
        .select_related("item")
    )
    recent = list(recent)
    by_item = {feat.item.pk: feat for feat in features(rec.item for rec in recent)}
    ignored: Counter[int] = Counter()
    for rec in recent:
        feat = by_item[rec.item_id]
        if rec.status == Status.IGNORED and feat.dominant_topic is not None:
            ignored[feat.dominant_topic] += 1
        elif rec.status == Status.INTERESTING:
            interests.interesting_topics.update(feat.topics)
            interests.interesting_sources.add(rec.item.source_id)
    interests.ignored_topics = {topic for topic, n in ignored.items() if n >= IGNORE_LIMIT}
    return interests


def recency(published_at: datetime, now: datetime) -> float:
    age_days = (now - published_at).total_seconds() / 86400
    return min(1.0, max(0.0, 1 - age_days / RECENCY_DAYS))


def score(interests: Interests, feat: ItemFeatures, now: datetime) -> float:
    item = feat.item
    source: NewsSource = item.source
    topic_part = max((feat.topics.get(t, 0.0) for t in interests.topics), default=0.0)
    has_discipline = any(
        feat.disciplines.get(d, 0.0) >= DISCIPLINE_MIN_SCORE for d in interests.disciplines
    )
    value = (
        TOPIC_WEIGHT * topic_part
        + DISCIPLINE_WEIGHT * has_discipline
        + RECENCY_WEIGHT * recency(item.published_at, now)
        + TRUST_WEIGHT * source.trust_level / 5
    )
    if feat.dominant_topic in interests.ignored_topics:
        value -= IGNORE_PENALTY
    if interests.interesting_topics & set(feat.topics):
        value += INTEREST_TOPIC_BONUS
    if source.pk in interests.interesting_sources:
        value += INTEREST_SOURCE_BONUS
    if item.language == NewsSource.Language.EN and not interests.accepts_english:
        value -= LANGUAGE_PENALTY
    return round(value, 3)


def candidates(now: datetime, item_ids: Iterable[int] | None = None):
    """Notícias que ainda podem ser sugeridas: recentes, visíveis, de fonte ativa."""
    items = NewsItem.objects.filter(
        is_hidden=False,
        source__is_active=True,
        published_at__gt=now - timedelta(days=RECENCY_DAYS),
    ).select_related("source")
    if item_ids is not None:
        items = items.filter(pk__in=list(item_ids))
    return items


def _eligible(interests: Interests, item: NewsItem) -> bool:
    return interests.include_low_trust or item.source.trust_level > LOW_TRUST_MAX


def recommend_for_user(
    user: User,
    item_ids: Iterable[int] | None = None,
    now: datetime | None = None,
    item_features: list[ItemFeatures] | None = None,
) -> int:
    """Calcula as sugestões da pessoa (para as notícias dadas ou todas as recentes). Devolve
    quantas sugestões novas foram criadas."""
    now = now or timezone.now()
    interests = interests_for(user, now)
    if interests is None:
        return 0
    if item_features is None:
        item_features = features(candidates(now, item_ids))
    existing = {
        rec.item_id: rec
        for rec in NewsRecommendation.objects.filter(
            user=user, item_id__in=[feat.item.pk for feat in item_features]
        )
    }
    created: list[NewsRecommendation] = []
    changed: list[NewsRecommendation] = []
    dropped: list[int] = []
    for feat in item_features:
        rec = existing.get(feat.item.pk)
        if rec is not None and rec.status != Status.SUGGESTED:
            continue  # a pessoa já decidiu
        value = score(interests, feat, now) if interests.has_interests else 0.0
        keep = value >= THRESHOLD and _eligible(interests, feat.item)
        if rec is None and keep:
            created.append(NewsRecommendation(user=user, item=feat.item, score=value))
        elif rec is not None and keep and rec.score != value:
            rec.score = value
            changed.append(rec)
        elif rec is not None and not keep:
            dropped.append(rec.pk)
    with transaction.atomic():
        NewsRecommendation.objects.filter(pk__in=dropped).delete()
        NewsRecommendation.objects.bulk_update(changed, ["score", "updated_at"])
        NewsRecommendation.objects.bulk_create(created, ignore_conflicts=True)
        expire(user, now)
    return len(created)


def expire(user: User, now: datetime | None = None) -> int:
    """Sugestões antigas viram "ignoradas" sozinhas: as de notícias com mais de 14 dias e as
    que passam de 30 ativas (ficam as de notícias mais novas)."""
    now = now or timezone.now()
    active = NewsRecommendation.objects.filter(user=user, status=Status.SUGGESTED)
    old = active.filter(item__published_at__lte=now - timedelta(days=RECENCY_DAYS))
    expired = old.update(status=Status.IGNORED, acted_at=None, updated_at=now)
    overflow = list(
        active.order_by("-item__published_at", "-pk").values_list("pk", flat=True)[MAX_ACTIVE:]
    )
    if overflow:
        expired += NewsRecommendation.objects.filter(pk__in=overflow).update(
            status=Status.IGNORED, acted_at=None, updated_at=now
        )
    return expired


def recipients() -> list[User]:
    """Pessoas da equipe ativas com tópicos ou disciplinas no perfil."""
    has_interests = Q(profile__topics__isnull=False) | Q(profile__disciplines__isnull=False)
    return list(User.objects.filter(has_interests, is_active=True).distinct().order_by("pk"))


def recommend_items(item_ids: Iterable[int] | None = None, now: datetime | None = None) -> int:
    """Sugestões para todo mundo (das notícias dadas, ou de todas as recentes)."""
    now = now or timezone.now()
    shared = features(candidates(now, item_ids))
    if not shared:
        return 0
    return sum(recommend_for_user(user, now=now, item_features=shared) for user in recipients())


# --- ações do professor na tela de sugestões ---

ACTIONS = {
    "ignorar": (Status.IGNORED, "Ignorada."),
    "salvar": (Status.SAVED, "Salva. Está na aba Salvas."),
    "interessante": (Status.INTERESTING, "Marcada como interessante."),
    "restaurar": (Status.SUGGESTED, "De volta às sugestões."),
}


def act(user: User, rec: NewsRecommendation, action: str) -> str:
    """Grava a escolha da pessoa. Devolve a mensagem para a tela."""
    if rec.user_id != user.pk:
        raise PermissionError("Sugestão de outra pessoa.")
    if rec.status == Status.CONVERTED:
        raise ValueError("Esta notícia já virou pauta.")
    status, message = ACTIONS[action]
    rec.status = status
    rec.acted_at = None if status == Status.SUGGESTED else timezone.now()
    rec.save(update_fields=["status", "acted_at", "updated_at"])
    return message


def notify_new_suggestions(now: datetime | None = None) -> int:
    """Aviso semanal no sino: "5 sugestões novas para você" (docs/21, riscos). Só para quem tem
    sugestões criadas nos últimos 7 dias e ainda não mexidas."""
    from django.urls import reverse

    from apps.editorial.models import Notification
    from apps.editorial.notifications import notify

    now = now or timezone.now()
    rows = Counter(
        NewsRecommendation.objects.filter(
            status=Status.SUGGESTED,
            created_at__gte=now - timedelta(days=7),
            user__is_active=True,
        ).values_list("user_id", flat=True)
    )
    url = reverse("curation:suggestions")
    for user in User.objects.filter(pk__in=rows):
        total = rows[user.pk]
        text = "1 sugestão nova" if total == 1 else f"{total} sugestões novas"
        notify(user, Notification.Kind.SUGGESTIONS, f"{text} de pauta para você", url=url)
    return len(rows)
