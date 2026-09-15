from django.contrib import admin

from .models import Comment, Reaction


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


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Consulta e exclusão (pedido de remoção pelo e-mail de contato, docs/20).

    Aprovar, rejeitar e editar o nome ficam na fila de moderação do painel (E41). Apagar um
    aprovado refaz Article.comments_count (signals.comment_deleted).
    """

    list_display = ("author_name", "article", "status", "had_links", "created_at")
    list_filter = ("status", "had_links")
    search_fields = ("author_name", "body")
    raw_id_fields = ("article",)
    readonly_fields = (
        "article",
        "author_name",
        "body",
        "status",
        "had_links",
        "reply_body",
        "replied_by",
        "replied_at",
        "moderated_by",
        "moderated_at",
        "created_at",
    )
    exclude = ("anon_key", "ip_hash")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
