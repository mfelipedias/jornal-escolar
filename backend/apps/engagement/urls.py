from django.urls import path

from . import views

app_name = "engagement"

urlpatterns = [
    path("x/articles/<int:pk>/react/", views.react, name="react"),
]
