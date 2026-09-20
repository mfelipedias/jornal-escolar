"""Curadoria de notícias externas (docs/21, docs/06 "curation.*").

A E45 cria as fontes e os itens coletados; a E46, a deduplicação por título e a retenção.
Classificação, recomendação e pautas chegam nas etapas seguintes da Fase 4. Só guardamos
metadados: título, resumo curto do próprio feed, link e data. Nunca o texto integral, nunca
imagens (só o endereço delas).
"""

from datetime import datetime, timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

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
