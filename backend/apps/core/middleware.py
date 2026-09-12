from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class AppVersionHeaderMiddleware:
    """Adiciona X-App-Version a todas as respostas (docs/30)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response["X-App-Version"] = settings.APP_VERSION
        return response
