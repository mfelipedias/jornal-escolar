from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models


class MediaAsset(models.Model):
    """Imagem enviada pela equipe (docs/06, docs/16, docs/23).

    O arquivo original é reescrito pelo Pillow (sem EXIF) e há três variantes WebP.
    A ligação com a publicação (article) entra na E12.
    """

    class License(models.TextChoices):
        OWN = "own", "Própria (da escola ou de quem publicou)"
        CC_BY = "cc-by", "Creative Commons BY"
        CC_BY_SA = "cc-by-sa", "Creative Commons BY-SA"
        PUBLIC_DOMAIN = "public-domain", "Domínio público"
        AUTHORIZED = "authorized", "Uso autorizado pelo autor"

    VARIANT_WIDTHS = (480, 960, 1600)

    file = models.FileField("arquivo", upload_to="media/", max_length=255)
    variants = models.JSONField(
        "variantes", default=dict, blank=True, help_text='{"w480": caminho, ...} em WebP'
    )
    width = models.PositiveIntegerField("largura")
    height = models.PositiveIntegerField("altura")
    size_bytes = models.PositiveIntegerField("tamanho (bytes)")
    mime = models.CharField("tipo", max_length=32)
    alt_text = models.CharField(
        "texto alternativo",
        max_length=250,
        blank=True,
        help_text="Descreve a imagem para quem não pode vê-la.",
    )
    is_decorative = models.BooleanField(
        "decorativa", default=False, help_text="Imagem sem informação; dispensa texto alternativo."
    )
    credit = models.CharField("crédito", max_length=120, blank=True)
    license = models.CharField(
        "licença", max_length=16, choices=License.choices, default=License.OWN
    )
    has_people = models.BooleanField("aparecem pessoas", default=False)
    consent_ok = models.BooleanField(
        "autorização de imagem",
        default=False,
        help_text="Quem publicou declara ter autorização das pessoas que aparecem.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enviada por",
        on_delete=models.SET_NULL,
        null=True,
        related_name="media_assets",
    )
    created_at = models.DateTimeField("enviada em", auto_now_add=True)

    class Meta:
        verbose_name = "imagem"
        verbose_name_plural = "imagens"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["uploaded_by", "created_at"])]

    def __str__(self) -> str:
        return self.alt_text or self.file.name.rsplit("/", 1)[-1]

    @property
    def url(self) -> str:
        return self.file.url

    def variant_url(self, key: str) -> str:
        path = self.variants.get(key)
        return default_storage.url(path) if path else self.url

    @property
    def variant_urls(self) -> dict[str, str]:
        return {key: default_storage.url(path) for key, path in self.variants.items()}

    @property
    def srcset(self) -> str:
        """Pronto para <img srcset>: "url 480w, url 960w, url 1600w" (sem larguras repetidas)."""
        seen: dict[int, str] = {}
        for key, path in sorted(self.variants.items(), key=lambda kv: int(kv[0][1:])):
            target = int(key[1:])
            actual = min(target, self.width)
            seen.setdefault(actual, default_storage.url(path))
        return ", ".join(f"{url} {w}w" for w, url in sorted(seen.items()))

    @property
    def needs_consent(self) -> bool:
        """Foto com pessoas sem autorização bloqueia a publicação (docs/23)."""
        return self.has_people and not self.consent_ok

    def all_paths(self) -> list[str]:
        return [p for p in [self.file.name, *self.variants.values()] if p]
