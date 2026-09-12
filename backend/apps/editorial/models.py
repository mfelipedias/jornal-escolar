from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Aviso no painel (sino). O sistema não envia e-mail (docs/04, "Notificações")."""

    class Kind(models.TextChoices):
        REVIEW_REQUESTED = "review_requested", "Revisão pedida"
        CHANGES_REQUESTED = "changes_requested", "Alterações sugeridas"
        APPROVED = "approved", "Revisão aprovada"
        PUBLISHED_BY_OTHER = "published_by_other", "Publicado por outra pessoa"
        EDITED_BY_OTHER = "edited_by_other", "Editado por outra pessoa"
        ARCHIVED_BY_OTHER = "archived_by_other", "Arquivado por outra pessoa"
        COMMENT_PENDING = "comment_pending", "Comentário aguardando"
        REVIEW_STALE = "review_stale", "Revisão parada"
        SYSTEM = "system", "Sistema"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="destinatário",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="quem fez",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kind = models.CharField("tipo", max_length=24, choices=Kind.choices)
    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.CharField("mensagem", max_length=200)
    url = models.CharField("endereço", max_length=300, blank=True)
    read_at = models.DateTimeField("lida em", null=True, blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "read_at", "-updated_at"])]

    def __str__(self) -> str:
        return self.message

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
