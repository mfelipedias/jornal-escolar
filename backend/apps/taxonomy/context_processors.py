"""Áreas para a linha de navegação do cabeçalho público (docs/09, "Masthead")."""

from django.core.cache import cache
from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from .models import KnowledgeArea

NAV_AREAS_KEY = "taxonomy:nav-areas"


def nav_areas() -> list[KnowledgeArea]:
    return cache.get_or_set(
        NAV_AREAS_KEY, lambda: list(KnowledgeArea.objects.filter(is_active=True)), timeout=None
    )


def navigation(request: HttpRequest) -> dict:
    # Preguiçoso: páginas sem cabeçalho público (editor, admin) não consultam nada.
    return {"nav_areas": SimpleLazyObject(nav_areas)}
