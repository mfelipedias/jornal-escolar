"""Renderizador do corpo das publicações: documento do editor (JSON ProseMirror) → HTML e texto.

Decisão D4 (docs/05) e docs/16 "Renderizador servidor". O HTML nunca vem do navegador:
1. normalize() mantém só nós, marcas e atributos conhecidos; o resto é descartado.
2. to_html() emite HTML a partir do documento limpo, escapando todo texto.
3. nh3 limpa o resultado com lista fechada de tags e atributos (segunda barreira).

Precisa ficar em sincronia com as extensões habilitadas no editor (E14).
"""

import html
import logging
import math
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import nh3

from .models import MediaAsset

logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 200
MAX_DEPTH = 40

BLOCK_NODES = {
    "paragraph",
    "heading",
    "bulletList",
    "orderedList",
    "listItem",
    "blockquote",
    "horizontalRule",
    "figure",
}
INLINE_NODES = {"text", "hardBreak"}
MARKS = {"bold", "italic", "link"}
FIGURE_SIZES = {"normal", "wide"}
IMAGE_SIZES = {
    "normal": "(min-width: 768px) 700px, 100vw",
    "wide": "(min-width: 1280px) 1200px, 100vw",
}

ALLOWED_TAGS = {
    "p", "h2", "h3", "strong", "em", "a", "ul", "ol", "li", "blockquote", "cite",
    "hr", "br", "figure", "img", "figcaption", "span",
}  # fmt: skip
ALLOWED_ATTRIBUTES = {
    "a": {"href", "rel", "target"},
    "ol": {"start"},
    "figure": {"class"},
    "img": {"src", "srcset", "sizes", "alt", "width", "height", "loading", "decoding"},
    "span": {"class"},
}


@dataclass
class RenderResult:
    document: dict
    html: str
    text: str
    words: int
    reading_minutes: int
    asset_ids: set[int] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        """Sem texto e sem imagem válida: a checklist bloqueia (docs/04)."""
        return not self.text.strip() and not self.asset_ids


# --- 1. limpeza do documento ---


def safe_href(value: Any, *, allow_relative: bool = True) -> str | None:
    """Aceita http(s), mailto e caminhos internos. Recusa javascript:, data:, etc."""
    if not isinstance(value, str):
        return None
    href = value.strip()
    if not href or any(ch in href for ch in "\x00\n\r\t"):
        return None
    if allow_relative and href.startswith("/") and not href.startswith("//"):
        return href
    if allow_relative and href.startswith("#"):
        return href
    parts = urlsplit(href)
    if parts.scheme.lower() in ("http", "https") and parts.netloc:
        return href
    if parts.scheme.lower() == "mailto" and "@" in parts.path:
        return href
    return None


def _clean_marks(marks: Any) -> list[dict]:
    cleaned: list[dict] = []
    for mark in marks if isinstance(marks, list) else []:
        if not isinstance(mark, dict) or mark.get("type") not in MARKS:
            continue
        if mark["type"] == "link":
            href = safe_href((mark.get("attrs") or {}).get("href"))
            if href is None:
                continue  # link perigoso ou inválido: fica só o texto
            cleaned.append({"type": "link", "attrs": {"href": href}})
        elif all(m["type"] != mark["type"] for m in cleaned):
            cleaned.append({"type": mark["type"]})
    return cleaned


def _clean_str(value: Any, limit: int) -> str:
    return " ".join(str(value).split())[:limit] if isinstance(value, str | int | float) else ""


def _normalize_node(node: Any, depth: int, allowed_assets: set[int] | None) -> dict | None:
    if not isinstance(node, dict):
        return None
    kind = node.get("type")
    if depth > MAX_DEPTH:
        logger.warning("Documento aninhado demais; conteúdo descartado.")
        return None
    attrs = node.get("attrs") if isinstance(node.get("attrs"), dict) else {}

    if kind == "text":
        text = node.get("text")
        if not isinstance(text, str) or not text:
            return None
        result: dict = {"type": "text", "text": text}
        marks = _clean_marks(node.get("marks"))
        if marks:
            result["marks"] = marks
        return result
    if kind in ("hardBreak", "horizontalRule"):
        return {"type": kind}
    if kind == "figure":
        try:
            asset_id = int(attrs.get("assetId"))
        except (TypeError, ValueError):
            return None
        if allowed_assets is not None and asset_id not in allowed_assets:
            return None
        size = attrs.get("size") if attrs.get("size") in FIGURE_SIZES else "normal"
        return {
            "type": "figure",
            "attrs": {
                "assetId": asset_id,
                "alt": _clean_str(attrs.get("alt", ""), 250),
                "caption": _clean_str(attrs.get("caption", ""), 300),
                "credit": _clean_str(attrs.get("credit", ""), 120),
                "size": size,
            },
        }
    if kind not in {"doc", *BLOCK_NODES}:
        logger.warning("Nó desconhecido ignorado no documento: %r", kind)
        return None

    raw_children = node.get("content") if isinstance(node.get("content"), list) else []
    children = [
        child
        for child in (_normalize_node(c, depth + 1, allowed_assets) for c in raw_children)
        if child is not None
    ]
    result = {"type": kind}
    if kind == "heading":
        level = attrs.get("level")
        result["attrs"] = {"level": 3 if level in (3, 4, 5, 6) else 2}
    elif kind == "orderedList":
        start = attrs.get("start")
        if isinstance(start, int) and start > 1:
            result["attrs"] = {"start": start}
    elif kind == "blockquote":
        cite = _clean_str(attrs.get("cite", ""), 120)
        if cite:
            result["attrs"] = {"cite": cite}
    if children:
        result["content"] = children
    return result


def normalize(document: Any, allowed_assets: set[int] | None = None) -> dict:
    """Documento limpo, com raiz "doc". Entrada inválida vira documento vazio.

    Com allowed_assets, figuras que apontam para outras imagens são removidas.
    """
    if not isinstance(document, dict) or document.get("type") != "doc":
        return {"type": "doc", "content": []}
    cleaned = _normalize_node(document, 0, allowed_assets) or {"type": "doc"}
    cleaned.setdefault("content", [])
    return cleaned


def collect_asset_ids(document: dict) -> set[int]:
    ids: set[int] = set()
    stack = [document]
    while stack:
        node = stack.pop()
        if node.get("type") == "figure":
            ids.add(node["attrs"]["assetId"])
        stack.extend(node.get("content", []))
    return ids


# --- 2. HTML e texto ---


def _attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


class _Renderer:
    def __init__(self, assets: dict[int, MediaAsset]) -> None:
        self.assets = assets
        self.used_assets: set[int] = set()
        self.text_blocks: list[str] = []

    def children(self, node: dict) -> str:
        return "".join(self.node(child) for child in node.get("content", []))

    def inline_text(self, node: dict) -> str:
        parts: list[str] = []
        for child in node.get("content", []):
            if child["type"] == "text":
                parts.append(child["text"])
            elif child["type"] == "hardBreak":
                parts.append("\n")
            else:
                parts.append(self.inline_text(child))
        return "".join(parts)

    def node(self, node: dict) -> str:
        kind = node["type"]
        if kind == "doc":
            return self.children(node)
        if kind == "text":
            return self.text(node)
        if kind == "hardBreak":
            return "<br>"
        if kind == "horizontalRule":
            return "<hr>"
        if kind == "paragraph":
            self.text_blocks.append(self.inline_text(node))
            return f"<p>{self.children(node)}</p>" if node.get("content") else ""
        if kind == "heading":
            level = node["attrs"]["level"]
            self.text_blocks.append(self.inline_text(node))
            return f"<h{level}>{self.children(node)}</h{level}>" if node.get("content") else ""
        if kind in ("bulletList", "orderedList"):
            tag = "ul" if kind == "bulletList" else "ol"
            start = (node.get("attrs") or {}).get("start")
            start_attr = f' start="{int(start)}"' if start else ""
            inner = self.children(node)
            return f"<{tag}{start_attr}>{inner}</{tag}>" if inner else ""
        if kind == "listItem":
            return f"<li>{self.children(node)}</li>"
        if kind == "blockquote":
            inner = self.children(node)
            cite = (node.get("attrs") or {}).get("cite")
            if cite:
                self.text_blocks.append(cite)
                inner += f"<p><cite>{html.escape(cite)}</cite></p>"
            return f"<blockquote>{inner}</blockquote>" if inner else ""
        if kind == "figure":
            return self.figure(node)
        return ""

    def text(self, node: dict) -> str:
        out = html.escape(node["text"]).replace("\n", "<br>")
        marks = node.get("marks", [])
        for mark in marks:
            if mark["type"] == "bold":
                out = f"<strong>{out}</strong>"
            elif mark["type"] == "italic":
                out = f"<em>{out}</em>"
        for mark in marks:
            if mark["type"] == "link":
                href = mark["attrs"]["href"]
                external = href.startswith(("http://", "https://"))
                extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
                out = f'<a href="{_attr(href)}"{extra}>{out}</a>'
        return out

    def figure(self, node: dict) -> str:
        attrs = node["attrs"]
        asset = self.assets.get(attrs["assetId"])
        if asset is None:
            return ""  # imagem sem MediaAsset válido não é renderizada (docs/16)
        self.used_assets.add(asset.pk)
        alt = "" if asset.is_decorative else (attrs["alt"] or asset.alt_text)
        caption = attrs["caption"]
        credit = attrs["credit"] or asset.credit
        size = attrs["size"]
        img = (
            f'<img src="{_attr(asset.variant_url("w960"))}" srcset="{_attr(asset.srcset)}" '
            f'sizes="{IMAGE_SIZES[size]}" alt="{_attr(alt)}" width="{asset.width}" '
            f'height="{asset.height}" loading="lazy" decoding="async">'
        )
        figcaption = ""
        if caption or credit:
            credit_html = (
                f'<span class="figure-credit">{html.escape(credit)}</span>' if credit else ""
            )
            figcaption = f"<figcaption>{html.escape(caption)}{credit_html}</figcaption>"
            self.text_blocks.append(" ".join(part for part in (caption, credit) if part))
        return f'<figure class="figure figure--{size}">{img}{figcaption}</figure>'


def sanitize(markup: str) -> str:
    return nh3.clean(
        markup,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel=None,
        strip_comments=True,
    )


def render(document: Any, allowed_assets: set[int] | None = None) -> RenderResult:
    clean = normalize(document, allowed_assets)
    ids = collect_asset_ids(clean)
    assets = MediaAsset.objects.in_bulk(ids) if ids else {}
    renderer = _Renderer(assets)
    markup = sanitize(renderer.node(clean))
    text = "\n\n".join(block.strip() for block in renderer.text_blocks if block.strip())
    words = len(text.split())
    return RenderResult(
        document=clean,
        html=markup,
        text=text,
        words=words,
        reading_minutes=max(1, math.ceil(words / WORDS_PER_MINUTE)),
        asset_ids=renderer.used_assets,
    )
