"""Coleta de notícias dos feeds (docs/21, "Pipeline de coleta" e "Higiene").

fetch_source(fonte) baixa o feed com ETag/Last-Modified, lê com feedparser, normaliza cada item
(normalize.py) e grava só os que ainda não existem (url_hash único). Erros de uma fonte ficam
registrados nela (último erro, falhas seguidas) e nunca derrubam a coleta das outras.

Deduplicação por título e retenção de 60 dias são da E46; classificação, da E47.

Segurança (docs/23): só http e https, tempo limite, feed de no máximo 5 MB, no máximo
5 redirecionamentos e nenhum pedido para endereços de rede interna (protege o servidor se alguém
cadastrar, por engano ou de propósito, um endereço como http://localhost).
"""

import ipaddress
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.site_settings import get_setting

from . import normalize
from .models import NewsItem, NewsSource
from .seed_data import SOURCES

logger = logging.getLogger(__name__)

FEED_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEAD_TIMEOUT = httpx.Timeout(5.0)
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
# Itens lidos por coleta (os primeiros do feed, que costumam ser os mais novos).
MAX_ITEMS_PER_FETCH = 50
# Pedidos HEAD simultâneos para descobrir o endereço final dos links novos.
HEAD_WORKERS = 8
FEED_ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.5"
)

# Os testes trocam por um httpx.MockTransport: nenhum teste acessa a rede.
TRANSPORT: httpx.BaseTransport | None = None


class FetchError(Exception):
    """Falha esperada de uma coleta; a mensagem aparece para o admin."""


@dataclass
class FetchResult:
    source: NewsSource
    new: int = 0
    known: int = 0
    skipped: int = 0
    not_modified: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def describe(self) -> str:
        if self.error:
            return f"{self.source.name}: erro — {self.error}"
        if self.not_modified:
            return f"{self.source.name}: nada mudou desde a última coleta"
        return f"{self.source.name}: {self.new} nova(s), {self.known} já conhecida(s)"


def user_agent() -> str:
    """Identifica o jornal e um contato (docs/21, "Higiene"), sem o nome da escola."""
    contact = get_setting("site.contact_email")
    return f"JornalEscolar/{settings.APP_VERSION} (+{settings.SITE_URL}; {contact})"


def _block_internal_hosts(request: httpx.Request) -> None:
    """Recusa pedidos (inclusive redirecionamentos) para endereços fora da internet pública."""
    if not settings.CURATION_BLOCK_PRIVATE_HOSTS:
        return
    host = request.url.host
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return  # o próprio httpx informa que não achou o endereço
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not address.is_global:
            raise FetchError(f"Endereço de rede interna não permitido ({host}).")


def build_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent()},
        timeout=FEED_TIMEOUT,
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        event_hooks={"request": [_block_internal_hosts]},
        transport=TRANSPORT,
    )


def _http_error(exc: httpx.HTTPError) -> FetchError:
    if isinstance(exc, httpx.TimeoutException):
        return FetchError("Tempo esgotado ao buscar o feed.")
    if isinstance(exc, httpx.TooManyRedirects):
        return FetchError("Redirecionamentos demais.")
    return FetchError(f"Não foi possível acessar o feed ({exc.__class__.__name__}: {exc}).")


def download_feed(client: httpx.Client, source: NewsSource) -> tuple[bytes | None, httpx.Headers]:
    """Corpo do feed, ou None quando o site responde 304 (nada mudou)."""
    if not normalize.is_web_url(source.feed_url):
        raise FetchError("O endereço do feed precisa começar com http:// ou https://.")
    headers = {"Accept": FEED_ACCEPT}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    try:
        with client.stream("GET", source.feed_url, headers=headers) as response:
            if response.status_code == 304:
                return None, response.headers
            if response.status_code >= 400:
                raise FetchError(f"O site respondeu com o código {response.status_code}.")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_FEED_BYTES:
                    raise FetchError("O feed passou do limite de 5 MB.")
                chunks.append(chunk)
            return b"".join(chunks), response.headers
    except httpx.HTTPError as exc:
        raise _http_error(exc) from exc


def parse_feed(body: bytes, headers: httpx.Headers | None = None) -> feedparser.FeedParserDict:
    response_headers = {}
    if headers and headers.get("content-type"):
        response_headers["content-type"] = headers["content-type"]
    parsed = feedparser.parse(body, response_headers=response_headers)
    if not parsed.entries and (parsed.bozo or not parsed.version):
        reason = parsed.get("bozo_exception") or "nenhuma notícia encontrada"
        raise FetchError(f"O conteúdo não é um feed RSS ou Atom válido ({reason}).")
    return parsed


def resolve_url(client: httpx.Client, url: str) -> str:
    """Endereço final do link, seguindo redirecionamentos com HEAD. Se o site recusar o HEAD ou
    falhar, fica o link do feed."""
    try:
        response = client.head(url, timeout=HEAD_TIMEOUT)
    except (httpx.HTTPError, FetchError):
        return url
    if response.status_code >= 400:
        return url
    final = str(response.url)
    return final if normalize.is_web_url(final) and len(final) <= 1000 else url


@dataclass
class _Candidate:
    link: str
    title: str
    entry: dict


def _store_entries(
    client: httpx.Client, source: NewsSource, parsed: feedparser.FeedParserDict, now: datetime
) -> tuple[int, int, int]:
    """Grava os itens novos. Devolve (novos, já conhecidos, ignorados por falta de título/link)."""
    outlet_names = (source.name, parsed.feed.get("title", ""))
    candidates: list[_Candidate] = []
    skipped = 0
    for entry in parsed.entries[:MAX_ITEMS_PER_FETCH]:
        link = (entry.get("link") or "").strip()
        title = normalize.clean_title(entry.get("title", ""), outlet_names)[:300].strip()
        if not title or not normalize.is_web_url(link) or len(link) > 1000:
            skipped += 1
            continue
        candidates.append(_Candidate(link, title, entry))

    # Já conhecidos pelo link do feed ou pelo link limpo: não precisam do HEAD.
    cleaned = {c.link: normalize.canonicalize_url(c.link) for c in candidates}
    known_links = set(NewsItem.objects.filter(url__in=list(cleaned)).values_list("url", flat=True))
    known_hashes = set(
        NewsItem.objects.filter(
            url_hash__in=[normalize.url_hash(url) for url in cleaned.values()]
        ).values_list("url_hash", flat=True)
    )
    pending = [
        c
        for c in candidates
        if c.link not in known_links and normalize.url_hash(cleaned[c.link]) not in known_hashes
    ]
    known = len(candidates) - len(pending)

    links = list(dict.fromkeys(c.link for c in pending))
    with ThreadPoolExecutor(max_workers=HEAD_WORKERS) as pool:
        finals = dict(
            zip(links, pool.map(lambda url: resolve_url(client, url), links), strict=True)
        )

    new = 0
    seen: set[str] = set()
    for candidate in pending:
        canonical = normalize.canonicalize_url(finals[candidate.link])
        if len(canonical) > 1000:
            canonical = cleaned[candidate.link]
        digest = normalize.url_hash(canonical)
        if digest in seen:
            known += 1
            continue
        seen.add(digest)
        entry = candidate.entry
        defaults = {
            "source": source,
            "title": candidate.title,
            "url": candidate.link,
            "canonical_url": canonical,
            "title_hash": normalize.title_hash(candidate.title),
            "summary": normalize.clean_summary(entry.get("summary", "")),
            "image_url": normalize.entry_image_url(entry),
            "published_at": normalize.entry_datetime(entry, now),
            "fetched_at": now,
            "language": source.language,
        }
        try:
            with transaction.atomic():
                _, created = NewsItem.objects.get_or_create(url_hash=digest, defaults=defaults)
        except IntegrityError:
            created = False
        if created:
            new += 1
        else:
            known += 1
    return new, known, skipped


def _record(
    source: NewsSource, result: FetchResult, now: datetime, headers: httpx.Headers | None
) -> None:
    source.last_fetched_at = now
    fields = ["last_fetched_at", "updated_at"]
    if result.ok:
        source.last_success_at = now
        source.consecutive_failures = 0
        source.last_error = ""
        fields += ["last_success_at", "consecutive_failures", "last_error"]
        if headers is not None:
            source.etag = headers.get("etag", "")[:300]
            source.last_modified = headers.get("last-modified", "")[:100]
            fields += ["etag", "last_modified"]
    else:
        source.consecutive_failures += 1
        source.last_error = result.error
        source.last_error_at = now
        fields += ["consecutive_failures", "last_error", "last_error_at"]
    source.save(update_fields=fields)


def fetch_source(source: NewsSource, client: httpx.Client | None = None) -> FetchResult:
    """Coleta uma fonte e registra o resultado nela. Não levanta erro de rede nem de feed."""
    now = timezone.now()
    result = FetchResult(source)
    headers: httpx.Headers | None = None
    own_client = client is None
    client = client or build_client()
    try:
        body, headers = download_feed(client, source)
        if body is None:
            result.not_modified = True
        else:
            parsed = parse_feed(body, headers)
            result.new, result.known, result.skipped = _store_entries(client, source, parsed, now)
    except FetchError as exc:
        result.error = str(exc)
    except Exception:
        logger.exception("Erro inesperado ao coletar a fonte %s", source.pk)
        result.error = "Erro inesperado ao processar o feed (detalhes no log do servidor)."
    finally:
        if own_client:
            client.close()
    _record(source, result, now, headers)
    logger.info("Coleta: %s", result.describe())
    return result


def due_sources(now: datetime | None = None) -> list[NewsSource]:
    """Fontes ativas cujo intervalo entre coletas já passou."""
    now = now or timezone.now()
    active = NewsSource.objects.filter(is_active=True, kind=NewsSource.Kind.RSS)
    return [source for source in active if source.is_due(now)]


def fetch_sources(sources: list[NewsSource]) -> list[FetchResult]:
    with build_client() as client:
        return [fetch_source(source, client) for source in sources]


@dataclass
class SeedResult:
    created: int
    existing: int


def seed_sources() -> SeedResult:
    """Cadastra as fontes sugeridas em docs/21. Não mexe nas que já existem (pelo feed)."""
    created = 0
    for data in SOURCES:
        defaults = {key: value for key, value in data.items() if key != "feed_url"}
        _, was_created = NewsSource.objects.get_or_create(
            feed_url=data["feed_url"], defaults=defaults
        )
        created += was_created
    return SeedResult(created=created, existing=len(SOURCES) - created)
