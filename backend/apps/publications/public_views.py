"""Páginas públicas das publicações (docs/11)."""

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.core import seo
from apps.core.site_settings import get_setting
from apps.editorial import permissions

from . import listing, presentation, selectors
from . import seo as article_seo
from .models import Article


def _render_article(request: HttpRequest, article: Article, *, preview: bool) -> HttpResponse:
    context = {
        "article": article,
        "preview": preview,
        "area": presentation.main_area(article),
        "byline": presentation.byline(article),
        "byline_people": presentation.byline_people(article),
        "credit_groups": presentation.credit_groups(article),
        "related": (
            [presentation.card(item) for item in selectors.related_articles(article)]
            if not preview
            else []
        ),
        "can_edit": permissions.can_edit(request.user, article),
        "share_url": seo.absolute_url(article.get_absolute_url()),
        "seo": article_seo.page_meta(article, preview=preview),
        "was_updated": bool(
            article.published_at
            and article.updated_at
            and (article.updated_at - article.published_at).total_seconds() > 3600
        ),
    }
    response = render(request, "publications/detail.html", context)
    if preview:
        response["X-Robots-Tag"] = "noindex"
        response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def article_list(request: HttpRequest) -> HttpResponse:
    """/publicacoes/: todas as publicações com filtros por área, disciplina e tipo (docs/12)."""
    meta = seo.PageMeta(
        title="Publicações",
        description=f"Todas as publicações do {get_setting('site.name')}.",
        path=seo.listing_path(request),
    )
    return listing.render_listing(
        request, "publications/list.html", listing.parse(request.GET), context={"seo": meta}
    )


AGENDA_PAST_PER_PAGE = 20


@require_GET
def agenda(request: HttpRequest) -> HttpResponse:
    """/agenda/: próximos eventos e os que já aconteceram (paginados)."""
    upcoming, past = selectors.agenda()
    past_page = Paginator(past, AGENDA_PAST_PER_PAGE).get_page(request.GET.get("pagina"))
    context = {
        "upcoming": [presentation.event(a) for a in upcoming] if past_page.number == 1 else [],
        "past": [presentation.event(a) for a in past_page],
        "page_obj": past_page,
        "seo": seo.PageMeta(
            title="Agenda",
            description="O que vai acontecer na escola e o que já aconteceu.",
            path=seo.listing_path(request),
        ),
    }
    return render(request, "publications/agenda.html", context)


@require_GET
def detail(request: HttpRequest, slug: str) -> HttpResponse:
    """/publicacoes/<slug>/: publicada para todos; outros estados só como pré-visualização."""
    article = selectors.article_for_page(slug=slug)
    if article is None:
        raise Http404
    if article.status == Article.Status.PUBLISHED:
        return _render_article(request, article, preview=False)
    if permissions.can_view(request.user, article):
        return _render_article(request, article, preview=True)
    if article.status == Article.Status.ARCHIVED:
        return render(
            request,
            "publications/archived.html",
            {"article": article, "area": presentation.main_area(article)},
            status=410,
        )
    raise Http404


@require_GET
def preview(request: HttpRequest, pk: int) -> HttpResponse:
    """/publicacoes/previa/<id>/: rascunhos sem endereço ainda, para quem pode ver."""
    article = selectors.article_for_page(pk=pk)
    if article is None or not permissions.can_view(request.user, article):
        raise Http404
    if article.status == Article.Status.PUBLISHED and article.slug:
        return redirect(reverse("publications:detail", args=[article.slug]))
    return _render_article(request, article, preview=True)
