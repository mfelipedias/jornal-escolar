from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.models import TimeStampedModel


class Article(TimeStampedModel):
    """Publicação do jornal (docs/04, docs/06)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        IN_REVIEW = "in_review", "Em revisão"
        CHANGES_REQUESTED = "changes_requested", "Alterações sugeridas"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Arquivado"

    title = models.CharField("título", max_length=120, default="Sem título")
    subtitle = models.CharField("linha fina", max_length=220, blank=True)
    slug = models.SlugField(
        "endereço",
        max_length=140,
        unique=True,
        null=True,
        blank=True,
        help_text="Gerado na primeira publicação e nunca muda.",
    )
    type = models.ForeignKey(
        "taxonomy.ArticleType",
        verbose_name="tipo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField(
        "estado", max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    body_json = models.JSONField("corpo (documento do editor)", default=dict, blank=True)
    body_html = models.TextField("corpo em HTML", blank=True)
    body_text = models.TextField("corpo em texto", blank=True)
    cover = models.ForeignKey(
        "publications.MediaAsset",
        verbose_name="capa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    cover_caption = models.CharField("legenda da capa", max_length=200, blank=True)
    disciplines = models.ManyToManyField(
        "taxonomy.Discipline", verbose_name="disciplinas", related_name="articles", blank=True
    )
    topics = models.ManyToManyField(
        "taxonomy.Topic", verbose_name="tópicos", related_name="articles", blank=True
    )
    event_at = models.DateTimeField("data do evento", null=True, blank=True, db_index=True)
    event_location = models.CharField("local do evento", max_length=120, blank=True)
    sources = models.JSONField(
        "fontes", default=list, blank=True, help_text="Lista de {title, url, publisher}."
    )
    reading_minutes = models.PositiveSmallIntegerField("minutos de leitura", default=1)
    is_featured = models.BooleanField("destaque na home", default=False, db_index=True)
    featured_order = models.PositiveSmallIntegerField("ordem do destaque", null=True, blank=True)
    comments_enabled = models.BooleanField("comentários ligados", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_articles",
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="última edição por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    submitted_at = models.DateTimeField("enviado para revisão em", null=True, blank=True)
    published_at = models.DateTimeField("publicado em", null=True, blank=True)
    archived_at = models.DateTimeField("arquivado em", null=True, blank=True)
    reads_count = models.PositiveIntegerField("leituras", default=0)
    reactions_count = models.JSONField("reações", default=dict, blank=True)
    comments_count = models.PositiveIntegerField("comentários aprovados", default=0)

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="article_status_published")
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        if self.slug:
            return reverse("publications:detail", args=[self.slug])
        return reverse("publications:preview", args=[self.pk])

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def summary(self) -> str:
        """Linha fina ou início do texto (meta description, cards)."""
        if self.subtitle:
            return self.subtitle
        text = " ".join(self.body_text.split())
        return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + "…"


class ArticleContributor(models.Model):
    """Crédito de uma publicação: membro da equipe ou pessoa sem conta (aluno, turma, convidado)."""

    class Role(models.TextChoices):
        AUTHOR = "author", "Autor"
        COAUTHOR = "coauthor", "Coautor"
        COLLABORATOR = "collaborator", "Colaboração"
        REVIEWER = "reviewer", "Revisão"
        EDITOR = "editor", "Edição"

    EDITING_ROLES = (Role.AUTHOR, Role.COAUTHOR)

    article = models.ForeignKey(
        Article, verbose_name="publicação", on_delete=models.CASCADE, related_name="contributors"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="membro da equipe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contributions",
    )
    display_name = models.CharField(
        "nome no crédito",
        max_length=80,
        help_text="Para membros da equipe, copiado do perfil no momento do crédito.",
    )
    role = models.CharField("papel", max_length=16, choices=Role.choices, default=Role.AUTHOR)
    is_student = models.BooleanField("aluno", default=False)
    class_group = models.CharField(
        "turma", max_length=20, blank=True, help_text='Ex.: "2ª série B"'
    )
    consent_ok = models.BooleanField(
        "autorização",
        default=False,
        help_text="Declaro ter autorização do responsável para publicar o nome do aluno.",
    )
    contribution_note = models.CharField(
        "contribuição", max_length=80, blank=True, help_text='Ex.: "fotos", "entrevista"'
    )
    can_publish = models.BooleanField("pode publicar pelo autor", default=False)
    order = models.PositiveSmallIntegerField("ordem", default=0)
    show_in_credits = models.BooleanField("mostrar nos créditos", default=True)
    anonymized_at = models.DateTimeField(
        "anonimizado em",
        null=True,
        blank=True,
        editable=False,
        help_text="Nome do aluno trocado por crédito genérico (docs/23).",
    )

    class Meta:
        verbose_name = "crédito"
        verbose_name_plural = "créditos"
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "user", "role"],
                condition=Q(user__isnull=False),
                name="contributor_unique_user_role",
            ),
            models.CheckConstraint(
                condition=Q(is_student=False) | Q(user__isnull=True),
                name="contributor_student_has_no_user",
            ),
        ]
        indexes = [models.Index(fields=["user", "role"])]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"


class ArticleRevision(models.Model):
    """Cópia do texto em momentos importantes: publicação e edição depois de publicado."""

    class Reason(models.TextChoices):
        PUBLISHED = "published", "Publicação"
        SUBMITTED = "submitted", "Envio para revisão"
        EDITED_AFTER_PUBLISH = "edited_after_publish", "Edição depois de publicado"
        MANUAL = "manual", "Manual"

    article = models.ForeignKey(
        Article, verbose_name="publicação", on_delete=models.CASCADE, related_name="revisions"
    )
    number = models.PositiveIntegerField("número")
    title = models.CharField("título", max_length=120)
    subtitle = models.CharField("linha fina", max_length=220, blank=True)
    body_json = models.JSONField("corpo", default=dict)
    reason = models.CharField("motivo", max_length=24, choices=Reason.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="feita por",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField("feita em", auto_now_add=True)

    class Meta:
        verbose_name = "versão"
        verbose_name_plural = "versões"
        ordering = ["article", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["article", "number"], name="revision_unique_number")
        ]

    def __str__(self) -> str:
        return f"{self.article} · v{self.number}"


class MediaAsset(models.Model):
    """Imagem enviada pela equipe (docs/06, docs/16, docs/23).

    O arquivo original é reescrito pelo Pillow (sem EXIF) e há três variantes WebP.
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
    article = models.ForeignKey(
        Article,
        verbose_name="publicação",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
        return self.file.url if self.file else ""

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
