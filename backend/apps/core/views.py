from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import services


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
