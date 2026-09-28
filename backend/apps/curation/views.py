"""Tela de sugestões de pauta no painel (E48; docs/15 "Sugestões e Pautas", docs/21).

- GET /painel/sugestoes/: abas Para você, Salvas e Ignoradas; filtros por tópico, fonte e
  idioma (GET, funcionam sem JavaScript).
- POST /x/sugestoes/<id>/<acao>/: ignorar, salvar, interessante, restaurar. Com HTMX devolve o
  card atualizado; sem JavaScript volta para a tela com uma mensagem.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.templatetags.ui import PAGE_PARAM
from apps.editorial import permissions

from . import recommend, selectors
from .models import NewsRecommendation

PAGE_SIZE = 20


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _back(request: HttpRequest) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("curation:suggestions")


@never_cache
@require_GET
@login_required
def suggestions(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not permissions.can_view_suggestions(user):
        raise PermissionDenied
    current = request.GET.get("aba", "")
    if current not in selectors.TABS:
        current = selectors.DEFAULT_TAB
    filters = selectors.parse_filters(request.GET)
    counts = selectors.tab_counts(user, filters)
    page = Paginator(selectors.recommendations(user, current, filters), PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    query = filters.query()
    base = reverse("curation:suggestions")
    profile = getattr(user, "profile", None)
    context = {
        "tabs": [
            {
                "key": key,
                "label": label,
                "count": counts[key],
                "active": key == current,
                "url": f"{base}?aba={key}{'&' + query if query else ''}",
            }
            for key, (label, _) in selectors.TABS.items()
        ],
        "current": current,
        "filters": filters,
        "options": selectors.filter_options(user),
        "languages": selectors.LANGUAGES,
        "page_obj": page,
        "cards": selectors.cards(user, list(page.object_list)),
        "next_url": request.get_full_path(),
        "has_interests": bool(
            profile and (profile.topics.exists() or profile.disciplines.exists())
        ),
    }
    return render(request, "curation/suggestions.html", context)


@require_POST
@login_required
def suggestion_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    if action not in recommend.ACTIONS:
        raise Http404
    user = request.user
    if not permissions.can_view_suggestions(user):
        raise PermissionDenied
    rec = get_object_or_404(
        NewsRecommendation.objects.select_related("item__source"), pk=pk, user=user
    )
    try:
        done = recommend.act(user, rec, action)
        error = ""
    except ValueError as exc:
        done, error = "", str(exc)
    if not _is_htmx(request):
        if error:
            messages.error(request, error)
        else:
            messages.success(request, done)
        return redirect(_back(request))
    context = {
        "card": selectors.cards(user, [rec])[0],
        "done": done,
        "error": error,
        "next_url": _back(request),
    }
    return render(request, "curation/partials/suggestion_card.html", context)
