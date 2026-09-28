"""Curadoria de notícias externas (docs/21, docs/06 "curation.*").

A E45 cria as fontes e os itens coletados; a E46, a deduplicação por título e a retenção; a E47,
a classificação por tópico e disciplina; a E48, as sugestões por professor; a E49, as pautas.
Só guardamos metadados: título, resumo curto do próprio feed, link e data. Nunca o texto
integral, nunca imagens (só o endereço delas).
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel

SUMMARY_MAX_LENGTH = 600
# Fonte com este número de falhas seguidas aparece em alerta no admin (não é desativada).
FAILURES_ALERT = 5
# Notícia com o mesmo título de outra publicada até 7 dias antes ou depois é descartada.
TITLE_DEDUP_WINDOW = timedelta(days=7)
# Notícias coletadas há mais tempo que isto são apagadas pelo cleanup diário (docs/21, "Higiene").
RETENTION_DAYS = 60


class NewsSource(TimeStampedModel):
    """Feed RSS ou Atom cadastrado por um humano, com o nível de confiança."""

    class Kind(models.TextChoices):
        RSS = "rss", "RSS ou Atom"

    class Language(models.TextChoices):
        PT = "pt", "Português"
        EN = "en", "Inglês"

    name = models.CharField("nome", max_length=120)
    feed_url = models.URLField("endereço do feed", max_length=500, unique=True)
    site_url = models.URLField("site", max_length=500, blank=True)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.RSS)
    language = models.CharField(
        "idioma", max_length=5, choices=Language.choices, default=Language.PT
    )
    trust_level = models.PositiveSmallIntegerField(
        "confiança",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="De 1 a 5. Fontes com 2 ou menos só aparecem para quem pedir.",
    )
    default_topics = models.ManyToManyField(
        "taxonomy.Topic",
        verbose_name="tópicos padrão",
        related_name="news_sources",
        blank=True,
        help_text="Tudo o que vem desta fonte recebe estes tópicos na classificação.",
    )
    default_disciplines = models.ManyToManyField(
        "taxonomy.Discipline",
        verbose_name="disciplinas padrão",
        related_name="news_sources",
        blank=True,
    )
    fetch_interval_minutes = models.PositiveIntegerField(
        "intervalo entre coletas (minutos)",
        default=120,
        validators=[MinValueValidator(30)],
    )
    is_active = models.BooleanField("ativa", default=True)

    # Estado da coleta, preenchido pelo sistema.
    etag = models.CharField(max_length=300, blank=True, editable=False)
    last_modified = models.CharField(max_length=100, blank=True, editable=False)
    last_fetched_at = models.DateTimeField("última coleta", null=True, blank=True)
    last_success_at = models.DateTimeField("última coleta sem erro", null=True, blank=True)
    last_error = models.TextField("último erro", blank=True)
    last_error_at = models.DateTimeField("hora do último erro", null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField("falhas seguidas", default=0)

    class Meta:
        verbose_name = "fonte de notícias"
        verbose_name_plural = "fontes de notícias"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def needs_attention(self) -> bool:
        return self.consecutive_failures >= FAILURES_ALERT

    def is_due(self, now: datetime, tolerance: timedelta = timedelta(minutes=10)) -> bool:
        """Chegou a hora de coletar. A tolerância evita perder a vez por segundos, já que o
        agendador passa a cada 30 minutos."""
        if not self.is_active:
            return False
        if self.last_fetched_at is None:
            return True
        interval = timedelta(minutes=self.fetch_interval_minutes)
        return self.last_fetched_at + interval - tolerance <= now


class NewsItem(TimeStampedModel):
    """Uma notícia vista num feed: só metadados e o link para a fonte."""

    source = models.ForeignKey(
        NewsSource, verbose_name="fonte", on_delete=models.CASCADE, related_name="items"
    )
    title = models.CharField("título", max_length=300)
    url = models.URLField("link do feed", max_length=1000, db_index=True)
    canonical_url = models.URLField("link canônico", max_length=1000)
    url_hash = models.CharField(max_length=64, unique=True, editable=False)
    title_hash = models.CharField(max_length=64, db_index=True, editable=False)
    summary = models.TextField("resumo", max_length=SUMMARY_MAX_LENGTH, blank=True)
    image_url = models.URLField("imagem (só o endereço)", max_length=1000, blank=True)
    published_at = models.DateTimeField("publicada em", db_index=True)
    fetched_at = models.DateTimeField("coletada em")
    language = models.CharField("idioma", max_length=5, choices=NewsSource.Language.choices)
    is_hidden = models.BooleanField("oculta", default=False)

    class Meta:
        verbose_name = "notícia coletada"
        verbose_name_plural = "notícias coletadas"
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title


class NewsItemClassification(models.Model):
    """Tópico ou disciplina provável de uma notícia, com o score e o método (docs/21,
    "Classificação"). Uma linha por notícia, alvo e método; o score que vale é o maior entre os
    métodos. As linhas automáticas são refeitas a cada classificação; as manuais ficam."""

    class Method(models.TextChoices):
        SOURCE_DEFAULT = "source_default", "Padrão da fonte"
        KEYWORD = "keyword", "Palavra-chave"
        MANUAL = "manual", "Ajuste manual"

    item = models.ForeignKey(
        NewsItem,
        verbose_name="notícia",
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    topic = models.ForeignKey(
        "taxonomy.Topic",
        verbose_name="tópico",
        on_delete=models.CASCADE,
        related_name="news_classifications",
        null=True,
        blank=True,
    )
    discipline = models.ForeignKey(
        "taxonomy.Discipline",
        verbose_name="disciplina",
        on_delete=models.CASCADE,
        related_name="news_classifications",
        null=True,
        blank=True,
    )
    score = models.FloatField("score", validators=[MinValueValidator(0), MaxValueValidator(1)])
    method = models.CharField("método", max_length=20, choices=Method.choices)
    matched = models.CharField(
        "palavras encontradas", max_length=300, blank=True, help_text="Só no método palavra-chave."
    )
    created_at = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "classificação de notícia"
        verbose_name_plural = "classificações de notícias"
        ordering = ["-score"]
        constraints = [
            models.CheckConstraint(
                condition=Q(topic__isnull=True) ^ Q(discipline__isnull=True),
                name="curation_classification_topic_xor_discipline",
            ),
            models.UniqueConstraint(
                fields=["item", "topic", "method"],
                condition=Q(topic__isnull=False),
                name="curation_classification_unique_topic",
            ),
            models.UniqueConstraint(
                fields=["item", "discipline", "method"],
                condition=Q(discipline__isnull=False),
                name="curation_classification_unique_discipline",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.topic or self.discipline} ({self.score:.2f}, {self.get_method_display()})"


class NewsRecommendation(TimeStampedModel):
    """Notícia sugerida a um professor, com o score e o que ele fez com ela (docs/21,
    "Recomendação"). Uma por pessoa e notícia."""

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Sugerida"
        IGNORED = "ignored", "Ignorada"
        SAVED = "saved", "Salva"
        INTERESTING = "interesting", "Interessante"
        CONVERTED = "converted", "Virou pauta"

    # Estes seguram a notícia depois dos 60 dias de retenção (docs/21, "Higiene").
    KEPT = (Status.SAVED, Status.INTERESTING, Status.CONVERTED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="professor",
        on_delete=models.CASCADE,
        related_name="news_recommendations",
    )
    item = models.ForeignKey(
        NewsItem,
        verbose_name="notícia",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    score = models.FloatField("score")
    status = models.CharField(
        "situação", max_length=12, choices=Status.choices, default=Status.SUGGESTED
    )
    story_idea = models.ForeignKey(
        "StoryIdea",
        verbose_name="pauta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    acted_at = models.DateTimeField(
        "ação do professor em",
        null=True,
        blank=True,
        help_text="Vazio quando a sugestão expirou sozinha: não conta como ignorar.",
    )

    class Meta:
        verbose_name = "sugestão de notícia"
        verbose_name_plural = "sugestões de notícias"
        ordering = ["-score", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "item"], name="curation_recommendation_unique_user_item"
            )
        ]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"{self.item} → {self.user} ({self.get_status_display()})"


class StoryIdea(TimeStampedModel):
    """Pauta: uma ideia de texto para o jornal, nascida de uma sugestão ou escrita à mão
    (docs/15 "Sugestões e Pautas", docs/21 "Da sugestão à publicação")."""

    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        ASSIGNED = "assigned", "Atribuída"
        IN_PROGRESS = "in_progress", "Em produção"
        DONE = "done", "Concluída"

    title = models.CharField("título", max_length=200)
    notes = models.TextField("notas", max_length=2000, blank=True)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="proposta por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposed_story_ideas",
    )
    item = models.ForeignKey(
        NewsItem,
        verbose_name="notícia de origem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="story_ideas",
    )
    disciplines = models.ManyToManyField(
        "taxonomy.Discipline", verbose_name="disciplinas", related_name="story_ideas", blank=True
    )
    topics = models.ManyToManyField(
        "taxonomy.Topic", verbose_name="tópicos", related_name="story_ideas", blank=True
    )
    status = models.CharField(
        "situação", max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="com quem está",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_story_ideas",
    )
    article = models.ForeignKey(
        "publications.Article",
        verbose_name="publicação",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="story_ideas",
    )
    done_at = models.DateTimeField("concluída em", null=True, blank=True)

    class Meta:
        verbose_name = "pauta"
        verbose_name_plural = "pautas"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title
