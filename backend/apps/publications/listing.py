"""Listas de publicações com filtros por GET (docs/12, docs/19; E21 e E37).

Usado por /publicacoes/, pelas páginas de área, disciplina, tipo e tópico (que chegam com um
filtro fixo) e pela busca. Parâmetros da URL: area (um), disciplina e tipo (vários), professor
(endereço do perfil), periodo (30-dias, semestre, ano) ou de/ate (AAAA-MM-DD), ordem e
pagina. Sem JavaScript o formulário faz GET na própria página; com HTMX só a região da lista
é trocada e a URL vai para o histórico, então a URL sempre reproduz o filtro.

Contagem e cards de cada página ficam 60 segundos em cache por combinação de filtros, com a
versão do conteúdo público na chave (cache.py): publicar ou arquivar invalida tudo.
"""

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.core.cache import cache
from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.formats import date_format

from apps.accounts import selectors as account_selectors
from apps.accounts.models import TeacherProfile
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea, Topic

from . import presentation, selectors
from .cache import public_version
from .models import Article

PER_PAGE = 12
CACHE_SECONDS = 60

# Região trocada pelo HTMX quando um filtro muda (templates: id="listing-region").
REGION_ID = "listing-region"

# Ordens (docs/19). "lidas" usa Article.reads_count (E39); empate vai para a mais recente.
ORDER_RECENT = "recentes"
ORDER_RELEVANCE = "relevancia"
ORDER_MOST_READ = "lidas"
LIST_ORDERS: dict[str, str] = {ORDER_RECENT: "Mais recentes", ORDER_MOST_READ: "Mais lidas"}
SEARCH_ORDERS: dict[str, str] = {
    ORDER_RELEVANCE: "Mais relevantes",
    ORDER_RECENT: "Mais recentes",
    ORDER_MOST_READ: "Mais lidas",
}

# Períodos predefinidos: relativos a hoje, para a URL compartilhada continuar "atual".
PERIODS: dict[str, str] = {
    "30-dias": "Últimos 30 dias",
    "semestre": "Este semestre",
    "ano": "Este ano",
}


@dataclass
class Chip:
    label: str
    remove_url: str = ""  # vazio: filtro fixo da página, não removível


@dataclass
class ListingFilters:
    area: KnowledgeArea | None = None
    disciplines: list[Discipline] = field(default_factory=list)
    types: list[ArticleType] = field(default_factory=list)
    professor: TeacherProfile | None = None
    period: str = ""  # chave de PERIODS; vazio quando não há ou quando vale o intervalo
    date_from: date | None = None
    date_to: date | None = None
    order: str = ORDER_RECENT
    orders: dict[str, str] = field(default_factory=lambda: LIST_ORDERS)
    fixed_area: KnowledgeArea | None = None
    fixed_discipline: Discipline | None = None
    fixed_type: ArticleType | None = None
    fixed_topic: Topic | None = None

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
        """Algo que reduz a lista (a ordem não conta: não esconde nada)."""
        return bool(
            self.area
            or self.disciplines
            or self.types
            or self.professor
            or self.date_from
            or self.date_to
        )

    @property
    def default_order(self) -> str:
        return next(iter(self.orders))

    @property
    def is_default_order(self) -> bool:
        return self.order == self.default_order

    @property
    def has_choices(self) -> bool:
        """Filtro ou ordem diferente do padrão: mostra "Limpar filtros"."""
        return self.has_user_filters or not self.is_default_order

    def cache_token(self) -> str:
        """Combinação de filtros normalizada: mesma lista, mesma chave, qualquer que seja a
        ordem ou a repetição dos parâmetros na URL."""

        def slugs(items: Iterable) -> str:
            return ",".join(sorted({item.slug for item in items}))

        parts = [
            f"area={self.effective_area.slug if self.effective_area else ''}",
            f"disciplina={slugs(self.effective_disciplines)}",
            f"tipo={slugs(self.effective_types)}",
            f"topico={self.fixed_topic.slug if self.fixed_topic else ''}",
            f"professor={self.professor.slug if self.professor else ''}",
            f"de={self.date_from or ''}",
            f"ate={self.date_to or ''}",
            f"ordem={self.order}",
        ]
        return "&".join(parts)


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


def period_range(period: str, today: date | None = None) -> tuple[date | None, date | None]:
    """Datas de um período predefinido. Semestre: janeiro a junho ou julho a dezembro."""
    today = today or timezone.localdate()
    if period == "30-dias":
        return today - timedelta(days=30), None
    if period == "semestre":
        return date(today.year, 1 if today.month <= 6 else 7, 1), None
    if period == "ano":
        return date(today.year, 1, 1), None
    return None, None


def parse(
    query: QueryDict,
    *,
    fixed_area: KnowledgeArea | None = None,
    fixed_discipline: Discipline | None = None,
    fixed_type: ArticleType | None = None,
    fixed_topic: Topic | None = None,
    orders: dict[str, str] | None = None,
) -> ListingFilters:
    """Lê a URL ignorando valores desconhecidos e o que a página já fixa."""
    filters = ListingFilters(
        fixed_area=fixed_area,
        fixed_discipline=fixed_discipline,
        fixed_type=fixed_type,
        fixed_topic=fixed_topic,
        orders=orders or LIST_ORDERS,
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
    if query.get("professor"):
        filters.professor = (
            TeacherProfile.objects.filter(
                slug=query["professor"], is_public=True, user__is_active=True
            )
            .select_related("user")
            .first()
        )
    # Intervalo escrito à mão vale no lugar do período predefinido.
    filters.date_from = _parse_date(query.get("de"))
    filters.date_to = _parse_date(query.get("ate"))
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        filters.date_from, filters.date_to = filters.date_to, filters.date_from
    if not (filters.date_from or filters.date_to) and query.get("periodo") in PERIODS:
        filters.period = query["periodo"]
        filters.date_from, filters.date_to = period_range(filters.period)
    order = query.get("ordem")
    filters.order = order if order in filters.orders else filters.default_order
    return filters


def apply(queryset: QuerySet[Article], filters: ListingFilters) -> QuerySet[Article]:
    """Filtra e ordena. A ordem por relevância mantém a da consulta de busca."""
    if filters.order == ORDER_RECENT:
        queryset = queryset.order_by("-published_at", "-pk")
    elif filters.order == ORDER_MOST_READ:
        queryset = queryset.order_by("-reads_count", "-published_at", "-pk")
    if filters.date_from:
        queryset = queryset.filter(published_at__date__gte=filters.date_from)
    if filters.date_to:
        queryset = queryset.filter(published_at__date__lte=filters.date_to)
    if filters.professor:
        credited = account_selectors.profile_articles(filters.professor, account_selectors.TAB_ALL)
        queryset = queryset.filter(pk__in=credited.values("pk"))
    conditions = Q()
    if area := filters.effective_area:
        conditions &= Q(disciplines__area=area)
    if disciplines := filters.effective_disciplines:
        conditions &= Q(disciplines__in=disciplines)
    if types := filters.effective_types:
        conditions &= Q(type__in=types)
    if filters.fixed_topic:
        conditions &= Q(topics=filters.fixed_topic)
    if not conditions:
        return queryset
    matching = Article.objects.filter(conditions).values("pk")
    return queryset.filter(pk__in=matching)  # subconsulta: sem linhas repetidas pelo M2M


def _without(query: QueryDict, *keys: str, value: str | None = None) -> str:
    copy = query.copy()
    copy.pop("pagina", None)
    for key in keys:
        if value is None:
            copy.pop(key, None)
            if key == "area":  # disciplinas dependem da área escolhida
                copy.pop("disciplina", None)
        else:
            copy.setlist(key, [v for v in copy.getlist(key) if v != value])
    encoded = copy.urlencode()
    return f"?{encoded}" if encoded else "?"


def _short_date(value: date) -> str:
    return date_format(value, "d/m/Y")


def _period_label(filters: ListingFilters) -> str:
    if filters.period:
        return PERIODS[filters.period]
    if filters.date_from and filters.date_to:
        return f"De {_short_date(filters.date_from)} a {_short_date(filters.date_to)}"
    if filters.date_from:
        return f"Desde {_short_date(filters.date_from)}"
    if filters.date_to:
        return f"Até {_short_date(filters.date_to)}"
    return ""


def chips(filters: ListingFilters, query: QueryDict) -> list[Chip]:
    result: list[Chip] = []
    if filters.fixed_area:
        result.append(Chip(f"Área: {filters.fixed_area.name}"))
    if filters.fixed_discipline:
        result.append(Chip(f"Disciplina: {filters.fixed_discipline.name}"))
    if filters.fixed_type:
        result.append(Chip(f"Tipo: {filters.fixed_type.name}"))
    if filters.fixed_topic:
        result.append(Chip(f"Tópico: {filters.fixed_topic.name}"))
    if filters.area:
        result.append(Chip(f"Área: {filters.area.name}", _without(query, "area")))
    for discipline in filters.disciplines:
        result.append(Chip(discipline.name, _without(query, "disciplina", value=discipline.slug)))
    for article_type in filters.types:
        result.append(Chip(article_type.name, _without(query, "tipo", value=article_type.slug)))
    if filters.professor:
        name = filters.professor.user.public_name
        result.append(Chip(f"Por: {name}", _without(query, "professor")))
    if label := _period_label(filters):
        result.append(Chip(label, _without(query, "periodo", "de", "ate")))
    if not filters.is_default_order:
        result.append(Chip(filters.orders[filters.order], _without(query, "ordem")))
    return result


@dataclass
class FilterOptions:
    """O que o formulário oferece: só o que a página não fixou."""

    areas: list[KnowledgeArea]
    disciplines: list[Discipline]
    types: list[ArticleType]
    professors: list[TeacherProfile] = field(default_factory=list)
    periods: dict[str, str] = field(default_factory=lambda: PERIODS)
    orders: dict[str, str] = field(default_factory=dict)  # vazio: só uma ordem possível


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
    return FilterOptions(
        areas=areas,
        disciplines=disciplines,
        types=types,
        professors=account_selectors.credited_profiles(),
        orders=filters.orders if len(filters.orders) > 1 else {},
    )


def cached(key: str, build: Callable):
    """Valor da lista em cache por 60s, com a versão do conteúdo público na chave."""
    digest = hashlib.sha256(key.encode()).hexdigest()[:40]
    return cache.get_or_set(f"listing:v{public_version()}:{digest}", build, CACHE_SECONDS)


def cache_key(request: HttpRequest, filters: ListingFilters, *extra: object) -> str:
    """Página + filtros normalizados (+ o que mais mudar o resultado, como o termo da busca)."""
    return "|".join([request.path, filters.cache_token(), *map(str, extra)])


def cached_page(
    key: str,
    queryset: QuerySet[Article],
    number: str | int | None,
    make_cards: Callable[[list[Article]], list] | None = None,
) -> tuple[Page, list]:
    """Página da lista com contagem e cards em cache (60s), sem consultar de novo.

    O Paginator trabalha sobre range(total): o cache guarda só o total e os cards montados.
    """
    total = cached(f"{key}|total", queryset.count)
    page_obj = Paginator(range(total), PER_PAGE).get_page(number)
    if not total:
        return page_obj, []
    make_cards = make_cards or (lambda articles: [presentation.card(a) for a in articles])

    def build() -> list:
        start = page_obj.start_index() - 1
        return make_cards(list(selectors.for_cards(queryset)[start : page_obj.end_index()]))

    return page_obj, cached(f"{key}|pagina={page_obj.number}", build)


def is_load_more(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true" and "pagina" in request.GET


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
    key = cache_key(request, filters, f"sem={sorted(exclude_ids or [])}")
    page_obj, cards = cached_page(key, queryset, request.GET.get("pagina"))
    full_context = {
        "filters": filters,
        "page_obj": page_obj,
        "cards": cards,
        **(context or {}),
    }
    if is_load_more(request):
        response = render(request, "publications/partials/list_more.html", full_context)
    else:
        full_context.update(filter_context(request, filters))
        full_context["count_oob"] = True  # contagem fica no cabeçalho, fora da região
        response = render(request, template, full_context)
    # Mesma URL devolve página inteira ou só os cards: o cache do navegador separa os dois.
    patch_vary_headers(response, ["HX-Request"])
    return response


def filter_context(request: HttpRequest, filters: ListingFilters) -> dict:
    """Chips, opções e valores marcados da barra de filtros."""
    return {
        "chips": chips(filters, request.GET),
        "options": options(filters),
        "selected": selected(filters),
        "region_id": REGION_ID,
    }


def selected(filters: ListingFilters) -> dict:
    """O que vem marcado no formulário de filtros."""
    custom_dates = not filters.period
    return {
        "area": filters.area.slug if filters.area else "",
        "disciplinas": {d.slug for d in filters.disciplines},
        "tipos": {t.slug for t in filters.types},
        "professor": filters.professor.slug if filters.professor else "",
        "periodo": filters.period,
        "de": filters.date_from.isoformat() if custom_dates and filters.date_from else "",
        "ate": filters.date_to.isoformat() if custom_dates and filters.date_to else "",
        "ordem": filters.order,
    }
