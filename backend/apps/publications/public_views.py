"""Páginas públicas das publicações (docs/11)."""

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.editorial import permissions

from . import presentation, selectors
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
        "share_url": request.build_absolute_uri(request.path),
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
