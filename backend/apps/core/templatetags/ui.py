"""Filtros dos componentes de interface (docs/09). Uso: {% load ui %}."""

from django import template
from django.core.paginator import Page

register = template.Library()

# Estados editoriais: rótulo e classes do status-badge. in_review, changes_requested e
# approved ainda não existem no modelo (E29), mas o componente já sabe desenhá-los.
STATUS_BADGES: dict[str, tuple[str, str]] = {
    "draft": ("Rascunho", "bg-paper-2 text-ink-2"),
    "in_review": ("Em revisão", "bg-area-ambar-soft text-area-ambar"),
    "changes_requested": ("Alterações pedidas", "bg-area-coral-soft text-area-coral"),
    "approved": ("Aprovado", "bg-area-azul-soft text-area-azul"),
    "published": ("Publicado", "bg-area-verde-soft text-area-verde"),
    "archived": ("Arquivado", "bg-area-grafite-soft text-area-grafite"),
}


@register.filter
def status_badge(status: str) -> dict[str, str]:
    """{% with badge=article.status|status_badge %}: {"label": ..., "classes": ...}."""
    label, classes = STATUS_BADGES.get(str(status), (str(status), STATUS_BADGES["draft"][1]))
    return {"label": label, "classes": classes}


@register.filter
def elided_pages(page_obj: Page) -> list:
    """Números de página com reticências: 1 … 4 5 6 … 12."""
    return list(
        page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    )
