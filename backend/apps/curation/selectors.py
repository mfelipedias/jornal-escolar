"""Consultas da tela de sugestões (E48; docs/15 "Sugestões e Pautas", docs/21 "Tela de
sugestões")."""

from dataclasses import dataclass, field

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import User
from apps.editorial import permissions
from apps.taxonomy.models import Discipline, Topic

from .classify import VISIBLE_SCORE
from .models import NewsItemClassification, NewsRecommendation, NewsSource, StoryIdea

Status = NewsRecommendation.Status

# aba → (rótulo, filtro)
TABS: dict[str, tuple[str, Q]] = {
    "para-voce": ("Para você", Q(status=Status.SUGGESTED)),
    "salvas": ("Salvas", Q(status__in=(Status.SAVED, Status.INTERESTING, Status.CONVERTED))),
    # As que expiraram sozinhas não aparecem: a pessoa não as ignorou.
    "ignoradas": ("Ignoradas", Q(status=Status.IGNORED, acted_at__isnull=False)),
}
DEFAULT_TAB = "para-voce"
LANGUAGES = NewsSource.Language.choices
MAX_TAGS = 3


@dataclass
class Filters:
    topic: Topic | None = None
    source: NewsSource | None = None
    language: str = ""

    @property
    def active(self) -> bool:
        return bool(self.topic or self.source or self.language)

    def query(self) -> str:
        parts = []
        if self.topic:
            parts.append(f"topico={self.topic.slug}")
        if self.source:
            parts.append(f"fonte={self.source.pk}")
        if self.language:
            parts.append(f"idioma={self.language}")
        return "&".join(parts)


def parse_filters(params) -> Filters:
    filters = Filters()
    slug = params.get("topico", "")
    if slug:
        filters.topic = Topic.objects.filter(slug=slug, is_active=True).first()
    source = params.get("fonte", "")
    if source.isdigit():
        filters.source = NewsSource.objects.filter(pk=source).first()
    if params.get("idioma") in dict(LANGUAGES):
        filters.language = params["idioma"]
    return filters


def _base(user: User) -> QuerySet[NewsRecommendation]:
    return NewsRecommendation.objects.filter(user=user, item__is_hidden=False)


def _filtered(qs: QuerySet[NewsRecommendation], filters: Filters) -> QuerySet:
    if filters.topic:
        qs = qs.filter(
            item__classifications__topic=filters.topic,
            item__classifications__score__gte=VISIBLE_SCORE,
        )
    if filters.source:
        qs = qs.filter(item__source=filters.source)
    if filters.language:
        qs = qs.filter(item__language=filters.language)
    return qs.distinct()


def recommendations(user: User, tab: str, filters: Filters) -> QuerySet[NewsRecommendation]:
    qs = _filtered(_base(user).filter(TABS[tab][1]), filters).select_related("item__source")
    if tab == "para-voce":
        return qs.order_by("-score", "-item__published_at", "-pk")
    return qs.order_by("-acted_at", "-pk")


def tab_counts(user: User, filters: Filters) -> dict[str, int]:
    qs = _filtered(_base(user), filters)
    return {key: qs.filter(condition).count() for key, (_, condition) in TABS.items()}


def suggestion_count(user: User) -> int:
    """Contador do menu: sugestões ainda não vistas pela pessoa."""
    if not user.is_authenticated:
        return 0
    return _base(user).filter(status=Status.SUGGESTED).count()


def top_suggestions(user: User, limit: int = 3) -> list["Card"]:
    """Bloco "Sugestões para você" do início do painel."""
    recs = list(recommendations(user, "para-voce", Filters())[:limit])
    return cards(user, recs)


def filter_options(user: User) -> dict:
    """Tópicos e fontes que aparecem nas sugestões da pessoa, para os filtros."""
    items = NewsRecommendation.objects.filter(user=user).values("item")
    topics = Topic.objects.filter(
        is_active=True,
        news_classifications__item__in=items,
        news_classifications__score__gte=VISIBLE_SCORE,
    ).distinct()
    sources = NewsSource.objects.filter(items__in=items).distinct()
    return {"topics": topics.order_by("name"), "sources": sources.order_by("name")}


@dataclass
class Card:
    """Uma sugestão pronta para o template (docs/21, "Tela de sugestões")."""

    rec: NewsRecommendation
    topics: list[Topic] = field(default_factory=list)
    disciplines: list[Discipline] = field(default_factory=list)
    colleagues_interested: int = 0

    @property
    def item(self):
        return self.rec.item

    @property
    def discipline_names(self) -> str:
        return ", ".join(d.name for d in self.disciplines)

    @property
    def trust_dots(self) -> list[bool]:
        return [n < self.rec.item.source.trust_level for n in range(5)]


def cards(user: User, recs: list[NewsRecommendation]) -> list[Card]:
    item_ids = [rec.item_id for rec in recs]
    topics: dict[int, list[tuple[float, Topic]]] = {}
    disciplines: dict[int, list[tuple[float, Discipline]]] = {}
    rows = (
        NewsItemClassification.objects.filter(item_id__in=item_ids, score__gte=VISIBLE_SCORE)
        .select_related("topic", "discipline")
        .order_by("-score")
    )
    for row in rows:
        if row.topic and row.topic.is_active:
            bucket = topics.setdefault(row.item_id, [])
            if all(t.pk != row.topic_id for _, t in bucket):
                bucket.append((row.score, row.topic))
        elif row.discipline and row.discipline.is_active:
            bucket = disciplines.setdefault(row.item_id, [])
            if all(d.pk != row.discipline_id for _, d in bucket):
                bucket.append((row.score, row.discipline))
    interested: dict[int, int] = {}
    if permissions.is_editor(user):
        # Sinal para os editores: quantos colegas acharam a notícia interessante (docs/21).
        interested = dict(
            NewsRecommendation.objects.filter(item_id__in=item_ids, status=Status.INTERESTING)
            .exclude(user=user)
            .values("item_id")
            .annotate(total=Count("pk"))
            .values_list("item_id", "total")
        )
    return [
        Card(
            rec=rec,
            topics=[t for _, t in topics.get(rec.item_id, [])][:MAX_TAGS],
            disciplines=[d for _, d in disciplines.get(rec.item_id, [])][:MAX_TAGS],
            colleagues_interested=interested.get(rec.item_id, 0),
        )
        for rec in recs
    ]


# --- quadro de pautas (E49) ---

IdeaStatus = StoryIdea.Status
BOARD_COLUMNS = (
    (IdeaStatus.OPEN, "Abertas", "Qualquer pessoa da equipe pode pegar."),
    (IdeaStatus.ASSIGNED, "Atribuídas", "Com alguém, ainda sem rascunho."),
    (IdeaStatus.IN_PROGRESS, "Em produção", "Com rascunho no editor."),
    (IdeaStatus.DONE, "Concluídas", "Viraram publicação."),
)
DONE_LIMIT = 20


@dataclass
class IdeaCard:
    idea: StoryIdea
    can_edit: bool
    can_take: bool
    can_release: bool
    can_start_draft: bool
    can_delete: bool
    is_mine: bool


def idea_card(user: User, idea: StoryIdea) -> IdeaCard:
    return IdeaCard(
        idea=idea,
        can_edit=permissions.can_edit_story_idea(user, idea),
        can_take=permissions.can_take_story_idea(user, idea),
        can_release=permissions.can_release_story_idea(user, idea),
        can_start_draft=permissions.can_start_draft(user, idea),
        can_delete=permissions.can_delete_story_idea(user, idea),
        is_mine=idea.assigned_to_id == user.pk,
    )


def board(user: User, only_mine: bool = False) -> list[dict]:
    ideas = StoryIdea.objects.select_related(
        "proposed_by", "assigned_to", "item__source", "article"
    ).prefetch_related("topics")
    if only_mine:
        ideas = ideas.filter(Q(assigned_to=user) | Q(proposed_by=user))
    columns = []
    for status, label, help_text in BOARD_COLUMNS:
        column = ideas.filter(status=status)
        if status == IdeaStatus.DONE:
            column = column.order_by("-done_at")[:DONE_LIMIT]
        else:
            column = column.order_by("-updated_at")
        columns.append(
            {
                "key": status,
                "label": label,
                "help": help_text,
                "cards": [idea_card(user, idea) for idea in column],
            }
        )
    return columns


def my_idea_count(user: User) -> int:
    """Contador do menu: pautas com a pessoa ainda não concluídas."""
    if not user.is_authenticated:
        return 0
    return StoryIdea.objects.filter(
        assigned_to=user, status__in=(IdeaStatus.ASSIGNED, IdeaStatus.IN_PROGRESS)
    ).count()
