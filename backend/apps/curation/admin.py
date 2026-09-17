from django.contrib import admin, messages
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from . import services
from .models import FAILURES_ALERT, NewsItem, NewsSource


class HealthFilter(admin.SimpleListFilter):
    title = "situação"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return [("alerta", f"Com {FAILURES_ALERT} falhas seguidas ou mais"), ("ok", "Sem alerta")]

    def queryset(self, request, queryset):
        if self.value() == "alerta":
            return queryset.filter(consecutive_failures__gte=FAILURES_ALERT)
        if self.value() == "ok":
            return queryset.filter(consecutive_failures__lt=FAILURES_ALERT)
        return queryset


def _report(request: HttpRequest, results: list[services.FetchResult]) -> None:
    for result in results:
        level = messages.SUCCESS if result.ok else messages.ERROR
        messages.add_message(request, level, result.describe())


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    change_form_template = "admin/curation/newssource/change_form.html"
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    list_display = (
        "name",
        "language",
        "trust_level",
        "is_active",
        "last_success_at",
        "health",
    )
    list_filter = ("is_active", "language", "trust_level", HealthFilter)
    search_fields = ("name", "feed_url")
    filter_horizontal = ("default_topics", "default_disciplines")
    actions = ["fetch_now"]
    readonly_fields = (
        "last_fetched_at",
        "last_success_at",
        "consecutive_failures",
        "last_error",
        "last_error_at",
    )
    fieldsets = (
        (None, {"fields": ("name", "feed_url", "site_url", "kind", "language", "trust_level")}),
        ("Coleta", {"fields": ("is_active", "fetch_interval_minutes")}),
        ("Classificação", {"fields": ("default_topics", "default_disciplines")}),
        (
            "Última coleta",
            {
                "fields": (
                    "last_fetched_at",
                    "last_success_at",
                    "consecutive_failures",
                    "last_error",
                    "last_error_at",
                )
            },
        ),
    )

    @admin.display(description="situação")
    def health(self, obj: NewsSource) -> str:
        if obj.needs_attention:
            return format_html("⚠ {} falhas seguidas", obj.consecutive_failures)
        if obj.consecutive_failures:
            return f"{obj.consecutive_failures} falha(s)"
        return "ok" if obj.last_success_at else "—"

    @admin.action(description="Buscar agora")
    def fetch_now(self, request: HttpRequest, queryset: QuerySet[NewsSource]) -> None:
        _report(request, services.fetch_sources(list(queryset)))

    def get_urls(self):
        view = self.admin_site.admin_view(require_POST(self.fetch_now_view))
        return [
            path("<int:object_id>/buscar-agora/", view, name="curation_newssource_fetch"),
            *super().get_urls(),
        ]

    def fetch_now_view(self, request: HttpRequest, object_id: int) -> HttpResponseRedirect:
        source = get_object_or_404(NewsSource, pk=object_id)
        if not self.has_change_permission(request, source):
            messages.error(request, "Você não tem permissão para buscar esta fonte.")
        else:
            _report(request, [services.fetch_source(source)])
        return HttpResponseRedirect(reverse("admin:curation_newssource_change", args=[source.pk]))


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at", "language", "is_hidden")
    list_filter = ("source", "language", "is_hidden", "published_at")
    list_select_related = ("source",)
    search_fields = ("title", "summary", "canonical_url")
    date_hierarchy = "published_at"
    actions = ["hide", "unhide"]
    fields = (
        "source",
        "title",
        "link",
        "summary",
        "image_url",
        "published_at",
        "fetched_at",
        "language",
        "is_hidden",
    )
    readonly_fields = fields

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        # A página abre só para leitura; ocultar é pelas ações da lista.
        return False

    @admin.display(description="link")
    def link(self, obj: NewsItem) -> str:
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            obj.canonical_url,
            obj.canonical_url,
        )

    @admin.action(description="Ocultar das sugestões", permissions=["hide"])
    def hide(self, request: HttpRequest, queryset: QuerySet[NewsItem]) -> None:
        updated = queryset.update(is_hidden=True)
        self.message_user(request, f"{updated} notícia(s) ocultada(s).", messages.SUCCESS)

    @admin.action(description="Mostrar de novo", permissions=["hide"])
    def unhide(self, request: HttpRequest, queryset: QuerySet[NewsItem]) -> None:
        updated = queryset.update(is_hidden=False)
        self.message_user(request, f"{updated} notícia(s) visível(is) de novo.", messages.SUCCESS)

    def has_hide_permission(self, request: HttpRequest) -> bool:
        opts = self.opts
        return request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")
