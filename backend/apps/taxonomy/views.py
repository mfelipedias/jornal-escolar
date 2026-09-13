"""Páginas públicas de área, disciplina e tipo (docs/12, E21).

São a lista de publicações com um filtro fixo e um cabeçalho próprio.
"""

from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.publications import listing, presentation, selectors

from .models import ArticleType, Discipline, KnowledgeArea


@require_GET
def area(request: HttpRequest, slug: str) -> HttpResponse:
    area = get_object_or_404(
        KnowledgeArea.objects.prefetch_related(
            Prefetch("disciplines", queryset=Discipline.objects.filter(is_active=True))
        ),
        slug=slug,
        is_active=True,
    )
    filters = listing.parse(request.GET, fixed_area=area)
    # Destaque: a mais recente da área, se tiver capa (docs/12), só na lista sem filtros.
    # Calculado também no "Carregar mais", para as páginas seguintes não repetirem cards.
    hero = None
    if not filters.has_user_filters:
        latest = selectors.for_cards(listing.apply(selectors.published(), filters)).first()
        if latest and latest.cover_id:
            hero = latest
    context = {
        "area": area,
        "hero": presentation.card(hero) if hero else None,
        "writers": [presentation.writer(u) for u in selectors.writers_about(area)],
    }
    return listing.render_listing(
        request,
        "taxonomy/area.html",
        filters,
        exclude_ids=[hero.pk] if hero else None,
        context=context,
    )


@require_GET
def discipline(request: HttpRequest, slug: str) -> HttpResponse:
    discipline = get_object_or_404(
        Discipline.objects.select_related("area"), slug=slug, is_active=True, area__is_active=True
    )
    filters = listing.parse(request.GET, fixed_discipline=discipline)
    context = {
        "discipline": discipline,
        "area": discipline.area,
        "writers": [
            presentation.writer(u)
            for u in selectors.writers_about(discipline.area, discipline=discipline)
        ],
    }
    return listing.render_listing(request, "taxonomy/discipline.html", filters, context=context)


@require_GET
def article_type(request: HttpRequest, slug: str) -> HttpResponse:
    article_type = get_object_or_404(ArticleType, slug=slug, is_active=True)
    filters = listing.parse(request.GET, fixed_type=article_type)
    return listing.render_listing(
        request, "taxonomy/type.html", filters, context={"article_type": article_type}
    )
