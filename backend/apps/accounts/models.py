import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MaxLengthValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel

ACCESS_LINK_VALIDITY = timedelta(days=7)


def normalize_email(email: str) -> str:
    """E-mail inteiro em minúsculas: é a chave de correspondência com a conta Microsoft."""
    return email.strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        user = self.model(email=normalize_email(email), **extra_fields)
        # Sem senha, a conta só entra pela Microsoft ou por link de acesso (docs/14).
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("role", User.Role.STAFF)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        extra_fields["role"] = User.Role.ADMIN
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username: str | None) -> "User":
        return self.get(email=normalize_email(username or ""))


class User(AbstractBaseUser, PermissionsMixin):
    """Conta de membro da equipe da escola. Alunos não têm conta (docs/02)."""

    class Role(models.TextChoices):
        STAFF = "staff", "Equipe"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Administrador"

    class StaffKind(models.TextChoices):
        TEACHER = "teacher", "Professor"
        MONITOR = "monitor", "Monitor"
        COORDINATOR = "coordinator", "Coordenação"
        PRINCIPAL = "principal", "Direção"
        LIBRARIAN = "librarian", "Sala de leitura"
        OTHER = "other", "Outro"

    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField("nome completo", max_length=150)
    display_name = models.CharField(
        "nome público",
        max_length=80,
        blank=True,
        help_text="Como o nome aparece no site. Se vazio, usa o nome completo.",
    )
    role = models.CharField(
        "papel",
        max_length=10,
        choices=Role.choices,
        default=Role.STAFF,
        db_index=True,
        help_text="Define o que a pessoa pode fazer no sistema.",
    )
    staff_kind = models.CharField(
        "cargo",
        max_length=12,
        choices=StaffKind.choices,
        default=StaffKind.TEACHER,
        help_text="Apenas para exibição; não dá permissões.",
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
        help_text="Desmarque para bloquear o acesso sem apagar a conta.",
    )
    is_staff = models.BooleanField(
        "acesso ao Django Admin",
        default=False,
        editable=False,
        help_text="Calculado a partir do papel: só administradores.",
    )
    avatar = models.ForeignKey(
        "publications.MediaAsset",
        verbose_name="foto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    date_joined = models.DateTimeField("cadastrado em", default=timezone.now)
    deactivated_at = models.DateTimeField("desativado em", null=True, blank=True)
    anonymized_at = models.DateTimeField(
        "anonimizado em",
        null=True,
        blank=True,
        editable=False,
        help_text="Dados pessoais apagados (docs/23). A conta não pode ser reativada.",
    )

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.public_name} <{self.email}>"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = normalize_email(self.email)
        # O papel é a única fonte de verdade: administrador tem acesso total ao Django Admin,
        # os demais papéis não têm acesso nenhum (docs/02).
        self.is_staff = self.is_superuser = self.role == self.Role.ADMIN
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "role" in update_fields:
            kwargs["update_fields"] = {*update_fields, "is_staff", "is_superuser"}
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.email = normalize_email(self.email)

    @property
    def is_anonymized(self) -> bool:
        return self.anonymized_at is not None

    @property
    def public_name(self) -> str:
        return self.display_name or self.full_name

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.public_name


def _default_list() -> list:
    return []


class TeacherProfile(TimeStampedModel):
    """Perfil público de um membro da equipe (docs/06, docs/13, docs/14).

    O nome é por tradição; vale para todos os cargos. Criado junto com a conta.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="profile",
    )
    slug = models.SlugField(
        "endereço do perfil",
        max_length=90,
        unique=True,
        help_text="Parte final da URL do perfil. Mudar quebra links antigos.",
    )
    headline = models.CharField(
        "apresentação curta",
        max_length=120,
        blank=True,
        help_text='Ex.: "Professora de Biologia", "Monitor escolar".',
    )
    bio = models.TextField("sobre mim", blank=True, validators=[MaxLengthValidator(800)])
    education = models.JSONField(
        "formação",
        default=_default_list,
        blank=True,
        help_text="Lista de {degree, institution, year}.",
    )
    since_year = models.PositiveSmallIntegerField("na escola desde", null=True, blank=True)
    links = models.JSONField(
        "links", default=_default_list, blank=True, help_text="Lista de {label, url}, até 4."
    )
    disciplines = models.ManyToManyField(
        "taxonomy.Discipline", verbose_name="disciplinas", related_name="profiles", blank=True
    )
    areas = models.ManyToManyField(
        "taxonomy.KnowledgeArea",
        verbose_name="áreas de atuação",
        related_name="profiles",
        blank=True,
    )
    topics = models.ManyToManyField(
        "taxonomy.Topic", verbose_name="interesses", related_name="profiles", blank=True
    )
    accepts_english = models.BooleanField("aceita sugestões em inglês", default=True)
    is_public = models.BooleanField("perfil público", default=True)
    show_reviewer_credit = models.BooleanField("mostrar crédito como revisor", default=True)
    reviewers_may_publish = models.BooleanField(
        "revisores podem publicar por mim (padrão)", default=False
    )
    show_reads = models.BooleanField("mostrar leituras nas minhas publicações", default=True)
    onboarded_at = models.DateTimeField(
        "assistente de primeiro acesso concluído em",
        null=True,
        blank=True,
        help_text="Vazio: o próximo login leva ao assistente de primeiro acesso.",
    )

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self) -> str:
        return self.user.public_name

    def get_absolute_url(self) -> str:
        return reverse("accounts:teacher_detail", args=[self.slug])


class AccessLink(models.Model):
    """Link de uso único para criar ou redefinir a senha, gerado pelo admin (docs/14).

    Substitui convite e "esqueci minha senha", já que o sistema não envia e-mail.
    """

    class Purpose(models.TextChoices):
        FIRST_ACCESS = "first_access", "Primeiro acesso"
        PASSWORD_RESET = "password_reset", "Redefinir senha"

    class Status(models.TextChoices):
        VALID = "valid", "Válido"
        USED = "used", "Usado"
        EXPIRED = "expired", "Expirado"
        REVOKED = "revoked", "Cancelado"

    id = models.UUIDField("código", primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="access_links",
    )
    purpose = models.CharField("finalidade", max_length=16, choices=Purpose.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="gerado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField("gerado em", auto_now_add=True)
    expires_at = models.DateTimeField("expira em")
    used_at = models.DateTimeField("usado em", null=True, blank=True)
    revoked_at = models.DateTimeField("cancelado em", null=True, blank=True)

    class Meta:
        verbose_name = "link de acesso"
        verbose_name_plural = "links de acesso"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "used_at", "revoked_at"])]

    def __str__(self) -> str:
        return f"{self.get_purpose_display()}: {self.user.email}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.expires_at is None:
            self.expires_at = timezone.now() + ACCESS_LINK_VALIDITY
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("accounts:access_link", kwargs={"token": self.id})

    @property
    def status(self) -> str:
        if self.used_at:
            return self.Status.USED
        if self.revoked_at:
            return self.Status.REVOKED
        if self.expires_at <= timezone.now():
            return self.Status.EXPIRED
        return self.Status.VALID

    @property
    def is_valid(self) -> bool:
        return self.status == self.Status.VALID and self.user.is_active
