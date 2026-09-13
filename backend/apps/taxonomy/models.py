from typing import Any

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class AreaColor(models.TextChoices):
    """As oito cores de área do design system (docs/09)."""

    CORAL = "coral", "Coral"
    VERDE = "verde", "Verde"
    AZUL = "azul", "Azul"
    AMBAR = "ambar", "Âmbar"
    VIOLETA = "violeta", "Violeta"
    PETROLEO = "petroleo", "Petróleo"
    MAGENTA = "magenta", "Magenta (reservada)"
    GRAFITE = "grafite", "Grafite (geral)"


# Classes do Tailwind escritas por extenso: o Tailwind só gera classes que encontra no código.
AREA_COLOR_CLASSES: dict[str, dict[str, str]] = {
    "coral": {
        "text": "text-area-coral",
        "soft_bg": "bg-area-coral-soft",
        "solid_bg": "bg-area-coral",
        "border": "border-area-coral",
    },
    "verde": {
        "text": "text-area-verde",
        "soft_bg": "bg-area-verde-soft",
        "solid_bg": "bg-area-verde",
        "border": "border-area-verde",
    },
    "azul": {
        "text": "text-area-azul",
        "soft_bg": "bg-area-azul-soft",
        "solid_bg": "bg-area-azul",
        "border": "border-area-azul",
    },
    "ambar": {
        "text": "text-area-ambar",
        "soft_bg": "bg-area-ambar-soft",
        "solid_bg": "bg-area-ambar",
        "border": "border-area-ambar",
    },
    "violeta": {
        "text": "text-area-violeta",
        "soft_bg": "bg-area-violeta-soft",
        "solid_bg": "bg-area-violeta",
        "border": "border-area-violeta",
    },
    "petroleo": {
        "text": "text-area-petroleo",
        "soft_bg": "bg-area-petroleo-soft",
        "solid_bg": "bg-area-petroleo",
        "border": "border-area-petroleo",
    },
    "magenta": {
        "text": "text-area-magenta",
        "soft_bg": "bg-area-magenta-soft",
        "solid_bg": "bg-area-magenta",
        "border": "border-area-magenta",
    },
    "grafite": {
        "text": "text-area-grafite",
        "soft_bg": "bg-area-grafite-soft",
        "solid_bg": "bg-area-grafite",
        "border": "border-area-grafite",
    },
}


class SluggedModel(TimeStampedModel):
    """Nome e endereço amigável (slug) gerado a partir do nome quando vazio."""

    name = models.CharField("nome", max_length=80, unique=True)
    slug = models.SlugField(
        "endereço",
        max_length=80,
        unique=True,
        blank=True,
        help_text="Usado na URL. Se vazio, é gerado a partir do nome.",
    )
    is_active = models.BooleanField("ativo", default=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class OrderedSluggedModel(SluggedModel):
    description = models.TextField("descrição", blank=True)
    order = models.PositiveSmallIntegerField(
        "ordem", default=0, help_text="Menor aparece primeiro."
    )

    class Meta:
        abstract = True
        ordering = ["order", "name"]


class KnowledgeArea(OrderedSluggedModel):
    """Área do conhecimento (BNCC e áreas próprias da escola)."""

    color = models.CharField(
        "cor",
        max_length=16,
        choices=AreaColor.choices,
        default=AreaColor.GRAFITE,
        help_text="Cor usada em etiquetas, cards e no cabeçalho da área.",
    )
    short_name = models.CharField(
        "nome curto",
        max_length=30,
        blank=True,
        help_text='Usado no menu do cabeçalho, ex.: "Natureza". Se vazio, usa o nome.',
    )

    class Meta(OrderedSluggedModel.Meta):
        verbose_name = "área do conhecimento"
        verbose_name_plural = "áreas do conhecimento"

    def get_absolute_url(self) -> str:
        return reverse("taxonomy:area", args=[self.slug])

    @property
    def nav_name(self) -> str:
        return self.short_name or self.name

    @property
    def color_classes(self) -> dict[str, str]:
        return AREA_COLOR_CLASSES.get(self.color, AREA_COLOR_CLASSES[AreaColor.GRAFITE])


class Discipline(OrderedSluggedModel):
    area = models.ForeignKey(
        KnowledgeArea,
        verbose_name="área",
        on_delete=models.PROTECT,
        related_name="disciplines",
    )

    class Meta(OrderedSluggedModel.Meta):
        verbose_name = "disciplina"
        verbose_name_plural = "disciplinas"
        ordering = ["area__order", "order", "name"]

    def get_absolute_url(self) -> str:
        return reverse("taxonomy:discipline", args=[self.slug])


class Topic(SluggedModel):
    """Assunto transversal (ex.: Inteligência Artificial).

    Sugestões de professores entram inativas e são aprovadas no admin.
    """

    disciplines = models.ManyToManyField(
        Discipline,
        verbose_name="disciplinas sugeridas",
        related_name="topics",
        blank=True,
    )
    keywords = models.JSONField(
        "palavras-chave",
        default=list,
        blank=True,
        help_text="Termos usados para classificar notícias (Fase 4).",
    )

    class Meta:
        verbose_name = "tópico"
        verbose_name_plural = "tópicos"
        ordering = ["name"]


class ArticleType(OrderedSluggedModel):
    """Tipo editorial da publicação (Notícia, Reportagem, Evento...)."""

    has_event_date = models.BooleanField(
        "exige data do evento",
        default=False,
        help_text="Publicações deste tipo precisam informar quando o evento acontece.",
    )

    class Meta(OrderedSluggedModel.Meta):
        verbose_name = "tipo de publicação"
        verbose_name_plural = "tipos de publicação"

    def get_absolute_url(self) -> str:
        return reverse("taxonomy:type", args=[self.slug])
