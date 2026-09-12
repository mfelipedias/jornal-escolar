from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from allauth.account.views import LoginView as AllauthLoginView
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from . import services
from .forms import AccessLinkPasswordForm
from .models import AccessLink


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


@never_cache
@sensitive_post_parameters("new_password1", "new_password2")
@require_http_methods(["GET", "POST"])
def access_link(request: HttpRequest, token: UUID) -> HttpResponse:
    """/acesso/<código>/: criar ou redefinir a senha com um link gerado pelo admin."""
    link = AccessLink.objects.select_related("user").filter(pk=token).first()
    if link is None or not link.is_valid:
        response = render(request, "accounts/access_link_invalid.html", status=410)
        response["Referrer-Policy"] = "no-referrer"
        return response

    form = AccessLinkPasswordForm(link.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = services.use_access_link(link, form.cleaned_data["new_password1"])
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Senha criada. Você já está dentro do jornal.")
        return redirect("/")

    response = render(request, "accounts/access_link.html", {"form": form, "link": link})
    response["Referrer-Policy"] = "no-referrer"
    return response


def not_found(request: HttpRequest, *args: Any, **kwargs: Any):
    """Recursos do allauth que não usamos (cadastro, e-mail, recuperação por e-mail)."""
    raise Http404
