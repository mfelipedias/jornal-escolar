import json
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.http import json_error
from apps.core.ratelimit import hit
from apps.editorial import permissions

from . import media
from .forms import MediaAssetMetadataForm
from .models import MediaAsset


def login_required_json(view):
    """Endpoints internos respondem 401 em JSON em vez de redirecionar para o login."""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return json_error("not_authenticated", "Entre no sistema para continuar.", 401)
        return view(request, *args, **kwargs)

    return wrapper


@require_POST
@login_required_json
def media_upload(request: HttpRequest) -> JsonResponse:
    """POST /x/media/ (multipart, campo "file")."""
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return json_error("missing_file", "Nenhum arquivo enviado.", 400)
    if not permissions.can_upload_media(request.user):
        return json_error("forbidden", "Sua conta não pode enviar imagens.", 403)
    if not hit(
        f"media-upload:{request.user.pk}", limit=settings.MEDIA_UPLOADS_PER_HOUR, period=3600
    ):
        return json_error("rate_limited", "Muitos envios em pouco tempo. Tente mais tarde.", 429)
    try:
        asset = media.process_upload(uploaded, request.user)
    except media.MediaError as exc:
        return json_error(exc.code, exc.message, exc.status)
    return JsonResponse(media.serialize(asset), status=201)


@require_http_methods(["GET", "PATCH"])
@login_required_json
def media_detail(request: HttpRequest, pk: int) -> JsonResponse:
    """GET/PATCH /x/media/<id>/: dados e metadados (texto alternativo, crédito, consentimento)."""
    asset = get_object_or_404(MediaAsset, pk=pk)
    if not permissions.can_edit_media(request.user, asset):
        return json_error("forbidden", "Você não pode alterar esta imagem.", 403)
    if request.method == "GET":
        return JsonResponse(media.serialize(asset))

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)
    if not isinstance(payload, dict):
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)

    data = {**media.serialize(asset), **payload}
    form = MediaAssetMetadataForm(data=data, instance=asset)
    if not form.is_valid():
        return json_error("invalid", "Revise os campos.", 400, fields=form.errors.get_json_data())
    form.save()
    return JsonResponse(media.serialize(asset))
