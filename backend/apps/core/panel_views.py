"""Páginas institucionais no painel (docs/18, "Páginas estáticas"): lista, editor e publicar."""

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.editorial import permissions
from apps.publications.views import login_required_json

from . import services
from .http import json_error
from .models import StaticPage


def _require_editor(request: HttpRequest) -> None:
    if not permissions.can_edit_pages(request.user):
        raise PermissionDenied


@never_cache
@require_GET
@login_required
def page_list(request: HttpRequest) -> HttpResponse:
    """/painel/paginas/: as três páginas, com estado e ações."""
    _require_editor(request)
    services.seed_site()  # cria só as páginas que faltam (textos iniciais)
    pages = sorted(
        StaticPage.objects.select_related("updated_by"),
        key=lambda p: StaticPage.Slug.values.index(p.slug),
    )
    return render(request, "core/page_list.html", {"pages": pages})


@never_cache
@require_GET
@login_required
def page_edit(request: HttpRequest, slug: str) -> HttpResponse:
    """/painel/paginas/<slug>/editar/: mesmo editor das publicações, sem imagens."""
    _require_editor(request)
    services.seed_site()
    page = get_object_or_404(StaticPage, slug=slug)
    editor_data = {
        "storageKey": f"page:{page.slug}",
        "title": page.title,
        "subtitle": page.lead,
        "body": page.body_json or {"type": "doc", "content": []},
        "updatedAt": page.updated_at.isoformat(),
        "saveUrl": reverse("core:page_save_body", args=[page.slug]),
        "mediaUrl": None,
        "bodyLabel": "Texto da página",
    }
    return render(request, "core/page_editor.html", {"page": page, "editor_data": editor_data})


@require_http_methods(["PUT"])
@login_required_json
def page_save_body(request: HttpRequest, slug: str) -> JsonResponse:
    """PUT /x/pages/<slug>/body/: autosave no mesmo formato do editor de publicações."""
    page = get_object_or_404(StaticPage, slug=slug)
    if len(request.body) > settings.EDITOR_MAX_BODY_BYTES:
        return json_error("too_large", "O texto ficou grande demais para salvar.", 413)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)

    fields = {}
    if "title" in payload:
        fields["title"] = payload["title"]
    if "subtitle" in payload:
        fields["lead"] = payload["subtitle"]
    if "body_json" in payload:
        fields["body_json"] = payload["body_json"]
    expected = parse_datetime(str(payload.get("updated_at") or ""))
    try:
        saved = services.update_page(request.user, page, expected_updated_at=expected, **fields)
    except PermissionDenied:
        return json_error("forbidden", "Você não pode editar esta página.", 403)
    except services.PageConflictError:
        return json_error(
            "conflict",
            "Esta página foi alterada por outra pessoa. Recarregue para ver as mudanças.",
            409,
        )
    except ValidationError as exc:
        return json_error("invalid", "Revise os campos.", 400, fields=exc.message_dict)
    return JsonResponse(
        {
            "saved_at": timezone.localtime(saved.updated_at).strftime("%H:%M"),
            "updated_at": saved.updated_at.isoformat(),
        }
    )


@require_POST
@login_required
def page_publish(request: HttpRequest, slug: str) -> HttpResponse:
    """POST /painel/paginas/<slug>/publicar/ com publicada = 1 (pôr no ar) ou 0 (tirar)."""
    _require_editor(request)
    page = get_object_or_404(StaticPage, slug=slug)
    published = request.POST.get("publicada") == "1"
    services.set_page_published(request.user, page, published)
    if published:
        messages.success(request, f"“{page.title}” está no ar.")
    else:
        messages.info(request, f"“{page.title}” saiu do ar. O texto continua guardado.")
    return redirect("core:page_list")
