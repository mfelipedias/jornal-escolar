from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import notifications
from .models import Notification


@require_GET
@login_required
def notification_list(request):
    """/painel/notificacoes/: histórico completo (as mais recentes primeiro)."""
    items = Notification.objects.filter(user=request.user).select_related("actor")[:200]
    return render(request, "editorial/notifications.html", {"notifications": items})


@require_GET
@login_required
def notification_dropdown(request):
    """GET /x/notifications/: lista suspensa do sino."""
    return render(
        request,
        "editorial/partials/notification_list.html",
        {"notifications": notifications.recent(request.user)},
    )


@require_POST
@login_required
def notification_read_all(request):
    """POST /x/notifications/read-all/: devolve o sino zerado (HTMX) ou volta para a lista."""
    notifications.mark_all_read(request.user)
    if not request.headers.get("HX-Request"):
        return redirect("editorial:notifications")
    return render(
        request,
        "components/notification_bell.html",
        {"notification_unread": 0, "notifications": notifications.recent(request.user)},
    )


@require_GET
@login_required
def notification_open(request, pk: int):
    """/x/notifications/<id>/abrir/: marca como lida e leva ao objeto."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notifications.mark_read(notification)
    target = notification.url
    # Só endereços internos: nunca redirecionar para fora do site.
    if not target or urlsplit(target).netloc or not target.startswith("/"):
        target = "editorial:notifications"
    return redirect(target)
