"""Telas e endpoints do editor de publicações (docs/16, docs/07)."""

import json
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from apps.core.http import json_error
from apps.editorial import permissions

from . import services
from .models import Article
from .views import login_required_json


@login_required
@require_http_methods(["GET", "POST"])
def create(request: HttpRequest) -> HttpResponse:
    """/painel/publicacoes/nova/: GET mostra o convite; POST cria o rascunho e abre o editor."""
    if not permissions.can_create_article(request.user):
        raise PermissionDenied
    if request.method == "POST":
        article = services.create_article(request.user)
        return redirect("publications:edit", pk=article.pk)
    return render(request, "publications/create.html")


@login_required
def edit(request: HttpRequest, pk: int) -> HttpResponse:
    """/painel/publicacoes/<id>/editar/"""
    article = get_object_or_404(Article, pk=pk)
    if not permissions.can_edit(request.user, article):
        raise PermissionDenied
    editor_data = {
        "articleId": article.pk,
        "title": "" if article.title == "Sem título" else article.title,
        "subtitle": article.subtitle,
        "body": article.body_json or {"type": "doc", "content": []},
        "updatedAt": article.updated_at.isoformat(),
        "saveUrl": f"/x/articles/{article.pk}/body/",
        "status": article.status,
    }
    return render(
        request,
        "publications/editor.html",
        {"article": article, "editor_data": editor_data},
    )


def _payload(request: HttpRequest) -> dict[str, Any] | JsonResponse:
    if len(request.body) > settings.EDITOR_MAX_BODY_BYTES:
        return json_error("too_large", "O texto ficou grande demais para salvar.", 413)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)
    if not isinstance(payload, dict):
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)
    return payload


@require_http_methods(["PUT"])
@login_required_json
def save_body(request: HttpRequest, pk: int) -> JsonResponse:
    """PUT /x/articles/<id>/body/: autosave de título, linha fina e corpo (docs/16, "Autosave")."""
    article = get_object_or_404(Article, pk=pk)
    payload = _payload(request)
    if isinstance(payload, JsonResponse):
        return payload

    fields: dict[str, Any] = {}
    if "title" in payload:
        fields["title"] = " ".join(str(payload["title"] or "").split()) or "Sem título"
    if "subtitle" in payload:
        fields["subtitle"] = " ".join(str(payload["subtitle"] or "").split())[:220]
    if "body_json" in payload:
        fields["body_json"] = payload["body_json"]
    expected = (
        parse_datetime(str(payload.get("updated_at") or "")) if not payload.get("force") else None
    )

    try:
        saved = services.update_article(
            request.user, article, expected_updated_at=expected, **fields
        )
    except PermissionDenied:
        return json_error("forbidden", "Você não pode editar esta publicação.", 403)
    except services.ConflictError:
        return json_error(
            "conflict",
            "Este texto foi alterado por outra pessoa. Recarregue para ver as mudanças.",
            409,
        )
    except ValidationError as exc:
        return json_error("invalid", "Revise os campos.", 400, fields=exc.message_dict)

    return JsonResponse(
        {
            "saved_at": timezone.localtime(saved.updated_at).strftime("%H:%M"),
            "updated_at": saved.updated_at.isoformat(),
            "reading_minutes": saved.reading_minutes,
            "status": saved.status,
        }
    )
