from allauth.account.views import logout
from django.urls import path, re_path

from . import views

app_name = "accounts"

urlpatterns = [
    path("entrar/", views.login, name="login"),
    path("sair/", logout, name="logout"),
]

# Rotas que precisam vir antes de include("allauth.urls") em config/urls.py.
allauth_overrides = [
    path("entrar/login/", views.redirect_to_login),
    path("admin/login/", views.redirect_to_login),
    # Sem cadastro aberto, sem e-mail e sem recuperação de senha automática (docs/23).
    re_path(
        r"^entrar/(?:signup|password/reset|email|confirm-email|reauthenticate|login/code)(?:/.*)?$",
        views.not_found,
    ),
    re_path(r"^entrar/3rdparty/(?:signup/)?$", views.not_found),
]
