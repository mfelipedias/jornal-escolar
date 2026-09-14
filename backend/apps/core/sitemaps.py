"""Sitemap do jornal em /sitemap.xml (docs/07, E26).

Só entram páginas públicas e indexáveis: nada do painel, pré-visualizações, perfis
ocultos ou páginas institucionais fora do ar. Os endereços usam SITE_URL.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Q
from django.urls import reverse

from apps.accounts.models import TeacherProfile
from apps.publications.models import Article, ArticleContributor
from apps.taxonomy.models import ArticleType, Discipline, KnowledgeArea

from .models import StaticPage

NOT_REVIEWER = [r for r in ArticleContributor.Role if r != ArticleContributor.Role.REVIEWER]


class SiteUrlSitemap(Sitemap):
    """Domínio e protocolo de SITE_URL, e não do Host da requisição."""

    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


class MainPagesSitemap(SiteUrlSitemap):
    changefreq = "daily"

    def items(self):
        return ["core:home", "publications:list", "publications:agenda", "accounts:teacher_list"]

    def location(self, item):
        return reverse(item)


class ArticleSitemap(SiteUrlSitemap):
    changefreq = "weekly"

    def items(self):
        return (
            Article.objects.filter(status=Article.Status.PUBLISHED, slug__isnull=False)
            .only("slug", "updated_at", "published_at")
            .order_by("-published_at")
        )

    def lastmod(self, article):
        return article.updated_at


class StaticPageSitemap(SiteUrlSitemap):
    changefreq = "monthly"

    def items(self):
        return StaticPage.objects.filter(is_published=True).order_by("slug")

    def lastmod(self, page):
        return page.updated_at


class TaxonomySitemap(SiteUrlSitemap):
    changefreq = "weekly"

    def items(self):
        return [
            *KnowledgeArea.objects.filter(is_active=True),
            *Discipline.objects.filter(is_active=True, area__is_active=True).select_related("area"),
            *ArticleType.objects.filter(is_active=True),
        ]


class TeacherSitemap(SiteUrlSitemap):
    """Perfis públicos; conta desativada só se ainda tiver crédito visível (docs/13)."""

    changefreq = "weekly"

    def items(self):
        visible_credit = Q(
            user__contributions__article__status=Article.Status.PUBLISHED,
            user__contributions__show_in_credits=True,
        ) & (Q(user__contributions__role__in=NOT_REVIEWER) | Q(show_reviewer_credit=True))
        return (
            TeacherProfile.objects.filter(is_public=True)
            .filter(Q(user__is_active=True) | visible_credit)
            .distinct()
            .order_by("slug")
        )

    def lastmod(self, profile):
        return profile.updated_at


SITEMAPS = {
    "paginas": MainPagesSitemap,
    "publicacoes": ArticleSitemap,
    "institucional": StaticPageSitemap,
    "temas": TaxonomySitemap,
    "equipe": TeacherSitemap,
}
