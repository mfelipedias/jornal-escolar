from django.urls import path

from . import editor_views, public_views, views

app_name = "publications"

urlpatterns = [
    # Público
    path("publicacoes/", public_views.article_list, name="list"),
    path("agenda/", public_views.agenda, name="agenda"),
    path("publicacoes/previa/<int:pk>/", public_views.preview, name="preview"),
    path("publicacoes/<slug:slug>/", public_views.detail, name="detail"),
    # Painel
    path("painel/publicacoes/nova/", editor_views.create, name="create"),
    path("painel/publicacoes/<int:pk>/editar/", editor_views.edit, name="edit"),
    # Endpoints internos do editor
    path("x/articles/<int:pk>/body/", editor_views.save_body, name="save_body"),
    path("x/articles/<int:pk>/meta/", editor_views.save_meta, name="save_meta"),
    path("x/articles/<int:pk>/cover/", editor_views.save_cover, name="save_cover"),
    path("x/articles/<int:pk>/checklist/", editor_views.checklist, name="checklist"),
    path("x/articles/<int:pk>/contributors/", editor_views.add_contributor, name="add_contributor"),
    path(
        "x/articles/<int:pk>/contributors/<int:cid>/",
        editor_views.remove_contributor,
        name="remove_contributor",
    ),
    path(
        "x/articles/<int:pk>/transition/<slug:action>/",
        editor_views.transition,
        name="transition",
    ),
    path("x/articles/<int:pk>/duplicate/", editor_views.duplicate, name="duplicate"),
    path("x/users/search/", editor_views.search_users, name="search_users"),
    # Imagens
    path("x/media/", views.media_upload, name="media_upload"),
    path("x/media/<int:pk>/", views.media_detail, name="media_detail"),
]
