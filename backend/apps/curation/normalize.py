"""Normalização dos itens de feed (docs/21, "Normalização"): funções puras, sem rede nem banco.

- Título: sem HTML, espaços colapsados, sem o sufixo " - Nome do veículo".
- Resumo: sem HTML, até 600 caracteres terminando na última frase completa.
- URL canônica: esquema e host em minúsculas, sem porta padrão, sem fragmento e sem parâmetros
  de rastreamento (utm_*, fbclid, gclid...).
- url_hash: SHA-256 da URL canônica sem o esquema e sem "www.", para http e https do mesmo
  endereço contarem como a mesma notícia.
- title_hash: SHA-256 do título em minúsculas, sem acentos e sem pontuação.
- Título marcante: com pelo menos 4 palavras. Só esses entram na deduplicação por título, porque
  títulos curtos ("Editorial", "Podcast da semana") se repetem sem ser a mesma notícia.
"""

import hashlib
import html
import re
import time
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import nh3

from .models import SUMMARY_MAX_LENGTH

TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "gbraid",
        "wbraid",
        "msclkid",
        "yclid",
        "twclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "_ga",
        "_gl",
        "__twitter_impression",
        "xtor",
        "at_medium",
        "at_campaign",
        "ocid",
        "cmpid",
    }
)
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_")
DEFAULT_PORTS = {"http": 80, "https": 443}

_BLOCK_TAGS = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/blockquote|/tr)\b[^>]*>", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
_ENTITY = re.compile(r"&#?\w+;")
# Marcação que o nh3 não reconhece como tag (ex.: "<_cdata>" de feeds mal gerados).
_LEFTOVER_TAG = re.compile(r"</?_?[a-zA-Z][\w:.-]*(?:\s[^<>]*)?/?>")
_SENTENCE_END = re.compile(r"[.!?…](?:[\"'”’)\]])?(?=\s|$)")  # noqa: RUF001
# Rodapé que o WordPress põe no resumo ("O post X apareceu primeiro em Y."), em qualquer posição,
# e o "[…]" do fim.
_WORDPRESS_NOTE = re.compile(
    r"(?:The post|O post) .{1,300}? (?:appeared first on|apareceu primeiro em) [^.]{1,100}\.",
    re.IGNORECASE,
)
_READ_MORE = re.compile(r"\s*\[(?:…|\.\.\.)\]\s*$")
_TITLE_SEPARATORS = (" - ", " – ", " — ", " | ")  # noqa: RUF001 (hífen, meia-risca, travessão)
_PUNCTUATION = re.compile(r"[^\w\s]")
TITLE_DEDUP_MIN_WORDS = 4


def strip_html(value: str) -> str:
    """Texto puro: tags removidas (conteúdo de script e style some), entidades decodificadas e
    espaços colapsados."""
    if not value:
        return ""
    # Duas passadas: há feeds com o HTML escapado duas vezes ("&lt;p&gt;" dentro do CDATA).
    for _ in range(2):
        value = _BLOCK_TAGS.sub(" ", value)
        value = html.unescape(nh3.clean(value, tags=set(), clean_content_tags={"script", "style"}))
        value = _LEFTOVER_TAG.sub(" ", value)
        if "<" not in value and not _ENTITY.search(value):
            break
    return _SPACES.sub(" ", value).strip()


def fold(value: str) -> str:
    """Minúsculas e sem acentos, para comparar textos."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def clean_title(raw: str, outlet_names: tuple[str, ...] = ()) -> str:
    title = strip_html(raw)
    names = {fold(name).strip() for name in outlet_names if name and name.strip()}
    for separator in _TITLE_SEPARATORS:
        head, sep, tail = title.rpartition(separator)
        if sep and head.strip() and fold(tail).strip() in names:
            title = head.strip()
            break
    return title


def clean_summary(raw: str, limit: int = SUMMARY_MAX_LENGTH) -> str:
    text = _READ_MORE.sub("", _WORDPRESS_NOTE.sub("", strip_html(raw))).strip()
    text = _SPACES.sub(" ", text)
    if len(text) <= limit:
        return text
    window = text[:limit]
    ends = [match.end() for match in _SENTENCE_END.finditer(window)]
    if ends and ends[-1] >= limit // 3:
        return window[: ends[-1]].strip()
    cut = window[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-–—")  # noqa: RUF001
    return f"{cut}…"


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if ":" in host:  # IPv6
        host = f"[{host}]"
    netloc = host
    if parts.port and parts.port != DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{parts.port}"
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def url_hash(canonical_url: str) -> str:
    parts = urlsplit(canonical_url)
    netloc = parts.netloc.removeprefix("www.")
    key = urlunsplit(("", netloc, parts.path, parts.query, "")).removeprefix("//")
    return hashlib.sha256(key.encode()).hexdigest()


def title_key(title: str) -> str:
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", fold(title))).strip()


def title_hash(title: str) -> str:
    return hashlib.sha256(title_key(title).encode()).hexdigest()


def is_distinctive_title(title: str) -> bool:
    return len(title_key(title).split()) >= TITLE_DEDUP_MIN_WORDS


def is_web_url(url: str) -> bool:
    parts = urlsplit(url or "")
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def entry_datetime(entry: dict, fallback: datetime) -> datetime:
    """Data de publicação, senão de atualização, senão a hora da coleta. Datas no futuro (feeds
    com fuso errado) viram a hora da coleta."""
    for key in ("published_parsed", "updated_parsed"):
        parsed: time.struct_time | None = entry.get(key)
        if parsed:
            try:
                moment = datetime(*parsed[:6], tzinfo=UTC)
            except (TypeError, ValueError):
                continue
            return min(moment, fallback)
    return fallback


def entry_image_url(entry: dict) -> str:
    """Endereço da imagem do item, se o feed informar. A imagem nunca é baixada."""
    candidates: list[str] = []
    candidates += [media.get("url", "") for media in entry.get("media_thumbnail") or []]
    candidates += [
        media.get("url", "")
        for media in entry.get("media_content") or []
        if media.get("medium") == "image" or str(media.get("type", "")).startswith("image/")
    ]
    candidates += [
        link.get("href", "")
        for link in entry.get("links") or []
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image/")
    ]
    for candidate in candidates:
        if is_web_url(candidate) and len(candidate) <= 1000:
            return candidate
    return ""
