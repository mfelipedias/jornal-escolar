from django.contrib import admin

from .models import Reaction


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    """Só consulta: reações nascem e mudam pela página da publicação."""

    list_display = ("article", "kind", "user", "created_at")
    list_filter = ("kind",)
    raw_id_fields = ("article", "user")
    readonly_fields = ("article", "user", "anon_key", "kind", "created_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False  # apagar por aqui deixaria Article.reactions_count desatualizado
