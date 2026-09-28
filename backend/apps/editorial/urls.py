from django.urls import path

from . import panel_views, views

app_name = "editorial"

urlpatterns = [
    path("painel/editorial/", panel_views.overview, name="overview"),
    path("painel/editorial/publicacoes/", panel_views.articles, name="articles"),
    path("painel/editorial/publicacoes/acoes/", panel_views.bulk_action, name="bulk_action"),
    path("painel/editorial/contas/", panel_views.accounts, name="accounts"),
    path(
        "painel/editorial/contas/<int:pk>/<str:action>/",
        panel_views.account_action,
        name="account_action",
    ),
    path("painel/notificacoes/", views.notification_list, name="notifications"),
    path("x/notifications/", views.notification_dropdown, name="notification_dropdown"),
    path("x/notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("x/notifications/<int:pk>/abrir/", views.notification_open, name="notification_open"),
    path("painel/revisao/", views.review_queue, name="queue"),
    path("painel/publicacoes/<int:pk>/revisar/", views.review, name="review"),
    path("x/articles/<int:pk>/review-comments/", views.comment_create, name="comment_create"),
    path("x/review-comments/<int:pk>/reply/", views.comment_reply, name="comment_reply"),
    path("x/review-comments/<int:pk>/<str:action>/", views.comment_status, name="comment_status"),
    path("painel/destaques/", views.featured, name="featured"),
    path("x/featured/search/", views.featured_search, name="featured_search"),
    path("x/articles/<int:pk>/feature/", views.feature, name="feature"),
]
