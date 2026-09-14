"""Metadados para buscadores e compartilhamento (docs/10, 11, 13; E26).

Cada página pública monta um PageMeta e passa no contexto como "seo". O template
components/seo.html transforma isso em <link rel="canonical">, Open Graph, Twitter Card
e JSON-LD. Endereços absolutos usam SITE_URL, e não o Host da requisição, para que
o canônico seja sempre o domínio oficial do jornal.

O nome da escola nunca entra aqui: quem publica é o jornal (site.name).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import SafeString, mark_safe

from .site_settings import get_setting

SCHEMA_CONTEXT = "https://schema.org"
DESCRIPTION_MAX = 160
DEFAULT_IMAGE = ("img/og-default.png", 1200, 630)
LOGO_IMAGE = ("img/logo.png", 512, 512)

# JSON dentro de <script>: sem "<", ">" e "&" literais, nada fecha a tag antes da hora.
_SCRIPT_ESCAPES = {ord("<"): "\\u003c", ord(">"): "\\u003e", ord("&"): "\\u0026"}


def site_root() -> str:
    return settings.SITE_URL.rstrip("/")


def absolute_url(url: str) -> str:
    """/publicacoes/x/ → https://jornal.exemplo/publicacoes/x/ (endereço completo fica igual)."""
    if not url or url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return f"{settings.SITE_URL.split('://', 1)[0]}:{url}"
    return f"{site_root()}/{url.lstrip('/')}"


def listing_path(request) -> str:
    """Canônico de listas: o próprio endereço, só com ?pagina=N (filtros apontam para a base)."""
    page = request.GET.get("pagina", "")
    if page.isdigit() and int(page) > 1:
        return f"{request.path}?pagina={int(page)}"
    return request.path


def shorten(text: str, limit: int = DESCRIPTION_MAX) -> str:
    """Texto numa linha, cortado na última palavra inteira antes do limite."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def json_ld_script(data: dict[str, Any] | list[dict[str, Any]]) -> SafeString:
    """Conteúdo pronto para <script type="application/ld+json">."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return mark_safe(text.translate(_SCRIPT_ESCAPES))  # "<", ">" e "&" já escapados


def iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


@dataclass
class OgImage:
    url: str  # absoluto
    width: int | None = None
    height: int | None = None
    alt: str = ""


def default_image() -> OgImage:
    path, width, height = DEFAULT_IMAGE
    return OgImage(url=absolute_url(static(path)), width=width, height=height)


def organization() -> dict[str, Any]:
    """Quem publica: o próprio jornal, com o nome configurado no admin."""
    path, width, height = LOGO_IMAGE
    return {
        "@type": "NewsMediaOrganization",
        "name": get_setting("site.name"),
        "url": f"{site_root()}/",
        "logo": {
            "@type": "ImageObject",
            "url": absolute_url(static(path)),
            "width": width,
            "height": height,
        },
    }


def website() -> dict[str, Any]:
    """JSON-LD da home. O SearchAction entra quando existir a busca (/busca/, Fase 3)."""
    return {
        "@context": SCHEMA_CONTEXT,
        "@type": "WebSite",
        "name": get_setting("site.name"),
        "url": f"{site_root()}/",
        "description": home_description(),
        "inLanguage": "pt-BR",
        "publisher": organization(),
    }


def home_description() -> str:
    return shorten(get_setting("site.description") or get_setting("site.tagline"))


@dataclass
class PageMeta:
    """O que buscadores e redes sociais leem de uma página."""

    title: str
    description: str = ""
    path: str = ""  # endereço canônico (sem domínio); vazio = sem canônico
    image: OgImage | None = None
    og_type: str = "website"
    noindex: bool = False
    published_time: datetime | None = None
    modified_time: datetime | None = None
    json_ld: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.description = shorten(self.description) or shorten(get_setting("site.tagline"))
        if self.image is None:
            self.image = default_image()

    @property
    def canonical(self) -> str:
        return absolute_url(self.path) if self.path and not self.noindex else ""

    @property
    def site_name(self) -> str:
        return get_setting("site.name")

    @property
    def published_iso(self) -> str:
        return iso(self.published_time)

    @property
    def modified_iso(self) -> str:
        return iso(self.modified_time)

    @property
    def json_ld_scripts(self) -> list[SafeString]:
        return [] if self.noindex else [json_ld_script(item) for item in self.json_ld]


def robots_txt() -> str:
    """Áreas internas ficam fora; o resto é público e aponta o sitemap."""
    disallow = [
        "/painel/",
        "/admin/",
        "/entrar/",
        "/sair/",
        "/acesso/",
        "/x/",
        "/dev/",
        "/publicacoes/previa/",
    ]
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in disallow), ""]
    lines.append(f"Sitemap: {site_root()}/sitemap.xml")
    return "\n".join(lines) + "\n"
