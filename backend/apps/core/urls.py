from django.urls import path, register_converter

from . import dev_views, views
from .converters import StaticPageSlugConverter

register_converter(StaticPageSlugConverter, "pageslug")

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("dev/components/", dev_views.components, name="components"),
    path("<pageslug:slug>/", views.page, name="page"),
]
