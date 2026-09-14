"""Menu lateral do painel (docs/15, "Menu lateral").

Só entram os itens da Fase 1. Revisões, Comentários, Sugestões, Pautas e Editorial
aparecem quando as fases deles chegarem: basta acrescentar a linha aqui.
"""

from dataclasses import dataclass

from django.urls import reverse

from apps.accounts.models import User
from apps.editorial import permissions


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    url: str
    icon: str
    active: bool = False
    external: bool = False  # sai do painel (admin, jornal)


# Rota atual → item do menu marcado como ativo.
ACTIVE_BY_VIEW = {
    "dashboard:home": "home",
    "dashboard:my_articles": "my_articles",
    "publications:create": "create",
    "accounts:profile_edit": "profile",
    "accounts:account_settings": "account",
    "editorial:notifications": "home",
}


def menu_items(user: User, view_name: str = "") -> list[MenuItem]:
    active = ACTIVE_BY_VIEW.get(view_name, "")
    rows = [
        ("home", "Início", reverse("dashboard:home"), "home", False),
        ("my_articles", "Minhas publicações", reverse("dashboard:my_articles"), "list", False),
        ("create", "Nova publicação", reverse("publications:create"), "plus", False),
        ("profile", "Perfil", reverse("accounts:profile_edit"), "user", False),
        ("account", "Conta", reverse("accounts:account_settings"), "key", False),
    ]
    if permissions.is_admin(user):
        rows.append(("admin", "Administração", reverse("admin:index"), "settings", True))
    rows.append(("site", "Ver o jornal", reverse("core:home"), "newspaper", True))
    return [
        MenuItem(key=key, label=label, url=url, icon=icon, active=key == active, external=ext)
        for key, label, url, icon, ext in rows
    ]
