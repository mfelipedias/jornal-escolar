from typing import Any

from django.http import HttpResponse, JsonResponse


def json_error(code: str, message: str, status: int, **extra: Any) -> JsonResponse:
    """Formato único de erro dos endpoints internos /x/ (docs/07)."""
    return JsonResponse({"error": {"code": code, "message": message, **extra}}, status=status)


def attachment(content: bytes, filename: str, mime: str) -> HttpResponse:
    """Arquivo para baixar (exportação de dados), sem guardar em cache nenhum."""
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response
