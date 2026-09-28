from django.urls import path

from . import views

app_name = "curation"

urlpatterns = [
    path("painel/sugestoes/", views.suggestions, name="suggestions"),
    path(
        "x/sugestoes/<int:pk>/<str:action>/",
        views.suggestion_action,
        name="suggestion_action",
    ),
]
