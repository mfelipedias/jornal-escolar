"""Conta aguardando aprovação (Fase 4b, C2; docs/27 quinta rodada).

Quem se cadastrou sozinho entra, completa o perfil e vê a tela "aguardando aprovação". No
painel (/painel/ e /x/) só alcança o que está em ALLOWED; o resto volta para a tela de espera
(ou responde 403 em pedidos que não são de página). O site público continua normal.
As permissões também recusam (permissions.is_staff_member): este filtro só dá o caminho certo.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

PANEL_PREFIXES = ("/painel/", "/x/")
ALLOWED = frozenset(
    {
        "accounts:pending",
        "accounts:onboarding",
        "accounts:onboarding_done",
        "accounts:profile_edit",
        "accounts:account_settings",
        "editorial:notifications",
        "editorial:notification_dropdown",
        "editorial:notification_read_all",
        "editorial:notification_open",
        # Reagir, contar leitura e comentar são do público; a pessoa também é leitora.
        "engagement:react",
        "engagement:read",
        "engagement:comment",
    }
)


class PendingApprovalMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_approved
            and request.path_info.startswith(PANEL_PREFIXES)
        ):
            try:
                view_name = resolve(request.path_info).view_name
            except Resolver404:
                view_name = ""
            if view_name not in ALLOWED:
                if request.method == "GET" and request.headers.get("HX-Request") != "true":
                    return redirect("accounts:pending")
                return HttpResponseForbidden("Conta aguardando aprovação.")
        return self.get_response(request)
