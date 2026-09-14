from collections.abc import Callable

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string


class HtmxMessagesMiddleware:
    """Em respostas HTMX, entrega as mensagens do Django como toasts (docs/09).

    A página não recarrega, então as mensagens vão junto do fragmento como um
    trecho "out of band" que o HTMX acrescenta na região de toasts do base.html.
    Views usam messages.success(...) igual às páginas normais.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if (
            request.headers.get("HX-Request") != "true"
            or response.streaming
            or not 200 <= response.status_code < 300
            or "HX-Redirect" in response
            or not response.get("Content-Type", "").startswith("text/html")
        ):
            return response
        pending = list(messages.get_messages(request))
        if pending:
            response.content += render_to_string(
                "components/toast_oob.html", {"toast_messages": pending}
            ).encode()
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        return response


class SecurityHeadersMiddleware:
    """Content-Security-Policy e Permissions-Policy em todas as respostas (docs/23).

    A política vem de settings.CONTENT_SECURITY_POLICY (dicionário diretiva -> valores);
    None desliga, como no desenvolvimento com o servidor do Vite, que injeta estilos e usa
    outra porta. O Django Admin ganha 'unsafe-inline' em estilos: os templates dele usam
    atributos style. Scripts nunca aceitam 'unsafe-inline'.
    """

    ADMIN_PREFIX = "/admin/"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        policy = settings.CONTENT_SECURITY_POLICY
        if policy and "Content-Security-Policy" not in response:
            directives = {key: list(values) for key, values in policy.items()}
            if request.path.startswith(self.ADMIN_PREFIX):
                directives["style-src"] = [*directives.get("style-src", []), "'unsafe-inline'"]
            response["Content-Security-Policy"] = "; ".join(
                " ".join([name, *values]) for name, values in directives.items()
            )
        if settings.PERMISSIONS_POLICY and "Permissions-Policy" not in response:
            response["Permissions-Policy"] = settings.PERMISSIONS_POLICY
        return response


class AppVersionHeaderMiddleware:
    """Adiciona X-App-Version a todas as respostas (docs/30)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response["X-App-Version"] = settings.APP_VERSION
        return response
