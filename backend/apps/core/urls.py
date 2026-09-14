from django.urls import path, register_converter

from . import dev_views, panel_views, views
from .converters import StaticPageSlugConverter

register_converter(StaticPageSlugConverter, "pageslug")

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("dev/components/", dev_views.components, name="components"),
    path("<pageslug:slug>/", views.page, name="page"),
    # Painel (editor+)
    path("painel/paginas/", panel_views.page_list, name="page_list"),
    path("painel/paginas/<pageslug:slug>/editar/", panel_views.page_edit, name="page_edit"),
    path("painel/paginas/<pageslug:slug>/publicar/", panel_views.page_publish, name="page_publish"),
    path("x/pages/<pageslug:slug>/body/", panel_views.page_save_body, name="page_save_body"),
]
