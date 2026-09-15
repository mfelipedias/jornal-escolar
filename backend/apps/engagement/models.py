from django.conf import settings
from django.db import models
from django.db.models import Q


class Reaction(models.Model):
    """Reação de um leitor a uma publicação (docs/20, docs/06).

    Quem entrou no sistema reage como usuário; o visitante, pelo código aleatório do cookie
    anônimo (anon_key). Exatamente um dos dois fica preenchido, e cada um tem no máximo uma
    reação por publicação. O total por tipo fica em Article.reactions_count.
    """

    class Kind(models.TextChoices):
        INTERESTING = "interesting", "Interessante"
        LEARNED = "learned", "Aprendi algo"
        LIKED = "liked", "Gostei"
        CONGRATS = "congrats", "Parabéns"

    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reactions",
    )
    anon_key = models.UUIDField("código anônimo", null=True, blank=True)
    kind = models.CharField("tipo", max_length=16, choices=Kind.choices)
    created_at = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "reação"
        verbose_name_plural = "reações"
        constraints = [
            models.UniqueConstraint(
                fields=["article", "user"],
                condition=Q(user__isnull=False),
                name="reaction_unique_user",
            ),
            models.UniqueConstraint(
                fields=["article", "anon_key"],
                condition=Q(anon_key__isnull=False),
                name="reaction_unique_anon_key",
            ),
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, anon_key__isnull=True)
                    | Q(user__isnull=True, anon_key__isnull=False)
                ),
                name="reaction_user_or_anon_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.article} · {self.get_kind_display()}"


EMOJIS = {
    Reaction.Kind.INTERESTING: "👍",
    Reaction.Kind.LEARNED: "💡",
    Reaction.Kind.LIKED: "❤️",
    Reaction.Kind.CONGRATS: "👏",
}


class ArticleRead(models.Model):
    """Uma leitura contada: no máximo uma por pessoa, por publicação, por dia (docs/20).

    viewer_key não guarda o usuário nem o código do cookie em claro: é um HMAC com a
    SECRET_KEY e o dia (services.viewer_key), então os registros não formam um histórico de
    leitura de alguém (docs/23) nem se ligam de um dia para o outro. O total fica em
    Article.reads_count; registros com mais de 90 dias são apagados pelo comando cleanup.
    """

    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        related_name="reads",
    )
    viewer_key = models.CharField("leitor (hash)", max_length=64)
    day = models.DateField("dia")
    created_at = models.DateTimeField("registrada em", auto_now_add=True)

    class Meta:
        verbose_name = "leitura"
        verbose_name_plural = "leituras"
        constraints = [
            models.UniqueConstraint(
                fields=["article", "viewer_key", "day"], name="article_read_unique_per_day"
            ),
        ]
        indexes = [models.Index(fields=["day"], name="article_read_day")]

    def __str__(self) -> str:
        return f"{self.article} · {self.day}"


class Comment(models.Model):
    """Comentário público de um leitor (docs/20, "Comentários públicos"; docs/06).

    Nasce pendente e só aparece na página depois de aprovado (moderação na E41). Não há conta
    nem e-mail: o leitor informa um nome. anon_key (cookie "jv") e ip_hash (SHA-256 com sal
    mensal, apps.core.audit.hash_ip) servem só para os limites e para o moderador ver rajadas;
    o comando cleanup os apaga depois de 30 dias, junto com os rejeitados. URLs são removidas
    do corpo ao salvar, com a marca had_links. A equipe responde com reply_body (um nível só,
    sem conversa entre leitores). Article.comments_count guarda só os aprovados.
    """

    NAME_MIN = 2
    NAME_MAX = 60
    BODY_MIN = 5
    BODY_MAX = 1000
    REPLY_MAX = 1000

    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando aprovação"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Rejeitado"

    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author_name = models.CharField("nome", max_length=NAME_MAX)
    body = models.TextField("comentário", max_length=BODY_MAX)
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    anon_key = models.UUIDField("código anônimo", null=True, blank=True)
    ip_hash = models.CharField("IP (hash)", max_length=64, blank=True)
    had_links = models.BooleanField("tinha links", default=False)
    reply_body = models.TextField("resposta", max_length=REPLY_MAX, blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="respondido por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comment_replies",
    )
    replied_at = models.DateTimeField("respondido em", null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="moderado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_comments",
    )
    moderated_at = models.DateTimeField("moderado em", null=True, blank=True)
    created_at = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "comentário público"
        verbose_name_plural = "comentários públicos"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["article", "status", "created_at"], name="comment_article_status"),
            models.Index(fields=["status", "created_at"], name="comment_status_created"),
        ]

    def __str__(self) -> str:
        return f"{self.author_name} · {self.article}"
