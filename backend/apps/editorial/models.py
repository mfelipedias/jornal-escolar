from django.conf import settings
from django.db import models


class EditorialEvent(models.Model):
    """Auditoria editorial: quem fez o quê, quando e de qual estado para qual (docs/04, docs/06).

    Toda transição de estado e toda edição por terceiro gera um evento. Só leitura no admin.
    """

    class Kind(models.TextChoices):
        STATUS_CHANGE = "status_change", "Mudança de estado"
        REVIEWER_ASSIGNED = "reviewer_assigned", "Revisor designado"
        REVIEWER_REMOVED = "reviewer_removed", "Revisão cancelada ou recusada"
        APPROVED = "approved", "Revisão aprovada"
        CONTRIBUTOR_CHANGED = "contributor_changed", "Créditos alterados"
        EDITED_AFTER_PUBLISH = "edited_after_publish", "Editado depois de publicado"
        EDITED_BY_THIRD_PARTY = "edited_by_third_party", "Editado por terceiro"
        CREDIT_ANONYMIZED = "credit_anonymized", "Crédito anonimizado"

    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="quem fez",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="editorial_events",
    )
    kind = models.CharField("tipo", max_length=24, choices=Kind.choices)
    from_status = models.CharField("estado anterior", max_length=20, blank=True)
    to_status = models.CharField("estado novo", max_length=20, blank=True)
    note = models.TextField("nota", blank=True)
    created_at = models.DateTimeField("quando", auto_now_add=True)

    class Meta:
        verbose_name = "evento editorial"
        verbose_name_plural = "eventos editoriais"
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["article", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.article} · {self.get_kind_display()}"


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
