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
