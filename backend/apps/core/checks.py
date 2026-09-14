"""Verificações de implantação: rodam com "manage.py check --deploy" (docs/34).

SITE_URL monta os endereços do sitemap, do Open Graph e do JSON-LD (E26). Se ficar com o
valor de desenvolvimento em produção, buscadores e o WhatsApp recebem links para localhost.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Tags, Warning, register

LOCAIS = {"localhost", "127.0.0.1", "0.0.0.0", ""}


@register(Tags.urls, deploy=True)
def check_site_url(app_configs=None, **kwargs):
    partes = urlsplit(settings.SITE_URL)
    problemas = []
    if partes.hostname in LOCAIS or partes.hostname is None:
        problemas.append(
            Warning(
                f"SITE_URL aponta para {settings.SITE_URL!r}.",
                hint="Em produção use o domínio real, ex.: https://jornal.projetosrosa.com.br",
                id="core.W001",
            )
        )
    elif partes.scheme != "https":
        problemas.append(
            Warning(
                f"SITE_URL não usa https: {settings.SITE_URL!r}.",
                hint="A Cloudflare entrega o site em https; use https:// em SITE_URL.",
                id="core.W002",
            )
        )
    elif partes.path not in {"", "/"}:
        problemas.append(
            Warning(
                "SITE_URL deve ser só o endereço do site, sem caminho nem barra no fim.",
                id="core.W003",
            )
        )
    return problemas
