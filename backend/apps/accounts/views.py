from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from allauth.account.views import LoginView as AllauthLoginView
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from . import services, signup
from .forms import (
    AccessLinkPasswordForm,
    PasswordResetRequestForm,
    SignupConfirmForm,
    SignupRequestForm,
)
from .models import AccessLink, EmailCode, User


class LoginView(AllauthLoginView):
    """/entrar/: botão da Microsoft (quando ligado) e senha de reserva."""

    template_name = "account/login.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["microsoft_login_enabled"] = services.microsoft_login_enabled()
        context["signup_available"] = signup.signup_available()
        context["password_reset_available"] = signup.password_reset_available()
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
        if services.needs_onboarding(user):
            return redirect("accounts:onboarding", step=1)
        return redirect("/")

    response = render(request, "accounts/access_link.html", {"form": form, "link": link})
    response["Referrer-Policy"] = "no-referrer"
    return response


def not_found(request: HttpRequest, *args: Any, **kwargs: Any):
    """Recursos do allauth que não usamos (cadastro, e-mail, recuperação por e-mail)."""
    raise Http404


# --- Cadastro próprio (Fase 4b, C1) ---

SIGNUP_SESSION_KEY = "signup_email"


def _signup_guard(request: HttpRequest) -> HttpResponse | None:
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    if not signup.signup_available():
        raise Http404
    return None


@never_cache
@require_http_methods(["GET", "POST"])
def signup_request(request: HttpRequest) -> HttpResponse:
    """/cadastro/: nome e e-mail; o código vai por e-mail (docs/27, quinta rodada)."""
    if (response := _signup_guard(request)) is not None:
        return response
    form = SignupRequestForm(request.POST or None)
    status = 200
    if request.method == "POST":
        if form.is_valid() and form.cleaned_data["website"]:
            # Campo-isca preenchido: robô. Finge que deu certo e não envia nada.
            request.session[SIGNUP_SESSION_KEY] = form.cleaned_data["email"].lower()
            return redirect("accounts:signup_confirm")
        if form.is_valid():
            try:
                signup.request_signup(
                    form.cleaned_data["email"], form.cleaned_data["full_name"], request
                )
            except ValidationError as exc:
                _add_errors(form, exc)
            except signup.RateLimited as exc:
                form.add_error(None, str(exc))
                status = 429
            else:
                request.session[SIGNUP_SESSION_KEY] = form.cleaned_data["email"].lower()
                return redirect("accounts:signup_confirm")
        if status == 200:
            status = 400
    context = {"form": form, "domains": signup.domain_message()}
    return render(request, "accounts/signup.html", context, status=status)


def _add_errors(form, exc: ValidationError) -> None:
    """Erros do serviço no formulário: no campo quando ele existe, senão no topo."""
    if not hasattr(exc, "error_dict"):
        form.add_error(None, exc)
        return
    for field, errors in exc.error_dict.items():
        for error in errors:
            form.add_error(field if field in form.fields else None, error)


@never_cache
@sensitive_post_parameters("new_password1", "new_password2", "code")
@require_http_methods(["GET", "POST"])
def signup_confirm(request: HttpRequest) -> HttpResponse:
    """/cadastro/confirmar/: código + senha. Cria a conta e leva ao assistente."""
    if (response := _signup_guard(request)) is not None:
        return response
    email = request.session.get(SIGNUP_SESSION_KEY)
    if not email:
        return redirect("accounts:signup")
    pending = EmailCode.objects.filter(email=email, purpose=EmailCode.Purpose.SIGNUP).first()
    name = pending.full_name if pending else ""
    form = SignupConfirmForm(signup.provisional_user(email, name), request.POST or None)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                user = signup.complete_signup(
                    email, form.cleaned_data["code"], form.cleaned_data["new_password1"], request
                )
            except ValidationError as exc:
                _add_errors(form, exc)
            except signup.RateLimited as exc:
                form.add_error(None, str(exc))
                status = 429
            else:
                request.session.pop(SIGNUP_SESSION_KEY, None)
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Conta criada. Agora conte um pouco sobre você.")
                return redirect("accounts:onboarding", step=1)
        if status == 200:
            status = 400
    context = {"form": form, "email": email}
    return render(request, "accounts/signup_confirm.html", context, status=status)


# --- "Esqueci minha senha" (Fase 4b, C3) ---

RESET_SESSION_KEY = "password_reset_email"


def _reset_guard(request: HttpRequest) -> None:
    if not signup.password_reset_available():
        raise Http404


@never_cache
@require_http_methods(["GET", "POST"])
def password_reset(request: HttpRequest) -> HttpResponse:
    """/entrar/esqueci/: e-mail da conta; o código vai por e-mail. Resposta sempre igual."""
    _reset_guard(request)
    form = PasswordResetRequestForm(request.POST or None)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            try:
                signup.request_password_reset(email, request)
            except signup.RateLimited as exc:
                form.add_error(None, str(exc))
                status = 429
            else:
                request.session[RESET_SESSION_KEY] = email
                return redirect("accounts:password_reset_confirm")
        if status == 200:
            status = 400
    return render(request, "accounts/password_reset.html", {"form": form}, status=status)


@never_cache
@sensitive_post_parameters("new_password1", "new_password2", "code")
@require_http_methods(["GET", "POST"])
def password_reset_confirm(request: HttpRequest) -> HttpResponse:
    """/entrar/esqueci/confirmar/: código + senha nova. Entra direto depois."""
    _reset_guard(request)
    email = request.session.get(RESET_SESSION_KEY)
    if not email:
        return redirect("accounts:password_reset")
    person = User.objects.filter(email=email).first() or signup.provisional_user(email)
    form = SignupConfirmForm(person, request.POST or None)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                user = signup.complete_password_reset(
                    email, form.cleaned_data["code"], form.cleaned_data["new_password1"], request
                )
            except ValidationError as exc:
                _add_errors(form, exc)
            except signup.RateLimited as exc:
                form.add_error(None, str(exc))
                status = 429
            else:
                request.session.pop(RESET_SESSION_KEY, None)
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Senha nova criada. Você já está dentro do jornal.")
                return redirect("dashboard:home")
        if status == 200:
            status = 400
    context = {"form": form, "email": email}
    return render(request, "accounts/password_reset_confirm.html", context, status=status)
