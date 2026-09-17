"""Feed RSS 2.0 das publicações em /feed/ (docs/11, E43).

As 20 publicações mais recentes no ar, para leitores de feed. Endereços absolutos usam
SITE_URL (e não o domínio do framework "sites", que o allauth deixa como example.com).
Quem publica é o jornal (site.name); o nome da escola nunca entra aqui.
"""

from django.contrib.syndication.views import Feed
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed
from django.views.decorators.http import require_GET

from apps.core import seo
from apps.core.site_settings import get_setting

from . import listing, presentation, selectors
from .models import Article

FEED_ITEMS = 20
DESCRIPTION_MAX = 300


class LatestArticlesFeed(Feed):
    feed_type = Rss201rev2Feed

    def title(self) -> str:
        return get_setting("site.name")

    def description(self) -> str:
        return get_setting("site.tagline") or f"Publicações do {get_setting('site.name')}."

    def link(self) -> str:
        return seo.absolute_url(reverse("core:home"))

    def feed_url(self) -> str:
        return seo.absolute_url(reverse("publications:feed"))

    def items(self) -> list[Article]:
        return list(selectors.for_cards(selectors.published())[:FEED_ITEMS])

    def item_title(self, item: Article) -> str:
        return item.title

    def item_description(self, item: Article) -> str:
        return item.subtitle or seo.shorten(item.body_text, DESCRIPTION_MAX)

    def item_link(self, item: Article) -> str:
        return seo.absolute_url(item.get_absolute_url())

    def item_pubdate(self, item: Article):
        return item.published_at

    def item_updateddate(self, item: Article):
        return item.updated_at

    def item_author_name(self, item: Article) -> str:
        # Mesmo nome que a página mostra (crédito de aluno anonimizado já vem trocado).
        return presentation.byline(item)

    def item_categories(self, item: Article) -> list[str]:
        names = [d.name for d in item.disciplines.all()]
        if item.type_id:
            names.append(item.type.name)
        return names


@require_GET
def latest(request: HttpRequest) -> HttpResponse:
    """Feed em cache por 60s com a versão do conteúdo público: publicar invalida."""
    content = listing.cached("feed|rss", lambda: LatestArticlesFeed()(request).content)
    return HttpResponse(content, content_type="application/rss+xml; charset=utf-8")
