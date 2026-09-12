from django.contrib import admin

from .models import Notification


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
