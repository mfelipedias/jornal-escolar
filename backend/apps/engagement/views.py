"""Endpoints das reações e das leituras (docs/20, docs/07).

Reações: POST /x/articles/<id>/react/ com kind.

Com HTMX devolve o fragmento da barra; sem JavaScript o formulário faz POST e volta para a
publicação. Limites (docs/23): 30 por minuto por IP e 10 por minuto por pessoa (usuário ou
código do cookie). Visitante sem o cookie emitido pela página da publicação não reage.

Leituras: POST /x/articles/<id>/read/, enviado pelo read-beacon.js com navigator.sendBeacon
depois do tempo mínimo com a aba visível e de rolar 25% do corpo. Responde 204 sem corpo,
tenha contado ou não; 429 passado o limite de 60 por minuto por IP. Exige CSRF como todo POST:
o token vai no corpo do beacon (csrfmiddlewaretoken), que não aceita cabeçalhos.
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
