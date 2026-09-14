"""Metadados da página de publicação: Open Graph e JSON-LD NewsArticle/Article (docs/11, E26).

Alunos entram só com o nome que já aparece no crédito: sem turma, sem URL e sem foto
(docs/23). Créditos ocultos ("mostrar nos créditos" desligado) não entram.
"""

from typing import Any

from django.utils.text import slugify

from apps.core import seo

from . import presentation
from .models import Article, ArticleContributor

# Tipos jornalísticos viram NewsArticle; os demais (projeto, resenha, curiosidade...), Article.
NEWS_TYPE_SLUGS = frozenset({"noticia", "reportagem", "entrevista", "evento"})
HEADLINE_MAX = 110  # limite recomendado pelo Google para headline


def schema_type(article: Article) -> str:
    type_slug = article.type.slug if article.type_id else ""
    return "NewsArticle" if slugify(type_slug) in NEWS_TYPE_SLUGS else "Article"


def cover_image(article: Article) -> seo.OgImage | None:
    """Capa na variante de 1600px (ou o original, se a imagem for menor)."""
    if not article.cover_id:
        return None
    cover = article.cover
    width = min(1600, cover.width) if cover.width else None
    height = round(cover.height * width / cover.width) if width and cover.height else None
    return seo.OgImage(
        url=seo.absolute_url(cover.variant_url("w1600")),
        width=width,
        height=height,
        alt="" if cover.is_decorative else cover.alt_text,
    )


def person(contributor: ArticleContributor) -> dict[str, Any]:
    """Equipe com o perfil (se público); aluno e convidado só com o nome."""
    data: dict[str, Any] = {"@type": "Person", "name": contributor.display_name}
    if contributor.user_id and not contributor.is_student:
        url = presentation.profile_url(contributor.user)
        if url:
            data["url"] = seo.absolute_url(url)
    return data


def authors(article: Article) -> list[dict[str, Any]]:
    return [
        person(c)
        for c in article.contributors.all()
        if c.role in ArticleContributor.EDITING_ROLES and c.show_in_credits
    ]


def article_json_ld(article: Article) -> dict[str, Any]:
    url = seo.absolute_url(article.get_absolute_url())
    modified = max(filter(None, [article.updated_at, article.published_at]), default=None)
    data: dict[str, Any] = {
        "@context": seo.SCHEMA_CONTEXT,
        "@type": schema_type(article),
        "headline": seo.shorten(article.title, HEADLINE_MAX),
        "description": seo.shorten(article.summary),
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "inLanguage": "pt-BR",
        "datePublished": seo.iso(article.published_at),
        "dateModified": seo.iso(modified),
        # Sem autor nos créditos, o próprio jornal assina.
        "author": authors(article) or [seo.organization()],
        "publisher": seo.organization(),
        "isAccessibleForFree": True,
    }
    image = cover_image(article)
    if image:
        data["image"] = [image.url]
    area = presentation.main_area(article)
    if area:
        data["articleSection"] = area.name
    keywords = [d.name for d in article.disciplines.all()] + [
        t.name for t in article.topics.all() if t.is_active
    ]
    if keywords:
        data["keywords"] = ", ".join(keywords)
    return data


def page_meta(article: Article, *, preview: bool) -> seo.PageMeta:
    if preview:
        return seo.PageMeta(title=article.title, description=article.summary, noindex=True)
    return seo.PageMeta(
        title=article.title,
        description=article.summary,
        path=article.get_absolute_url(),
        image=cover_image(article),
        og_type="article",
        published_time=article.published_at,
        modified_time=article.updated_at,
        json_ld=[article_json_ld(article)],
    )
