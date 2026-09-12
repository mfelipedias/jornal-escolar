from typing import Any
from urllib.parse import urlencode

from allauth.account.views import LoginView as AllauthLoginView
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.urls import reverse

from . import services


class LoginView(AllauthLoginView):
    """/entrar/: botão da Microsoft (quando ligado) e senha de reserva."""

    template_name = "account/login.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["microsoft_login_enabled"] = services.microsoft_login_enabled()
        return context


login = LoginView.as_view()


def redirect_to_login(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseRedirect:
    """Uma única tela de login (com limite de tentativas), inclusive para o /admin/."""
    url = reverse("accounts:login")
    next_url = request.GET.get("next")
    if next_url:
        url = f"{url}?{urlencode({'next': next_url})}"
    return HttpResponseRedirect(url)


def not_found(request: HttpRequest, *args: Any, **kwargs: Any):
    """Recursos do allauth que não usamos (cadastro, e-mail, recuperação por e-mail)."""
    raise Http404
