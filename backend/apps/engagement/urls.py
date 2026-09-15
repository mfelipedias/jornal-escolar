from django.urls import path

from . import views

app_name = "engagement"

urlpatterns = [
    path("x/articles/<int:pk>/react/", views.react, name="react"),
    path("x/articles/<int:pk>/read/", views.read, name="read"),
    path("x/articles/<int:pk>/comments/", views.comment, name="comment"),
    path("x/comments/<int:pk>/reply/", views.reply, name="reply"),
]
