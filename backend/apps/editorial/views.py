from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.publications import presentation, selectors, services
from apps.publications.models import Article

from . import notifications, permissions
from .models import Notification


@require_GET
@login_required
def notification_list(request):
    """/painel/notificacoes/: histórico completo (as mais recentes primeiro)."""
    items = Notification.objects.filter(user=request.user).select_related("actor")[:200]
    return render(request, "editorial/notifications.html", {"notifications": items})


@require_GET
@login_required
def notification_dropdown(request):
    """GET /x/notifications/: lista suspensa do sino."""
    return render(
        request,
        "editorial/partials/notification_list.html",
        {"notifications": notifications.recent(request.user)},
    )


@require_POST
@login_required
def notification_read_all(request):
    """POST /x/notifications/read-all/: devolve o sino zerado (HTMX) ou volta para a lista."""
    notifications.mark_all_read(request.user)
    if not request.headers.get("HX-Request"):
        return redirect("editorial:notifications")
    return render(
        request,
        "components/notification_bell.html",
        {"notification_unread": 0, "notifications": notifications.recent(request.user)},
    )


@require_GET
@login_required
def notification_open(request, pk: int):
    """/x/notifications/<id>/abrir/: marca como lida e leva ao objeto."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notifications.mark_read(notification)
    target = notification.url
    # Só endereços internos: nunca redirecionar para fora do site.
    if not target or urlsplit(target).netloc or not target.startswith("/"):
        target = "editorial:notifications"
    return redirect(target)


# --- destaques da home (docs/18, "Destaques da home") ---


def _require_feature(request: HttpRequest) -> None:
    if not permissions.can_feature(request.user):
        raise PermissionDenied


def _featured_context(request: HttpRequest, error: str = "") -> dict:
    query = " ".join((request.POST.get("q") or request.GET.get("q") or "").split())[:100]
    chosen = selectors.chosen_featured()
    chosen_ids = {a.pk for a in chosen}
    return {
        "chosen": [{"article": a, "card": presentation.card(a)} for a in chosen],
        # O bloco como a home mostra: marcados primeiro, completados pelas mais recentes.
        "preview": [
            {"card": presentation.card(a), "chosen": a.pk in chosen_ids}
            for a in selectors.featured_articles(services.MAX_FEATURED)
        ],
        "candidates": selectors.featured_candidates(query),
        "query": query,
        "is_full": len(chosen) >= services.MAX_FEATURED,
        "max_featured": services.MAX_FEATURED,
        "error": error,
    }


@never_cache
@require_GET
@login_required
def featured(request: HttpRequest) -> HttpResponse:
    """/painel/destaques/: ordem dos destaques da home, com busca e prévia."""
    _require_feature(request)
    return render(request, "editorial/featured.html", _featured_context(request))


@require_GET
@login_required
def featured_search(request: HttpRequest) -> HttpResponse:
    """GET /x/featured/search/?q=: publicadas com capa para adicionar (HTMX)."""
    _require_feature(request)
    context = _featured_context(request)
    return render(request, "editorial/partials/featured_candidates.html", context)


@require_POST
@login_required
def feature(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/feature/ com acao = adicionar | remover | subir | descer.

    Com HTMX devolve o quadro inteiro (lista, prévia e busca); sem HTMX volta para a tela.
    """
    _require_feature(request)
    article = get_object_or_404(Article, pk=pk)
    action = request.POST.get("acao", "")
    error = ""
    try:
        if action == "adicionar":
            services.feature(request.user, article)
        elif action == "remover":
            services.unfeature(request.user, article)
        elif action in ("subir", "descer"):
            services.move_featured(request.user, article, -1 if action == "subir" else 1)
        else:
            error = "Ação inválida."
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if request.headers.get("HX-Request") != "true":
        return redirect("editorial:featured")
    return render(
        request, "editorial/partials/featured_board.html", _featured_context(request, error)
    )
