from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html

from apps.core import audit

from . import services
from .models import Article, ArticleContributor, ArticleRevision, MediaAsset


class ArticleContributorInline(admin.TabularInline):
    model = ArticleContributor
    extra = 0
    fields = (
        "role",
        "user",
        "display_name",
        "is_student",
        "class_group",
        "consent_ok",
        "contribution_note",
        "order",
        "show_in_credits",
    )
    autocomplete_fields = ("user",)


class ArticleRevisionInline(admin.TabularInline):
    model = ArticleRevision
    extra = 0
    can_delete = False
    fields = ("number", "reason", "title", "created_by", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Consulta e correções pontuais. O texto é editado no editor do painel (docs/18)."""

    list_display = ("title", "status", "type", "published_at", "created_by", "is_featured")
    list_filter = ("status", "type", "is_featured", "disciplines__area")
    search_fields = ("title", "subtitle", "slug", "contributors__display_name")
    list_select_related = ("type", "created_by")
    date_hierarchy = "created_at"
    readonly_fields = (
        "slug",
        "status",
        "body_html",
        "body_text",
        "reading_minutes",
        "created_by",
        "created_at",
        "updated_at",
        "published_at",
        "archived_at",
        "reads_count",
        "reactions_count",
        "comments_count",
    )
    exclude = ("body_json", "submitted_at")
    filter_horizontal = ("disciplines", "topics")
    raw_id_fields = ("cover",)
    inlines = [ArticleContributorInline, ArticleRevisionInline]
    actions = ["archive_articles"]

    @admin.action(description="Arquivar (tirar do ar)")
    def archive_articles(self, request: HttpRequest, queryset: QuerySet[Article]) -> None:
        done = 0
        for article in queryset.exclude(status=Article.Status.ARCHIVED):
            try:
                services.archive(request.user, article, note="Arquivado pelo Django Admin.")
                done += 1
            except (PermissionDenied, ValidationError) as exc:
                self.message_user(request, f"{article}: {exc}", messages.WARNING)
        self.message_user(request, f"{done} publicação(ões) arquivada(s).", messages.SUCCESS)


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail",
        "__str__",
        "dimensions",
        "size",
        "has_people",
        "consent_ok",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("has_people", "consent_ok", "license", "created_at")
    search_fields = ("alt_text", "credit", "uploaded_by__email", "uploaded_by__full_name")
    list_select_related = ("uploaded_by",)
    readonly_fields = (
        "preview",
        "file",
        "variants",
        "dimensions",
        "size",
        "mime",
        "uploaded_by",
        "created_at",
    )
    fields = (
        "preview",
        "alt_text",
        "is_decorative",
        "credit",
        "license",
        "has_people",
        "consent_ok",
        "dimensions",
        "size",
        "mime",
        "uploaded_by",
        "created_at",
        "file",
        "variants",
    )

    def has_add_permission(self, request) -> bool:
        return False  # Imagens entram pelo editor, que processa e gera as variantes.

    def _audit_delete(self, request: HttpRequest, assets: list[MediaAsset]) -> None:
        for asset in assets:
            audit.record(
                audit.Action.MEDIA_DELETED,
                actor=request.user,
                target=asset,
                changes={"file": asset.file.name, "article": asset.article_id},
                request=request,
            )

    def delete_model(self, request: HttpRequest, obj: MediaAsset) -> None:
        self._audit_delete(request, [obj])
        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[MediaAsset]) -> None:
        self._audit_delete(request, list(queryset))
        for asset in queryset:  # um por um: o sinal apaga os arquivos
            asset.delete()

    @admin.display(description="")
    def thumbnail(self, obj: MediaAsset) -> str:
        style = "width:64px;height:48px;object-fit:cover;border-radius:4px"
        return format_html('<img src="{}" alt="" style="{}">', obj.variant_url("w480"), style)

    @admin.display(description="prévia")
    def preview(self, obj: MediaAsset) -> str:
        return format_html(
            '<img src="{}" alt="" style="max-width:480px;height:auto">', obj.variant_url("w960")
        )

    @admin.display(description="dimensões")
    def dimensions(self, obj: MediaAsset) -> str:
        return f"{obj.width} x {obj.height} px"

    @admin.display(description="tamanho", ordering="size_bytes")
    def size(self, obj: MediaAsset) -> str:
        return filesizeformat(obj.size_bytes)
