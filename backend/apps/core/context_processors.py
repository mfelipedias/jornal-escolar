from typing import Any

from django.conf import settings
from django.http import HttpRequest

from .selectors import footer_pages
from .site_settings import get_settings


def split_wordmark(name: str) -> tuple[str, str]:
    """Separa a última palavra do nome, que aparece na cor de acento ("Jornal" + "Escolar")."""
    head, _, last = name.strip().rpartition(" ")
    return head, last


def site(request: HttpRequest) -> dict[str, Any]:
    """Identidade do site para todos os templates: {{ site.name }}, {{ app_version }}..."""
    values = get_settings("site.")
    head, last = split_wordmark(values["site.name"])
    return {
        "site": {
            "name": values["site.name"],
            "tagline": values["site.tagline"],
            "footer_credit": values["site.footer_credit"],
            "contact_email": values["site.contact_email"],
            "show_date": values["site.show_date"],
            "wordmark_head": head,
            "wordmark_accent": last,
            "footer_pages": footer_pages(),
        },
        "app_version": settings.APP_VERSION,
    }
