from django.contrib import admin

from .models import EditorialComment, EditorialEvent, Notification


@admin.register(EditorialEvent)
class EditorialEventAdmin(admin.ModelAdmin):
    """Auditoria editorial: só leitura (docs/18)."""

    list_display = ("created_at", "article", "kind", "from_status", "to_status", "actor")
    list_filter = ("kind", "to_status")
    search_fields = ("article__title", "actor__email", "actor__full_name", "note")
    list_select_related = ("article", "actor")
    date_hierarchy = "created_at"
    readonly_fields = (
        "article",
        "actor",
        "kind",
        "from_status",
        "to_status",
        "note",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "kind", "read_at", "updated_at")
    list_filter = ("kind", "read_at")
    search_fields = ("message", "user__email", "user__full_name")
    list_select_related = ("user",)
    readonly_fields = (
        "user",
        "actor",
        "kind",
        "article",
        "message",
        "url",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(EditorialComment)
class EditorialCommentAdmin(admin.ModelAdmin):
    """Comentários internos da revisão: só leitura; conversa e resolução ficam na tela (docs/17)."""

    list_display = ("created_at", "article", "author", "status", "anchor_text")
    list_filter = ("status",)
    search_fields = ("article__title", "author__full_name", "body", "anchor_text")
    list_select_related = ("article", "author")
    readonly_fields = [field.name for field in EditorialComment._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
