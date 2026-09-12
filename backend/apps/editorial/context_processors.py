from django.http import HttpRequest

from .notifications import unread_count


def notifications(request: HttpRequest) -> dict[str, int]:
    """Contador do sino em todas as páginas (uma consulta, só para quem entrou)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"notification_unread": unread_count(user)}
