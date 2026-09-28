"""Menu lateral do painel (docs/15, "Menu lateral").

Itens da Fase 1; Revisões (E31) com o contador de revisões pedidas à pessoa; Comentários (E41)
com o contador de comentários públicos pendentes que a pessoa modera; Editorial (E33) só para
editor+, agrupando visão geral, todas as publicações, Destaques e Páginas (as duas últimas
mantêm os endereços da E25). Sugestões (E48) com o contador de sugestões de pauta ainda não
vistas; Pautas (E49) com o contador das pautas com a pessoa.
"""

from dataclasses import dataclass

from django.urls import reverse

from apps.accounts.models import User
from apps.curation import selectors as curation_selectors
from apps.editorial import permissions, selectors
from apps.engagement import selectors as engagement_selectors


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    url: str
    icon: str
    active: bool = False
    external: bool = False  # sai do painel (admin, jornal)
    count: int = 0  # contador ao lado do rótulo (0 esconde)


# Rota atual → item do menu marcado como ativo.
ACTIVE_BY_VIEW = {
    "dashboard:home": "home",
    "dashboard:my_articles": "my_articles",
    "publications:create": "create",
    "accounts:profile_edit": "profile",
    "accounts:account_settings": "account",
    "editorial:notifications": "home",
    "editorial:queue": "reviews",
    "editorial:review": "reviews",
    "engagement:moderation": "comments",
    "curation:suggestions": "suggestions",
    "curation:story_ideas": "ideas",
    "curation:story_idea_edit": "ideas",
    "editorial:overview": "editorial",
    "editorial:articles": "editorial",
    "editorial:featured": "editorial",
    "core:page_list": "editorial",
}


def menu_items(user: User, view_name: str = "") -> list[MenuItem]:
    active = ACTIVE_BY_VIEW.get(view_name, "")
    rows = [
        ("home", "Início", reverse("dashboard:home"), "home", False),
        ("my_articles", "Minhas publicações", reverse("dashboard:my_articles"), "list", False),
        ("create", "Nova publicação", reverse("publications:create"), "plus", False),
        ("reviews", "Revisões", reverse("editorial:queue"), "check", False),
        ("comments", "Comentários", reverse("engagement:moderation"), "message", False),
        ("suggestions", "Sugestões", reverse("curation:suggestions"), "bulb", False),
        ("ideas", "Pautas", reverse("curation:story_ideas"), "board", False),
    ]
    if permissions.can_access_editorial(user):
        rows.append(("editorial", "Editorial", reverse("editorial:overview"), "grid", False))
    rows += [
        ("profile", "Perfil", reverse("accounts:profile_edit"), "user", False),
        ("account", "Conta", reverse("accounts:account_settings"), "key", False),
    ]
    if permissions.can_access_admin(user):
        rows.append(("admin", "Administração", reverse("admin:index"), "settings", True))
    rows.append(("site", "Ver o jornal", reverse("core:home"), "newspaper", True))
    counts = {
        "reviews": selectors.pending_review_count(user),
        "comments": engagement_selectors.pending_count(user),
        "suggestions": curation_selectors.suggestion_count(user),
        "ideas": curation_selectors.my_idea_count(user),
    }
    return [
        MenuItem(
            key=key,
            label=label,
            url=url,
            icon=icon,
            active=key == active,
            external=ext,
            count=counts.get(key, 0),
        )
        for key, label, url, icon, ext in rows
    ]
