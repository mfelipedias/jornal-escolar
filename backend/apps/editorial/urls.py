from django.urls import path

from . import views

app_name = "editorial"

urlpatterns = [
    path("painel/notificacoes/", views.notification_list, name="notifications"),
    path("x/notifications/", views.notification_dropdown, name="notification_dropdown"),
    path("x/notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("x/notifications/<int:pk>/abrir/", views.notification_open, name="notification_open"),
    path("painel/destaques/", views.featured, name="featured"),
    path("x/featured/search/", views.featured_search, name="featured_search"),
    path("x/articles/<int:pk>/feature/", views.feature, name="feature"),
]
