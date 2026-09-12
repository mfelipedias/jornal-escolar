from django.urls import path

from . import views

app_name = "publications"

urlpatterns = [
    path("x/media/", views.media_upload, name="media_upload"),
    path("x/media/<int:pk>/", views.media_detail, name="media_detail"),
]
