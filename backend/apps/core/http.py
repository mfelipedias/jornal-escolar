from typing import Any

from django.http import JsonResponse


def json_error(code: str, message: str, status: int, **extra: Any) -> JsonResponse:
    """Formato único de erro dos endpoints internos /x/ (docs/07)."""
    return JsonResponse({"error": {"code": code, "message": message, **extra}}, status=status)
