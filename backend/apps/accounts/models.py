from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


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
    date_joined = models.DateTimeField("cadastrado em", default=timezone.now)
    deactivated_at = models.DateTimeField("desativado em", null=True, blank=True)

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
    def public_name(self) -> str:
        return self.display_name or self.full_name

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.public_name
