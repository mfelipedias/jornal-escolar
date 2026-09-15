"""Gera os arquivos de marca em backend/static/ a partir da geometria do glifo (docs/09, R1).

Uso, na raiz do repositório:  uv run --directory backend python ../scripts/brand.py

Saída: img/favicon.ico (32), img/apple-touch-icon.png (180), img/icon-192.png, img/icon-512.png,
img/logo.png (512, quadrado, para JSON-LD), img/og-default.png (1200x630, imagem padrão de
compartilhamento) e manifest.json. O favicon.svg e o components/glyph.html usam a mesma
geometria, escrita à mão; ao mudar o desenho, mudar nos três lugares.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "backend" / "static"
IMG = STATIC / "img"

ACCENT = "#c41260"
PAPER = "#fffdf7"
SUN = "#ffd23f"
WHITE = "#ffffff"

# Geometria do glifo no viewBox 0..32 (mesma de components/glyph.html).
OUTLINE = [(29, 4), (3, 15.5), (12.5, 19.5), (15, 28.5), (29, 4)]
FOLD = [(29, 4), (12.5, 19.5)]
LINES = [[(9.5, 13.6), (16, 10.8)], [(12.5, 16.2), (17, 14.2)]]
SUPERSAMPLE = 4


def draw_glyph(draw: ImageDraw.ImageDraw, origin: tuple[float, float], scale: float, color: str):
    """Desenha o avião com traço proporcional (2 unidades do viewBox), cantos redondos."""
    ox, oy = origin
    width = max(1, round(2 * scale))

    def pt(p):
        return (ox + p[0] * scale, oy + p[1] * scale)

    for poly in (OUTLINE, FOLD, *LINES):
        points = [pt(p) for p in poly]
        stroke = round(width * 0.75) if poly in LINES else width  # "texto" da asa mais fino
        draw.line(points, fill=color, width=stroke, joint="curve")
        radius = stroke / 2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def icon(size: int, *, radius_ratio: float = 14 / 64, padded: bool = True) -> Image.Image:
    """Quadrado arredondado no acento com o glifo branco (mesmo desenho do favicon.svg)."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * radius_ratio, fill=ACCENT)
    # No favicon.svg: translate(8 8) scale(1.5) num viewBox de 64.
    scale = big / 64 * 1.5
    origin = (big / 64 * 8, big / 64 * 8)
    draw_glyph(draw, origin, scale, WHITE)
    return image.resize((size, size), Image.LANCZOS)


def og_image() -> Image.Image:
    """1200x630: papel, glifo grande no acento e um traço de marca-texto embaixo."""
    w, h = 1200, 630
    big = (w * SUPERSAMPLE, h * SUPERSAMPLE)
    image = Image.new("RGB", big, PAPER)
    draw = ImageDraw.Draw(image)
    scale = 9 * SUPERSAMPLE
    glyph_w, glyph_h = 26 * scale, 24.5 * scale
    origin = ((big[0] - glyph_w) / 2 - 3 * scale, (big[1] - glyph_h) / 2 - 4 * scale)
    # Marca-texto inclinado atrás do avião.
    bar_h = 3.2 * scale
    bar = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(bar).rounded_rectangle(
        (origin[0] + 4 * scale, origin[1] + 22 * scale, origin[0] + 30 * scale, origin[1] + 22 * scale + bar_h),
        radius=bar_h / 4,
        fill=SUN,
    )
    rotated = bar.rotate(-2, resample=Image.BICUBIC, center=(big[0] / 2, big[1] / 2))
    image.paste(rotated, (0, 0), rotated)
    draw_glyph(draw, origin, scale, ACCENT)
    draw.rectangle((0, big[1] - 10 * SUPERSAMPLE, big[0], big[1]), fill=ACCENT)
    return image.resize((w, h), Image.LANCZOS)


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    icon(32).save(IMG / "favicon.ico", sizes=[(32, 32)])
    icon(180).save(IMG / "apple-touch-icon.png", optimize=True)
    icon(192).save(IMG / "icon-192.png", optimize=True)
    icon(512).save(IMG / "icon-512.png", optimize=True)
    icon(512).save(IMG / "logo.png", optimize=True)
    og_image().save(IMG / "og-default.png", optimize=True)
    manifest = {
        "name": "Jornal Escolar",
        "short_name": "Jornal",
        "description": "Jornal digital da comunidade escolar",
        "start_url": "/",
        "display": "browser",
        "lang": "pt-BR",
        "background_color": PAPER,
        "theme_color": PAPER,
        "icons": [
            {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/img/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    (STATIC / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("marca gerada em", IMG)


if __name__ == "__main__":
    main()
