"""Internet de mentira para a coleta de notícias: nenhum teste acessa a rede."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from apps.curation import services
from apps.curation.models import NewsSource

FEEDS = Path(__file__).parent / "feeds"


def feed(name: str) -> bytes:
    return (FEEDS / name).read_bytes()


class FakeWeb:
    """Responde por endereço exato (sem o fragmento). Cada rota é uma resposta pronta ou uma
    função que recebe o pedido; endereço sem rota responde 404. Guarda os pedidos feitos."""

    def __init__(self) -> None:
        self.routes: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def add(self, url: str, body: bytes = b"", status: int = 200, **headers: str) -> None:
        self.routes[url] = httpx.Response(status, content=body, headers=headers)

    def redirect(self, url: str, to: str) -> None:
        self.routes[url] = httpx.Response(301, headers={"Location": to})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes.get(str(request.url.copy_with(fragment=None)))
        if route is None:
            return httpx.Response(404)
        if callable(route):
            return route(request)
        return httpx.Response(route.status_code, headers=route.headers, content=route.content)

    def gets(self) -> list[str]:
        return [str(r.url) for r in self.requests if r.method == "GET"]

    def heads(self) -> list[str]:
        return [str(r.url) for r in self.requests if r.method == "HEAD"]


@pytest.fixture
def web(monkeypatch) -> FakeWeb:
    fake = FakeWeb()
    monkeypatch.setattr(services, "TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
def make_source(db):
    def make(feed_url: str = "https://ciencia.exemplo.org/feed/", **fields) -> NewsSource:
        fields.setdefault("name", "Ciência Exemplo")
        return NewsSource.objects.create(feed_url=feed_url, **fields)

    return make
