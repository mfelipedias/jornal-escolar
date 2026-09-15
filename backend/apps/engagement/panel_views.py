"""Moderação dos comentários públicos no painel (docs/20 "Moderação no painel", docs/15; E41).

- GET /painel/comentarios/: fila com as abas Pendentes, Aprovados e Rejeitados; ?publicacao=<id>
  filtra uma publicação. Editor e admin veem todas; o restante da equipe, só as que assina.
- POST /x/comments/<id>/<acao>/: approve, reject, rename, reply-approve. Com HTMX devolve o
  item atualizado; sem JavaScript volta para a fila com uma mensagem.
- POST /x/comments/bulk/: aprovar ou rejeitar os marcados.
- POST /x/articles/<id>/comments-toggle/: abre ou fecha os comentários da publicação.

Toda moderação grava AuditLog (comment_moderated) só com ids e códigos, sem nome nem texto.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core import audit
from apps.core.templatetags.ui import PAGE_PARAM
from apps.editorial import permissions
from apps.publications.models import Article

from . import presentation, selectors, services
from .models import Comment

PAGE_SIZE = 20
BULK_LIMIT = 100

# /x/comments/<id>/<acao>/ → mensagem de sucesso.
ACTIONS = {
    "approve": "Comentário aprovado.",
    "reject": "Comentário rejeitado.",
    "rename": "Nome atualizado.",
    "reply-approve": "Resposta salva e comentário aprovado.",
}
BULK_ACTIONS = {
    "aprovar": (Comment.Status.APPROVED, "aprovado", "aprovados"),
    "rejeitar": (Comment.Status.REJECTED, "rejeitado", "rejeitados"),
}


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _back(request: HttpRequest) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("engagement:moderation")


def _article_filter(request: HttpRequest) -> int | None:
    value = request.GET.get("publicacao", "")
    return int(value) if value.isdigit() else None


@never_cache
@require_GET
@login_required
def moderation(request: HttpRequest) -> HttpResponse:
    user = request.user
    current = request.GET.get("aba", "")
    if current not in selectors.TABS:
        current = selectors.DEFAULT_TAB
    article_id = _article_filter(request)
    article = None
    if article_id is not None:
        article = selectors.moderated_articles(user).filter(pk=article_id).first()
        if article is None:
            article_id = None
    counts = selectors.tab_counts(user, article_id)
    page = Paginator(selectors.moderation_queue(user, current, article_id), PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    comments = list(page.object_list)
    query = f"&publicacao={article.pk}" if article else ""
    context = {
        "tabs": [
            {
                "key": key,
                "label": label,
                "count": counts[key],
                "active": key == current,
                "url": f"{reverse('engagement:moderation')}?aba={key}{query}",
            }
            for key, (label, _) in selectors.TABS.items()
        ],
        "current": current,
        "filter_article": article,
        "sees_all": selectors.sees_all(user),
        "page_obj": page,
        "items": presentation.moderation_items(comments),
        "next_url": request.get_full_path(),
    }
    return render(request, "engagement/moderation.html", context)


def _item_response(
    request: HttpRequest,
    comment: Comment,
    *,
    done: str = "",
    errors: dict | None = None,
    data: dict | None = None,
    status: int = 200,
) -> HttpResponse:
    comment.refresh_from_db()
    item = presentation.moderation_items([comment])[0]
    context = {
        "item": item,
        "done": done,
        "errors": errors or {},
        "data": data or {},
        "next_url": _back(request),
    }
    return render(request, "engagement/partials/moderation_item.html", context, status=status)


@require_POST
@login_required
def moderate(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    if action not in ACTIONS:
        raise Http404
    comment = get_object_or_404(Comment.objects.select_related("article"), pk=pk)
    user = request.user
    if not permissions.can_moderate_comments(user, comment.article):
        raise PermissionDenied
    changes: dict = {}
    try:
        if action == "approve":
            services.moderate_comment(user, comment, Comment.Status.APPROVED)
            changes = {"status": Comment.Status.APPROVED}
        elif action == "reject":
            services.moderate_comment(user, comment, Comment.Status.REJECTED)
            changes = {"status": Comment.Status.REJECTED}
        elif action == "rename":
            services.rename_comment(user, comment, request.POST.get("author_name", ""))
            changes = {"author_name": "editado"}
        else:
            services.reply_and_approve(user, comment, request.POST.get("reply_body", ""))
            changes = {"status": Comment.Status.APPROVED, "reply": True}
    except ValidationError as error:
        errors = error.message_dict if hasattr(error, "error_dict") else {"": error.messages}
        if _is_htmx(request):
            return _item_response(
                request, comment, errors=errors, data=request.POST.dict(), status=400
            )
        messages.error(request, " ".join(m for msgs in errors.values() for m in msgs))
        return redirect(_back(request))

    audit.record(
        audit.Action.COMMENT_MODERATED,
        actor=user,
        target=comment,
        changes={"action": action, "article": comment.article_id, **changes},
        request=request,
    )
    if _is_htmx(request):
        return _item_response(request, comment, done=ACTIONS[action])
    messages.success(request, ACTIONS[action])
    return redirect(_back(request))


@require_POST
@login_required
def bulk(request: HttpRequest) -> HttpResponse:
    """Aprovar ou rejeitar em lote. Sempre volta para a fila (a lista muda inteira)."""
    back = _back(request)
    action = request.POST.get("acao", "")
    ids = list(dict.fromkeys(int(v) for v in request.POST.getlist("ids") if v.isdigit()))
    if action not in BULK_ACTIONS:
        messages.error(request, "Escolha aprovar ou rejeitar.")
        return redirect(back)
    if not ids:
        messages.error(request, "Marque ao menos um comentário.")
        return redirect(back)
    if len(ids) > BULK_LIMIT:
        messages.error(request, f"Marque no máximo {BULK_LIMIT} comentários por vez.")
        return redirect(back)
    if not permissions.is_staff_member(request.user):
        raise PermissionDenied
    status, one, many = BULK_ACTIONS[action]
    changed = services.moderate_many(request.user, ids, status)
    if changed:
        audit.record(
            audit.Action.COMMENT_MODERATED,
            actor=request.user,
            changes={"action": f"bulk-{action}", "status": status, "comments": changed},
            request=request,
        )
        total = len(changed)
        label = f"comentário {one}" if total == 1 else f"comentários {many}"
        messages.success(request, f"{total} {label}.")
    else:
        messages.info(request, "Nenhum comentário mudou de situação.")
    return redirect(back)


@require_POST
@login_required
def comments_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Abre ou fecha os comentários (campo enabled=1/0; sem o campo, inverte)."""
    article = get_object_or_404(Article, pk=pk)
    if not permissions.can_toggle_comments(request.user, article):
        raise PermissionDenied
    value = request.POST.get("enabled")
    enabled = (value == "1") if value in ("0", "1") else not article.comments_enabled
    services.set_comments_enabled(request.user, article, enabled)
    if enabled:
        messages.success(request, f"Comentários abertos em “{article.title}”.")
    else:
        messages.success(
            request,
            f"Comentários fechados em “{article.title}”. Os aprovados continuam na página.",
        )
    return redirect(_back(request))
