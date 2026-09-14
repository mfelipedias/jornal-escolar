from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.publications import home as home_blocks

from . import seo, services
from .models import StaticPage
from .site_settings import get_setting


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Página inicial (docs/10). Com HTMX e ?pagina=N devolve só mais "Últimas publicações"."""
    blocks = home_blocks.blocks()
    meta = seo.PageMeta(
        title=get_setting("site.name"),
        description=seo.home_description(),
        path=reverse("core:home"),
        json_ld=[seo.website()],
    )
    if not blocks.has_content:
        return render(request, "core/home.html", {"blocks": blocks, "seo": meta})
    page_obj, latest = home_blocks.latest_page(blocks.featured_ids, request.GET.get("pagina"))
    context = {"blocks": blocks, "page_obj": page_obj, "latest": latest, "seo": meta}
    if request.headers.get("HX-Request") == "true" and "pagina" in request.GET:
        return render(request, "core/partials/home_latest_more.html", context)
    return render(request, "core/home.html", context)


@require_GET
def page(request: HttpRequest, slug: str) -> HttpResponse:
    """Páginas institucionais: /sobre/, /privacidade/, /colaborar/ (docs/12)."""
    static_page = get_object_or_404(StaticPage, slug=slug, is_published=True)
    meta = seo.PageMeta(
        title=static_page.title,
        description=static_page.lead,
        path=static_page.get_absolute_url(),
    )
    return render(request, "core/page.html", {"page": static_page, "seo": meta})


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    return HttpResponse(seo.robots_txt(), content_type="text/plain; charset=utf-8")


@never_cache
@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    """Verificação de saúde para o Compose e o monitor externo (docs/24).

    Responde 200 com status "ok" ou 503 com status "error" e o que falhou.
    """
    database_ok = services.check_database()
    checks = {
        "database": database_ok,
        "migrations": database_ok and services.check_migrations(),
    }
    if all(checks.values()):
        return JsonResponse({"status": "ok", "version": settings.APP_VERSION})
    return JsonResponse(
        {"status": "error", "version": settings.APP_VERSION, "checks": checks},
        status=503,
    )
