from django.core.cache import cache

from .models import StaticPage

FOOTER_PAGES_CACHE_KEY = "core:footer_pages:v1"
FOOTER_PAGES_CACHE_TIMEOUT = 60

# Ordem dos links no rodapé (docs/09): Sobre · Privacidade · Como participar.
FOOTER_ORDER = [StaticPage.Slug.ABOUT, StaticPage.Slug.PRIVACY, StaticPage.Slug.CONTRIBUTE]


def footer_pages() -> list[dict[str, str]]:
    """Links do rodapé para as páginas institucionais publicadas."""
    pages = cache.get(FOOTER_PAGES_CACHE_KEY)
    if pages is None:
        published = set(StaticPage.objects.filter(is_published=True).values_list("slug", flat=True))
        pages = [
            {"slug": slug.value, "label": slug.label}
            for slug in FOOTER_ORDER
            if slug.value in published
        ]
        cache.set(FOOTER_PAGES_CACHE_KEY, pages, FOOTER_PAGES_CACHE_TIMEOUT)
    return pages


def clear_footer_pages_cache() -> None:
    cache.delete(FOOTER_PAGES_CACHE_KEY)
