from django.urls import path

from . import views

app_name = "curation"

urlpatterns = [
    path("painel/sugestoes/", views.suggestions, name="suggestions"),
    path(
        "x/sugestoes/<int:pk>/virar-pauta/",
        views.suggestion_to_idea,
        name="suggestion_to_idea",
    ),
    path("painel/pautas/", views.story_ideas, name="story_ideas"),
    path("painel/pautas/nova/", views.story_idea_create, name="story_idea_create"),
    path("painel/pautas/<int:pk>/editar/", views.story_idea_edit, name="story_idea_edit"),
    path("x/pautas/<int:pk>/<str:action>/", views.story_idea_action, name="story_idea_action"),
    path(
        "x/sugestoes/<int:pk>/<str:action>/",
        views.suggestion_action,
        name="suggestion_action",
    ),
]
