from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.templatetags.ui import PAGE_PARAM
from apps.publications import presentation, selectors, services
from apps.publications.models import Article

from . import notifications, permissions
from . import selectors as editorial_selectors
from . import services as comment_services
from .models import EditorialComment, Notification


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


# --- revisão por colega (docs/15 "Revisões", docs/17) ---

QUEUE_PAGE_SIZE = 20


@never_cache
@require_GET
@login_required
def review_queue(request: HttpRequest) -> HttpResponse:
    """/painel/revisao/: abas "Pedidas a mim", "Que eu pedi" e, para editores, "Todas"."""
    user = request.user
    tabs = editorial_selectors.queue_tabs(user)
    current = request.GET.get("aba", "")
    if current not in tabs:
        current = editorial_selectors.DEFAULT_TAB
    page = Paginator(editorial_selectors.review_queue(user, current), QUEUE_PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    context = {
        "tabs": [
            {
                "key": key,
                "label": editorial_selectors.QUEUE_TABS[key],
                "count": editorial_selectors.review_queue(user, key).count(),
                "active": key == current,
            }
            for key in tabs
        ],
        "current": current,
        "page_obj": page,
        "items": [
            {
                "article": article,
                "authors": presentation.byline(article),
                "review": editorial_selectors.review_summary(article),
            }
            for article in page.object_list
        ],
    }
    return render(request, "editorial/review_queue.html", context)


@never_cache
@require_GET
@login_required
def review(request: HttpRequest, pk: int) -> HttpResponse:
    """/painel/publicacoes/<id>/revisar/: ler como ficará publicado, decidir e ver o histórico.

    Revisor designado, editores e admin decidem; autores veem a mesma tela sem os botões de
    decisão. As decisões são enviadas para publications:transition com next= desta tela.
    """
    article = get_object_or_404(
        Article.objects.select_related("type", "cover").prefetch_related("contributors"), pk=pk
    )
    user = request.user
    if not permissions.can_comment_on_review(user, article):
        raise PermissionDenied
    checklist = services.checklist(article)
    context = {
        "article": article,
        "review": editorial_selectors.review_summary(article),
        "authors": presentation.byline(article),
        "checklist": checklist,
        "blocking": [item for item in checklist if item.blocking],
        "history": editorial_selectors.history_entries(article),
        # "Ver versões" (ArticleRevision) é de editor+ (docs/17, "Histórico da publicação").
        "revisions": (
            article.revisions.select_related("created_by")[:20]
            if permissions.is_editor(user)
            else None
        ),
        "archive_requires_note": permissions.archive_requires_note(user, article),
        **_comments_context(article),
    }
    return render(request, "editorial/review.html", context)


# --- comentários editoriais (docs/17, "Comentários editoriais") ---

COMMENTS_PARTIAL = "editorial/partials/review_comments.html"
ANCHOR_FIELDS = ("anchor_text", "anchor_prefix", "anchor_suffix", "anchor_from")


def _comments_context(article: Article, *, error: str = "", draft: dict | None = None) -> dict:
    return {
        "article": article,
        "board": editorial_selectors.comment_board(article),
        "comment_error": error,
        "draft": draft or {},
    }


def _comments_response(
    request: HttpRequest,
    article: Article,
    *,
    error: str = "",
    draft: dict | None = None,
    anchor: str = "",
) -> HttpResponse:
    """HTMX: devolve o painel de comentários. Sem JavaScript: volta para a tela de revisão."""
    if request.headers.get("HX-Request") == "true":
        context = _comments_context(article, error=error, draft=draft)
        return render(request, COMMENTS_PARTIAL, context)
    if error:
        messages.error(request, error)
    url = reverse("editorial:review", args=[article.pk])
    return redirect(f"{url}#{anchor}" if anchor else url)


def _error_text(exc: ValidationError) -> str:
    return " ".join(exc.messages)


@require_POST
@login_required
def comment_create(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/review-comments/: comentário geral ou ancorado no trecho."""
    article = get_object_or_404(Article, pk=pk)
    if not permissions.can_comment_on_review(request.user, article):
        raise PermissionDenied
    data = {name: request.POST.get(name, "") for name in ("body", *ANCHOR_FIELDS)}
    try:
        comment = comment_services.add_comment(
            request.user,
            article,
            data["body"],
            anchor_text=data["anchor_text"],
            anchor_prefix=data["anchor_prefix"],
            anchor_suffix=data["anchor_suffix"],
            anchor_from=data["anchor_from"],
        )
    except ValidationError as exc:
        return _comments_response(request, article, error=_error_text(exc), draft=data)
    return _comments_response(request, article, anchor=f"comentario-{comment.pk}")


@require_POST
@login_required
def comment_reply(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/review-comments/<id>/reply/: resposta (um nível)."""
    parent = get_object_or_404(EditorialComment.objects.select_related("article"), pk=pk)
    article = parent.article
    if not permissions.can_comment_on_review(request.user, article):
        raise PermissionDenied
    body = request.POST.get("body", "")
    try:
        comment_services.reply(request.user, parent, body)
    except ValidationError as exc:
        draft = {"reply_to": parent.pk, "reply_body": body}
        return _comments_response(request, article, error=_error_text(exc), draft=draft)
    return _comments_response(request, article, anchor=f"comentario-{parent.pk}")


@require_POST
@login_required
def comment_status(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    """POST /x/review-comments/<id>/resolve/ ou /reopen/."""
    comment = get_object_or_404(EditorialComment.objects.select_related("article"), pk=pk)
    article = comment.article
    if not permissions.can_resolve_comment(request.user, article):
        raise PermissionDenied
    change = {"resolve": comment_services.resolve, "reopen": comment_services.reopen}.get(action)
    if change is None:
        return HttpResponse(status=404)
    try:
        change(request.user, comment)
    except ValidationError as exc:
        return _comments_response(request, article, error=_error_text(exc))
    return _comments_response(request, article, anchor=f"comentario-{comment.pk}")
