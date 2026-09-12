from django.urls import path

from . import editor_views, views

app_name = "publications"

urlpatterns = [
    # Painel
    path("painel/publicacoes/nova/", editor_views.create, name="create"),
    path("painel/publicacoes/<int:pk>/editar/", editor_views.edit, name="edit"),
    # Endpoints internos
    path("x/articles/<int:pk>/body/", editor_views.save_body, name="save_body"),
    path("x/media/", views.media_upload, name="media_upload"),
    path("x/media/<int:pk>/", views.media_detail, name="media_detail"),
]
