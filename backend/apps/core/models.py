from typing import Any

from django.conf import settings
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    """Base das tabelas de negócio: created_at e updated_at (docs/06, "Princípios")."""

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class SiteSetting(models.Model):
    """Valor de uma configuração do site. As chaves e padrões ficam em site_settings.REGISTRY."""

    key = models.CharField("chave", max_length=64, primary_key=True)
    value = models.JSONField("valor", null=True, blank=True)
    description = models.CharField("descrição", max_length=200, blank=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "configuração"
        verbose_name_plural = "configurações"
        ordering = ["key"]

    def __str__(self) -> str:
        from .site_settings import REGISTRY

        spec = REGISTRY.get(self.key)
        return spec.label if spec else self.key

    def save(self, *args: Any, **kwargs: Any) -> None:
        from .site_settings import clear_cache

        super().save(*args, **kwargs)
        clear_cache()

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .site_settings import clear_cache

        result = super().delete(*args, **kwargs)
        clear_cache()
        return result


class StaticPage(TimeStampedModel):
    """Páginas institucionais editáveis: Sobre, Privacidade, Como colaborar (docs/12).

    O corpo é escrito no painel com o mesmo editor das publicações (docs/18): o documento
    fica em body_json e o HTML limpo, gerado pelo servidor (publications/rendering.py), em
    body_html. Sem imagens por enquanto.
    """

    class Slug(models.TextChoices):
        ABOUT = "sobre", "Sobre o jornal"
        PRIVACY = "privacidade", "Privacidade"
        CONTRIBUTE = "colaborar", "Como participar"

    slug = models.SlugField("página", max_length=32, unique=True, choices=Slug.choices)
    title = models.CharField("título", max_length=120)
    lead = models.CharField("linha fina", max_length=240, blank=True)
    body_json = models.JSONField("corpo (documento do editor)", default=dict, blank=True)
    body_html = models.TextField("corpo em HTML", blank=True)
    is_published = models.BooleanField(
        "publicada",
        default=True,
        help_text="Desmarque para tirar a página do ar sem apagar o texto.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "página institucional"
        verbose_name_plural = "páginas institucionais"
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        from .selectors import clear_footer_pages_cache

        super().save(*args, **kwargs)
        clear_footer_pages_cache()

    def get_absolute_url(self) -> str:
        return reverse("core:page", kwargs={"slug": self.slug})

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .selectors import clear_footer_pages_cache

        result = super().delete(*args, **kwargs)
        clear_footer_pages_cache()
        return result


class AuditLog(models.Model):
    """Registro de ações sensíveis (docs/23, "Auditoria"; docs/06). Só leitura no admin.

    Não guarda nomes nem e-mails: o alvo é identificado por tipo e id, e o IP vira um hash com
    sal mensal (apps/core/audit.py). Assim a anonimização de uma pessoa não precisa apagar a
    auditoria, que continua apontando para a conta já anonimizada.
    """

    class Action(models.TextChoices):
        LOGIN = "login", "Entrada no sistema"
        USER_CREATED = "user_created", "Conta criada"
        USER_SIGNED_UP = "user_signed_up", "Cadastro próprio"
        USER_APPROVED = "user_approved", "Conta aprovada"
        USER_REJECTED = "user_rejected", "Cadastro recusado"
        PASSWORD_RESET = "password_reset", "Senha redefinida por código"
        ROLE_CHANGED = "role_changed", "Papel alterado"
        USER_DEACTIVATED = "user_deactivated", "Conta desativada"
        USER_REACTIVATED = "user_reactivated", "Conta reativada"
        USER_ANONYMIZED = "user_anonymized", "Conta anonimizada"
        DATA_EXPORTED = "data_exported", "Dados exportados"
        DELETION_REQUESTED = "deletion_requested", "Exclusão pedida"
        ACCESS_LINK_CREATED = "access_link_created", "Link de acesso gerado"
        SETTING_CHANGED = "setting_changed", "Configuração alterada"
        MEDIA_DELETED = "media_deleted", "Imagem apagada"
        CREDIT_ANONYMIZED = "credit_anonymized", "Crédito de aluno anonimizado"
        ARTICLES_ARCHIVED = "articles_archived", "Publicações arquivadas em massa"
        REVIEWER_REASSIGNED = "reviewer_reassigned", "Revisor trocado em massa"
        FEATURED_CHANGED = "featured_changed", "Destaques da home alterados"
        PAGE_PUBLISHED = "page_published", "Página institucional posta no ar"
        PAGE_UNPUBLISHED = "page_unpublished", "Página institucional tirada do ar"
        COMMENT_MODERATED = "comment_moderated", "Comentário público moderado"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="quem fez",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Vazio quando a ação veio de um comando no servidor.",
    )
    action = models.CharField("ação", max_length=24, choices=Action.choices, db_index=True)
    target_type = models.CharField("tipo do alvo", max_length=40, blank=True)
    target_id = models.CharField("id do alvo", max_length=64, blank=True)
    changes = models.JSONField("detalhes", default=dict, blank=True)
    ip_hash = models.CharField("IP (hash)", max_length=64, blank=True)
    created_at = models.DateTimeField("quando", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "auditoria"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return self.get_action_display()


class EmailSettings(models.Model):
    """Servidor de envio de e-mail editado no Django Admin (Fase 4b, C1b; docs/35).

    Registro único (pk=1). Preenchido, vale no lugar das variáveis EMAIL_* do .env. A senha é
    guardada cifrada com uma chave derivada do SECRET_KEY (apps/core/mail.py) e nunca volta
    para a tela.
    """

    class Security(models.TextChoices):
        TLS = "tls", "STARTTLS (porta 587, o padrão do Gmail)"
        SSL = "ssl", "SSL/TLS direto (porta 465)"
        NONE = "none", "Nenhuma (só para testes na rede interna)"

    host = models.CharField("servidor de saída (SMTP)", max_length=200, default="smtp.gmail.com")
    port = models.PositiveIntegerField("porta", default=587)
    security = models.CharField(
        "segurança", max_length=8, choices=Security.choices, default=Security.TLS
    )
    username = models.CharField(
        "usuário (e-mail que envia)",
        max_length=254,
        blank=True,
        help_text="No Gmail, o próprio endereço. Os e-mails saem com este remetente.",
    )
    password_encrypted = models.TextField(blank=True, editable=False)
    from_name = models.CharField(
        "nome do remetente", max_length=80, blank=True, help_text="Vazio usa o nome do site."
    )
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "e-mail de envio"
        verbose_name_plural = "e-mail de envio"

    def __str__(self) -> str:
        return "E-mail de envio"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from .mail import clear_cache

        self.pk = 1
        super().save(*args, **kwargs)
        clear_cache()

    @property
    def has_password(self) -> bool:
        return bool(self.password_encrypted)

    @property
    def is_complete(self) -> bool:
        return bool(self.host and self.port and self.username and self.password_encrypted)
