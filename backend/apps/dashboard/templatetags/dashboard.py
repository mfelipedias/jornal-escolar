"""Tags do layout do painel. Uso: {% load dashboard %}."""

from django import template

from apps.dashboard.menu import MenuItem, menu_items

register = template.Library()


@register.simple_tag(takes_context=True)
def dashboard_menu(context: template.Context) -> list[MenuItem]:
    """{% dashboard_menu as items %}: itens do menu lateral com o atual marcado."""
    request = context["request"]
    match = getattr(request, "resolver_match", None)
    return menu_items(request.user, match.view_name if match else "")
