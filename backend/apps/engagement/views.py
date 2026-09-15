"""Endpoints das reações e das leituras (docs/20, docs/07).

Reações: POST /x/articles/<id>/react/ com kind.

Com HTMX devolve o fragmento da barra; sem JavaScript o formulário faz POST e volta para a
publicação. Limites (docs/23): 30 por minuto por IP e 10 por minuto por pessoa (usuário ou
código do cookie). Visitante sem o cookie emitido pela página da publicação não reage.

Leituras: POST /x/articles/<id>/read/, enviado pelo read-beacon.js com navigator.sendBeacon
depois do tempo mínimo com a aba visível e de rolar 25% do corpo. Responde 204 sem corpo,
tenha contado ou não; 429 passado o limite de 60 por minuto por IP. Exige CSRF como todo POST:
o token vai no corpo do beacon (csrfmiddlewaretoken), que não aceita cabeçalhos.

Comentários: POST /x/articles/<id>/comments/ (novo, pendente) e /x/comments/<id>/reply/
(resposta da equipe). Com HTMX devolvem o formulário ou o item; sem JavaScript voltam para a
publicação.
"""

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.audit import client_ip
from apps.core.ratelimit import hit
from apps.editorial import permissions
from apps.publications.models import Article

from . import presentation, services, visitor
from .forms import CommentForm, ReplyForm
from .models import Comment

RATE_LIMITED = "Muitas reações em pouco tempo. Espere um minuto e tente de novo."
NO_COOKIE = "Não deu para registrar a reação. Tente de novo (o navegador precisa aceitar cookies)."
INVALID = "Reação inválida."


def _respond(
    request: HttpRequest,
    article: Article,
    *,
    user,
    key,
    notice: str = "",
    status: int = 200,
) -> HttpResponse:
    if request.headers.get("HX-Request") == "true":
        current = services.current_kind(article, user=user, anon_key=key)
        bar = presentation.reaction_bar(article, current, notice=notice)
        response = render(
            request, "engagement/partials/reaction_bar.html", {"reaction_bar": bar}, status=status
        )
    elif status == 200:
        if notice:
            messages.warning(request, notice)
        response = redirect(f"{article.get_absolute_url()}#reacoes")
    else:
        response = render(
            request,
            "engagement/blocked.html",
            {"article": article, "notice": notice},
            status=status,
        )
    if user is None:
        visitor.ensure_cookie(request, response)
    return response


@never_cache
@require_POST
def react(request: HttpRequest, pk: int) -> HttpResponse:
    article = get_object_or_404(
        Article.objects.only("pk", "slug", "status", "reactions_count"), pk=pk
    )
    if article.status != Article.Status.PUBLISHED:
        raise Http404
    if not permissions.can_react(request.user, article):
        raise PermissionDenied
    user = request.user if request.user.is_authenticated else None
    key = None if user else visitor.anon_key(request)

    ip = client_ip(request) or "sem-ip"
    if not hit(f"react-ip:{ip}", limit=settings.REACTIONS_PER_MINUTE_PER_IP, period=60):
        return _respond(request, article, user=user, key=key, notice=RATE_LIMITED, status=429)
    if user is None and key is None:
        return _respond(request, article, user=user, key=key, notice=NO_COOKIE)
    who = f"u:{user.pk}" if user else f"a:{key}"
    if not hit(f"react-key:{who}", limit=settings.REACTIONS_PER_MINUTE_PER_KEY, period=60):
        return _respond(request, article, user=user, key=key, notice=RATE_LIMITED, status=429)

    try:
        services.toggle_reaction(article, request.POST.get("kind", ""), user=user, anon_key=key)
    except ValidationError:
        return _respond(request, article, user=user, key=key, notice=INVALID, status=400)
    return _respond(request, article, user=user, key=key)


@never_cache
@require_POST
def read(request: HttpRequest, pk: int) -> HttpResponse:
    article = get_object_or_404(Article.objects.only("pk", "status"), pk=pk)
    if article.status != Article.Status.PUBLISHED:
        raise Http404
    ip = client_ip(request) or "sem-ip"
    if not hit(f"read-ip:{ip}", limit=settings.READS_PER_MINUTE_PER_IP, period=60):
        return HttpResponse(status=429)
    user = request.user if request.user.is_authenticated else None
    key = None if user else visitor.anon_key(request)
    services.record_read(article, user=user, anon_key=key)
    return HttpResponse(status=204)


# --- comentários públicos (docs/20) ---

COMMENT_SENT = "Recebido! Seu comentário aparece depois que o autor aprovar."
COMMENT_RATE_LIMITED = (
    "Muitos comentários enviados desta rede na última hora. Tente de novo mais tarde."
)
COMMENT_PENDING_LIMIT = (
    "Você já tem comentários aguardando aprovação nesta publicação. Espere a moderação antes "
    "de enviar outro."
)
COMMENT_NO_COOKIE = (
    "Não deu para enviar o comentário. Tente de novo (o navegador precisa aceitar cookies)."
)


def _comment_response(
    request: HttpRequest,
    article: Article,
    form: CommentForm,
    *,
    notice: str = "",
    sent: bool = False,
    status: int = 200,
) -> HttpResponse:
    """Com HTMX, só o formulário; sem JavaScript, volta para a publicação ou mostra o erro."""
    if request.headers.get("HX-Request") == "true":
        response = render(
            request,
            "engagement/partials/comment_form.html",
            {"article_id": article.pk, "form": form, "notice": notice, "sent": sent},
            status=status,
        )
    elif sent or (status == 200 and notice):
        (messages.success if sent else messages.warning)(request, notice)
        response = redirect(f"{article.get_absolute_url()}#comentarios")
    else:
        response = render(
            request,
            "engagement/comment_page.html",
            {"article": article, "form": form, "notice": notice},
            status=status,
        )
    if not request.user.is_authenticated:
        visitor.ensure_cookie(request, response)
    return response


@never_cache
@require_POST
def comment(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/comments/: novo comentário, sempre pendente de aprovação.

    Honeypot preenchido responde como sucesso sem gravar (o robô não aprende a contornar).
    Limites: COMMENTS_PER_HOUR_PER_IP envios válidos por IP por hora (429) e
    COMMENTS_PENDING_PER_KEY pendentes por pessoa na publicação (429).
    """
    article = get_object_or_404(
        Article.objects.only("pk", "slug", "status", "comments_enabled"), pk=pk
    )
    if article.status != Article.Status.PUBLISHED:
        raise Http404
    if not permissions.can_comment(request.user, article):
        raise PermissionDenied
    form = CommentForm(request.POST)
    if not form.is_valid():
        return _comment_response(request, article, form, status=400)

    ip = client_ip(request)
    if not hit(
        f"comment-ip:{ip or 'sem-ip'}", limit=settings.COMMENTS_PER_HOUR_PER_IP, period=3600
    ):
        return _comment_response(request, article, form, notice=COMMENT_RATE_LIMITED, status=429)
    fresh = CommentForm(initial={"author_name": form.cleaned_data["author_name"]})
    if form.is_bot():
        return _comment_response(request, article, fresh, notice=COMMENT_SENT, sent=True)
    user = request.user if request.user.is_authenticated else None
    key = None if user else visitor.anon_key(request)
    if user is None and key is None:
        return _comment_response(request, article, form, notice=COMMENT_NO_COOKIE)

    try:
        services.submit_comment(
            article,
            author_name=form.cleaned_data["author_name"],
            body=form.cleaned_data["body"],
            anon_key=key,
            ip=ip,
            user=user,
        )
    except services.CommentLimitError:
        return _comment_response(request, article, form, notice=COMMENT_PENDING_LIMIT, status=429)
    except ValidationError as error:
        for field, messages_ in error.message_dict.items():
            form.add_error(field if field in form.fields else None, messages_)
        return _comment_response(request, article, form, status=400)
    return _comment_response(request, article, fresh, notice=COMMENT_SENT, sent=True)


@never_cache
@require_POST
def reply(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/comments/<id>/reply/: resposta da equipe (autores, coautores, editor, admin)."""
    item = get_object_or_404(Comment.objects.select_related("article"), pk=pk)
    article = item.article
    if not permissions.can_reply_comment(request.user, article):
        raise PermissionDenied
    form = ReplyForm(request.POST)
    status = 200
    if form.is_valid():
        try:
            services.reply_to_comment(request.user, item, form.cleaned_data["reply_body"])
        except ValidationError as error:
            form.add_error("reply_body", error.message_dict.get("reply_body", error.messages))
            status = 400
    else:
        status = 400
    if request.headers.get("HX-Request") != "true":
        if status == 200:
            return redirect(f"{article.get_absolute_url()}#comentario-{item.pk}")
        return render(
            request,
            "engagement/comment_page.html",
            {
                "article": article,
                "reply_form": form,
                "notice": " ".join(form.errors.get("reply_body", [])),
            },
            status=status,
        )
    context = {
        "comment": presentation.comment_item(item, article),
        "can_reply": True,
        "reply_form": form if status != 200 else None,
        "reply_open": status != 200,
    }
    return render(request, "engagement/partials/comment_item.html", context, status=status)
