from allauth.account.views import logout
from django.urls import path, re_path

from . import public_views, views

app_name = "accounts"

urlpatterns = [
    path("professores/", public_views.teacher_list, name="teacher_list"),
    path("professores/<slug:slug>/", public_views.teacher_detail, name="teacher_detail"),
    path("entrar/", views.login, name="login"),
    path("sair/", logout, name="logout"),
    path("acesso/<uuid:token>/", views.access_link, name="access_link"),
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
