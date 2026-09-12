from typing import Any

from django.conf import settings
from django.http import HttpRequest

# Valores padrão da identidade do site (docs/06, core.SiteSetting).
# Na E08 passam a vir do banco, editáveis no painel; as chaves continuam as mesmas.
SITE_DEFAULTS = {
    "name": "Jornal Escolar",
    "tagline": "Jornal digital da comunidade escolar",
    "footer_credit": "Desenvolvido por Professor Marcos Felipe A. D. da Silva",
    "contact_email": "marcossilva06@professor.educacao.sp.gov.br",
}


def split_wordmark(name: str) -> tuple[str, str]:
    """Separa a última palavra do nome, que aparece na cor de acento ("Jornal" + "Escolar")."""
    head, _, last = name.strip().rpartition(" ")
    return head, last


def site(request: HttpRequest) -> dict[str, Any]:
    head, last = split_wordmark(SITE_DEFAULTS["name"])
    return {
        "site": {**SITE_DEFAULTS, "wordmark_head": head, "wordmark_accent": last},
        "app_version": settings.APP_VERSION,
    }
