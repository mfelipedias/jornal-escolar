from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("painel/", views.home, name="home"),
    path("painel/publicacoes/", views.my_articles, name="my_articles"),
]
