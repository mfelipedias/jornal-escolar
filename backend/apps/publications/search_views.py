"""Página de busca /busca/ (docs/12, docs/19; E36).

Três grupos: publicações (com trecho destacado), pessoas da equipe e disciplinas, áreas e
tópicos. Os filtros de /publicacoes/ (área, disciplina, tipo) valem sobre as publicações.
Sem nenhum resultado exato, tenta títulos parecidos (erro de digitação).
"""

from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET

from apps.core import seo
from apps.core.audit import client_ip
from apps.core.ratelimit import hit
from apps.taxonomy.models import KnowledgeArea

from . import listing, presentation, search, selectors


def _card_builder(query: str, *, fuzzy: bool):
    """Cards da página; na busca exata, com o trecho do corpo onde o termo aparece."""

    def build(articles: list) -> list[presentation.ArticleCard]:
        cards = []
        for article in articles:
            card = presentation.card(article)
            if not fuzzy:
                card.snippet = search.highlight(article.headline, article.body_text)
            cards.append(card)
        return cards

    return build


@require_GET
def results(request: HttpRequest) -> HttpResponse:
    query = search.clean_query(request.GET.get("q"))
    context: dict = {
        "query": query,
        "seo": seo.PageMeta(
            title=f"Busca: {query}" if query else "Buscar",
            path=reverse("search:results"),
            noindex=True,  # página de resultados não entra nos buscadores
        ),
    }
    if not query:
        context["areas"] = list(KnowledgeArea.objects.filter(is_active=True))
        return render(request, "search/results.html", context)

    ip = client_ip(request) or "sem-ip"
    if not hit(f"search:{ip}", limit=settings.SEARCHES_PER_MINUTE, period=60):
        context["rate_limited"] = True
        return render(request, "search/results.html", context, status=429)

    filters = listing.parse(request.GET, orders=listing.SEARCH_ORDERS)
    key = listing.cache_key(request, filters, f"q={query}")
    articles = listing.apply(selectors.search_published(query), filters)
    # Sem resultado exato, títulos parecidos (erro de digitação). Guardado junto com a lista.
    fuzzy = listing.cached(f"{key}|parecidos", lambda: not articles.exists())
    if fuzzy:
        articles = listing.apply(selectors.search_published_similar_titles(query), filters)
    else:
        articles = selectors.with_headlines(articles, query)
    page_obj, cards = listing.cached_page(
        key,
        articles,
        request.GET.get("pagina"),
        make_cards=_card_builder(query, fuzzy=fuzzy),
    )
    context.update(
        {
            "fuzzy": fuzzy,
            "filters": filters,
            "page_obj": page_obj,
            "cards": cards,
        }
    )
    if listing.is_load_more(request):
        response = render(request, "search/partials/more.html", context)
        patch_vary_headers(response, ["HX-Request"])
        return response

    people = selectors.search_people(query)
    taxonomy = selectors.search_taxonomy(query)
    has_results = bool(page_obj.paginator.count or people or taxonomy)
    context.update(
        {
            "people": [presentation.writer(user) for user in people],
            "taxonomy": taxonomy,
            **listing.filter_context(request, filters),
            "clear_url": "?" + urlencode({"q": query}),
            "areas": [] if has_results else list(KnowledgeArea.objects.filter(is_active=True)),
        }
    )
    response = render(request, "search/results.html", context)
    patch_vary_headers(response, ["HX-Request"])
    return response
