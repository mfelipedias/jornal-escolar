"""Regras de entrada no sistema (docs/23, "Autenticação").

- Ninguém cria conta sozinho: o admin cadastra.
- Login Microsoft só para domínios permitidos e contas já cadastradas e ativas.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from apps.editorial import permissions

from . import services

MSG_NOT_REGISTERED = "Peça ao administrador para cadastrar você."
MSG_DOMAIN = "Use o seu e-mail institucional da escola."
MSG_INACTIVE = "Sua conta está desativada. Fale com o administrador."
MSG_DISABLED = "O login com a conta Microsoft está desligado. Entre com e-mail e senha."


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return False

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """Sem ?next=, o primeiro login (senha ou Microsoft) leva ao assistente (docs/14)."""
        user = request.user
        if user.is_authenticated and services.needs_onboarding(user):
            return reverse("accounts:onboarding", kwargs={"step": 1})
        return super().get_login_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: SocialLogin) -> bool:
        return False

    def pre_social_login(self, request: HttpRequest, sociallogin: SocialLogin) -> None:
        if not services.microsoft_login_enabled():
            self._reject(request, MSG_DISABLED)

        email = services.microsoft_verified_email(sociallogin.account.extra_data or {})
        if not email or not services.email_domain_allowed(email):
            self._reject(request, MSG_DOMAIN)

        user = services.find_staff_account(email)
        if user is None:
            self._reject(request, MSG_NOT_REGISTERED)
        if not permissions.can_log_in(user):
            self._reject(request, MSG_INACTIVE)

        if sociallogin.is_existing:
            if sociallogin.user.pk != user.pk:
                # A conta Microsoft já está ligada a outro usuário: não misturar contas.
                self._reject(request, MSG_NOT_REGISTERED)
            return

        sociallogin.connect(request, user)

    def _reject(self, request: HttpRequest, message: str) -> None:
        messages.error(request, message)
        raise ImmediateHttpResponse(redirect("accounts:login"))
