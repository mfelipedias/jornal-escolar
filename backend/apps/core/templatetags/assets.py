"""Tags dos arquivos gerados pelo Vite (docs/09, "Carregamento sem salto"). {% load assets %}."""

from functools import cache
from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html_join

register = template.Library()

# Fontes que a primeira tela usa: títulos e interface (Bricolage) e corpo de leitura
# (Newsreader), alfabeto latino. Itálico, outros alfabetos e eixos chegam depois pelo CSS.
PRELOAD_FONTS = ("bricolage-grotesque-latin-opsz-normal", "newsreader-latin-opsz-normal")


def dist_dir() -> Path:
    return Path(settings.DJANGO_VITE["default"]["manifest_path"]).parent


@cache
def _font_files() -> tuple[str, ...]:
    """Caminhos (relativos a static/) das fontes do build, com o hash que o Vite pôs no nome."""
    found: list[Path] = []
    for name in PRELOAD_FONTS:
        found.extend(sorted((dist_dir() / "assets").glob(f"{name}-*.woff2")))
    return tuple(f"dist/assets/{path.name}" for path in found)


@register.simple_tag
def font_preloads() -> str:
    """<link rel="preload"> das fontes principais. Só com o build; em dev o Vite serve tudo."""
    if settings.DJANGO_VITE["default"]["dev_mode"]:
        return ""
    return format_html_join(
        "\n",
        '<link rel="preload" href="{}" as="font" type="font/woff2" crossorigin>',
        ((static(path),) for path in _font_files()),
    )


@register.simple_tag
def stylesheet_url_or_empty(path: str = "src/css/app.css") -> str:
    """URL do CSS do Vite, ou "" se o manifest falhar. Usada só pela página 500, que precisa
    renderizar mesmo quando o próprio erro veio de arquivos do build."""
    from django_vite.templatetags.django_vite import vite_asset_url

    try:
        return vite_asset_url(path)
    except Exception:
        return ""
