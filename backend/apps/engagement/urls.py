from django.urls import path

from . import panel_views, views

app_name = "engagement"

urlpatterns = [
    path("x/articles/<int:pk>/react/", views.react, name="react"),
    path("x/articles/<int:pk>/read/", views.read, name="read"),
    path("x/articles/<int:pk>/comments/", views.comment, name="comment"),
    path("x/comments/<int:pk>/reply/", views.reply, name="reply"),
    path("painel/comentarios/", panel_views.moderation, name="moderation"),
    path("x/comments/bulk/", panel_views.bulk, name="moderate_bulk"),
    path("x/comments/<int:pk>/<str:action>/", panel_views.moderate, name="moderate"),
    path(
        "x/articles/<int:pk>/comments-toggle/",
        panel_views.comments_toggle,
        name="comments_toggle",
    ),
]
