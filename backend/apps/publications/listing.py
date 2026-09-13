"""Listas de publicações com filtros por GET (docs/12, E21).

Usado por /publicacoes/ e pelas páginas de área, disciplina e tipo, que chegam com um
filtro fixo. Parâmetros da URL: area (um), disciplina e tipo (vários), pagina.
Filtros por professor, período e ordem chegam na E37.
"""

from dataclasses import dataclass, field

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render

from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea

from . import presentation, selectors
from .models import Article

PER_PAGE = 12


@dataclass
class Chip:
    label: str
    remove_url: str = ""  # vazio: filtro fixo da página, não removível


@dataclass
class ListingFilters:
    area: KnowledgeArea | None = None
    disciplines: list[Discipline] = field(default_factory=list)
    types: list[ArticleType] = field(default_factory=list)
    fixed_area: KnowledgeArea | None = None
    fixed_discipline: Discipline | None = None
    fixed_type: ArticleType | None = None

    @property
    def effective_area(self) -> KnowledgeArea | None:
        return self.fixed_area or self.area

    @property
    def effective_disciplines(self) -> list[Discipline]:
        return [self.fixed_discipline] if self.fixed_discipline else self.disciplines

    @property
    def effective_types(self) -> list[ArticleType]:
        return [self.fixed_type] if self.fixed_type else self.types

    @property
    def has_user_filters(self) -> bool:
        return bool(self.area or self.disciplines or self.types)


def parse(
    query: QueryDict,
    *,
    fixed_area: KnowledgeArea | None = None,
    fixed_discipline: Discipline | None = None,
    fixed_type: ArticleType | None = None,
) -> ListingFilters:
    """Lê a URL ignorando valores desconhecidos e o que a página já fixa."""
    filters = ListingFilters(
        fixed_area=fixed_area, fixed_discipline=fixed_discipline, fixed_type=fixed_type
    )
    if not (fixed_area or fixed_discipline) and query.get("area"):
        filters.area = KnowledgeArea.objects.filter(is_active=True, slug=query["area"]).first()
    if not fixed_discipline:
        slugs = query.getlist("disciplina")
        disciplines = Discipline.objects.filter(is_active=True, slug__in=slugs)
        area = filters.effective_area
        if area:
            disciplines = disciplines.filter(area=area)
        filters.disciplines = list(disciplines.select_related("area")) if slugs else []
    if not fixed_type and query.getlist("tipo"):
        slugs = query.getlist("tipo")
        filters.types = list(ArticleType.objects.filter(is_active=True, slug__in=slugs))
    return filters


def apply(queryset: QuerySet[Article], filters: ListingFilters) -> QuerySet[Article]:
    conditions = Q()
    if area := filters.effective_area:
        conditions &= Q(disciplines__area=area)
    if disciplines := filters.effective_disciplines:
        conditions &= Q(disciplines__in=disciplines)
    if types := filters.effective_types:
        conditions &= Q(type__in=types)
    if not conditions:
        return queryset
    matching = Article.objects.filter(conditions).values("pk")
    return queryset.filter(pk__in=matching)  # subconsulta: sem linhas repetidas pelo M2M


def _without(query: QueryDict, key: str, value: str | None = None) -> str:
    copy = query.copy()
    copy.pop("pagina", None)
    if value is None:
        copy.pop(key, None)
        if key == "area":  # disciplinas dependem da área escolhida
            copy.pop("disciplina", None)
    else:
        copy.setlist(key, [v for v in copy.getlist(key) if v != value])
    encoded = copy.urlencode()
    return f"?{encoded}" if encoded else "?"


def chips(filters: ListingFilters, query: QueryDict) -> list[Chip]:
    result: list[Chip] = []
    if filters.fixed_area:
        result.append(Chip(f"Área: {filters.fixed_area.name}"))
    if filters.fixed_discipline:
        result.append(Chip(f"Disciplina: {filters.fixed_discipline.name}"))
    if filters.fixed_type:
        result.append(Chip(f"Tipo: {filters.fixed_type.name}"))
    if filters.area:
        result.append(Chip(f"Área: {filters.area.name}", _without(query, "area")))
    for discipline in filters.disciplines:
        result.append(Chip(discipline.name, _without(query, "disciplina", discipline.slug)))
    for article_type in filters.types:
        result.append(Chip(article_type.name, _without(query, "tipo", article_type.slug)))
    return result


@dataclass
class FilterOptions:
    """O que o formulário oferece: só o que a página não fixou."""

    areas: list[KnowledgeArea]
    disciplines: list[Discipline]
    types: list[ArticleType]


def options(filters: ListingFilters) -> FilterOptions:
    locked_area = filters.fixed_area or (
        filters.fixed_discipline.area if filters.fixed_discipline else None
    )
    areas = [] if locked_area else list(KnowledgeArea.objects.filter(is_active=True))
    disciplines: list[Discipline] = []
    if not filters.fixed_discipline:
        qs = Discipline.objects.filter(is_active=True, area__is_active=True).select_related("area")
        if area := filters.effective_area:
            qs = qs.filter(area=area)
        disciplines = list(qs)
    types = [] if filters.fixed_type else list(ArticleType.objects.filter(is_active=True))
    return FilterOptions(areas=areas, disciplines=disciplines, types=types)


def page(queryset: QuerySet[Article], number: str | None) -> tuple[Page, list]:
    page_obj = Paginator(selectors.for_cards(queryset), PER_PAGE).get_page(number)
    return page_obj, [presentation.card(a) for a in page_obj]


def render_listing(
    request: HttpRequest,
    template: str,
    filters: ListingFilters,
    *,
    exclude_ids: list[int] | None = None,
    context: dict | None = None,
) -> HttpResponse:
    """Página de lista completa ou, com HTMX e ?pagina=N, só os próximos cards."""
    queryset = apply(selectors.published(), filters)
    if exclude_ids:
        queryset = queryset.exclude(pk__in=exclude_ids)
    page_obj, cards = page(queryset, request.GET.get("pagina"))
    full_context = {
        "filters": filters,
        "page_obj": page_obj,
        "cards": cards,
        **(context or {}),
    }
    if request.headers.get("HX-Request") == "true" and "pagina" in request.GET:
        return render(request, "publications/partials/list_more.html", full_context)
    full_context["chips"] = chips(filters, request.GET)
    full_context["options"] = options(filters)
    full_context["selected"] = {
        "area": filters.area.slug if filters.area else "",
        "disciplinas": {d.slug for d in filters.disciplines},
        "tipos": {t.slug for t in filters.types},
    }
    return render(request, template, full_context)
