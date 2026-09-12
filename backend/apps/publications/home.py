"""Blocos da página inicial (docs/10).

Destaque, agenda, quem escreve e faixas por área ficam 5 minutos em cache e são refeitos
quando algo publicado muda (cache.py). "Últimas publicações" é paginada e sempre consultada.
"""

from dataclasses import dataclass, field

from django.core.cache import cache
from django.core.paginator import Page, Paginator

from apps.accounts.models import User
from apps.taxonomy.models import KnowledgeArea

from . import presentation, selectors
from .cache import public_version
from .models import Article

CACHE_SECONDS = 5 * 60
LATEST_PER_PAGE = 6
STRIP_LIMIT = 5
STRIP_CARDS = 3
MIN_FOR_STRIPS = 6  # com poucas publicações as faixas repetiriam o destaque


@dataclass
class AreaStrip:
    area: KnowledgeArea
    cards: list[presentation.ArticleCard]


@dataclass
class HomeBlocks:
    has_content: bool
    featured: list[presentation.ArticleCard] = field(default_factory=list)
    featured_ids: list[int] = field(default_factory=list)
    events: list[Article] = field(default_factory=list)
    events_past: bool = False
    writers: list[presentation.Credit] = field(default_factory=list)
    strips: list[AreaStrip] = field(default_factory=list)


def _writer(user: User) -> presentation.Credit:
    profile = getattr(user, "profile", None)
    return presentation.Credit(
        name=user.public_name,
        detail=(profile.headline if profile else "") or user.get_staff_kind_display(),
        is_staff=True,
        avatar_url=user.avatar.variant_url("w480") if user.avatar_id else "",
    )


def _strips(articles: list[Article], skip_ids: set[int]) -> list[AreaStrip]:
    """Uma faixa por área, na ordem configurada, com as 3 mais recentes daquela área principal."""
    by_area: dict[int, AreaStrip] = {}
    for article in articles:
        if article.pk in skip_ids:
            continue
        area = presentation.main_area(article)
        if area is None or not area.is_active:
            continue
        strip = by_area.setdefault(area.pk, AreaStrip(area=area, cards=[]))
        if len(strip.cards) < STRIP_CARDS:
            strip.cards.append(presentation.card(article))
    ordered = sorted(by_area.values(), key=lambda s: (s.area.order, s.area.name))
    return ordered[:STRIP_LIMIT]


def build_blocks() -> HomeBlocks:
    featured = selectors.featured_articles()
    if not featured:
        return HomeBlocks(has_content=False)
    featured_ids = [a.pk for a in featured]
    events, events_past = selectors.upcoming_events()
    recent = selectors.recent_for_area_strips()
    strips = _strips(recent, set(featured_ids)) if len(recent) >= MIN_FOR_STRIPS else []
    return HomeBlocks(
        has_content=True,
        featured=[presentation.card(a) for a in featured],
        featured_ids=featured_ids,
        events=events,
        events_past=events_past,
        writers=[_writer(u) for u in selectors.writers()],
        strips=strips,
    )


def blocks() -> HomeBlocks:
    key = f"home:blocks:v{public_version()}"
    return cache.get_or_set(key, build_blocks, CACHE_SECONDS)


def latest_page(featured_ids: list[int], number: str | int | None) -> tuple[Page, list]:
    """Últimas publicações sem as do destaque, 6 por página, com os cards montados."""
    paginator = Paginator(selectors.latest_articles(featured_ids), LATEST_PER_PAGE)
    page_obj = paginator.get_page(number)
    return page_obj, [presentation.card(a) for a in page_obj]
