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
        COMMENT_ADDED = "comment_added", "Comentário na revisão"
        COMMENT_REPLIED = "comment_replied", "Resposta a comentário"
        COMMENT_RESOLVED = "comment_resolved", "Comentário resolvido"
        COMMENT_REOPENED = "comment_reopened", "Comentário reaberto"

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


class EditorialComment(models.Model):
    """Comentário interno da revisão (docs/17, "Comentários editoriais"; docs/06).

    Geral (sem âncora) ou ancorado num trecho do texto. A âncora guarda o trecho citado
    (anchor_text), um pouco do texto antes e depois (anchor_prefix, anchor_suffix) e as
    posições no texto do documento quando o comentário foi criado (anchor_from, anchor_to).
    O trecho é reencontrado a cada leitura por editorial/anchors.py: editar outro parágrafo
    não perde a âncora; se o próprio trecho mudar, o comentário aparece como "trecho alterado".
    Respostas têm um nível só (parent aponta sempre para um comentário principal).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        RESOLVED = "resolved", "Resolvido"

    ANCHOR_MAX = 300
    CONTEXT_MAX = 40
    BODY_MAX = 2000

    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        related_name="editorial_comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="quem escreveu",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="editorial_comments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="responde a",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField("comentário", max_length=BODY_MAX)
    anchor_text = models.CharField("trecho", max_length=ANCHOR_MAX, blank=True)
    anchor_prefix = models.CharField("antes do trecho", max_length=CONTEXT_MAX, blank=True)
    anchor_suffix = models.CharField("depois do trecho", max_length=CONTEXT_MAX, blank=True)
    anchor_from = models.PositiveIntegerField("início do trecho", null=True, blank=True)
    anchor_to = models.PositiveIntegerField("fim do trecho", null=True, blank=True)
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.OPEN
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="resolvido por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_at = models.DateTimeField("resolvido em", null=True, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "comentário editorial"
        verbose_name_plural = "comentários editoriais"
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["article", "status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.article} · {self.body[:40]}"

    @property
    def is_anchored(self) -> bool:
        return bool(self.anchor_text)

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN


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
        REVIEW_COMMENT = "review_comment", "Comentário na revisão"
        REVIEW_STALE = "review_stale", "Revisão parada"
        SUGGESTIONS = "suggestions", "Sugestões de pauta"
        STORY_IDEA = "story_idea", "Pauta"
        ACCOUNT_PENDING = "account_pending", "Conta aguardando aprovação"
        ACCOUNT_APPROVED = "account_approved", "Conta aprovada"
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
