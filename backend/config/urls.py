from django.contrib import admin
from django.urls import include, path

from apps.accounts.urls import allauth_overrides

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    *allauth_overrides,
    path("admin/", admin.site.urls),
    # Login Microsoft: /entrar/microsoft/login/ e /entrar/microsoft/login/callback/
    path("entrar/", include("allauth.urls")),
]
