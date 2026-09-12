from django.urls import path, register_converter

from . import views
from .converters import StaticPageSlugConverter

register_converter(StaticPageSlugConverter, "pageslug")

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("<pageslug:slug>/", views.page, name="page"),
]
