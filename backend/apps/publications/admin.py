from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html

from .models import MediaAsset


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
