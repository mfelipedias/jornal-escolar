from django.urls import path

from . import views

app_name = "taxonomy"

urlpatterns = [
    path("areas/<slug:slug>/", views.area, name="area"),
    path("disciplinas/<slug:slug>/", views.discipline, name="discipline"),
    path("tipos/<slug:slug>/", views.article_type, name="type"),
    path("topicos/<slug:slug>/", views.topic, name="topic"),
]
