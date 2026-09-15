"""Rotas da busca, com nome próprio (search:results, docs/07)."""

from django.urls import path

from . import search_views

app_name = "search"

urlpatterns = [
    path("busca/", search_views.results, name="results"),
]
