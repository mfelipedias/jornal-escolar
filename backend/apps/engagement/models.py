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
