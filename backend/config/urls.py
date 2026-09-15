from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.accounts.urls import allauth_overrides

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.publications.urls")),
    path("", include("apps.publications.search_urls")),
    path("", include("apps.taxonomy.urls")),
    path("", include("apps.editorial.urls")),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.engagement.urls")),
    *allauth_overrides,
    path("admin/", admin.site.urls),
    # Login Microsoft: /entrar/microsoft/login/ e /entrar/microsoft/login/callback/
    path("entrar/", include("allauth.urls")),
]

if settings.DEBUG:
    # Em produção o Caddy serve /media/ direto do volume (docs/24).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
