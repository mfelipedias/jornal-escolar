import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_custom_user_model_is_active():
    assert get_user_model() is User


def test_create_user_defaults():
    user = User.objects.create_user(
        "ana@professor.educacao.sp.gov.br", "senha-forte-123", full_name="Ana"
    )

    assert user.role == User.Role.STAFF
    assert user.staff_kind == User.StaffKind.TEACHER
    assert user.is_active
    assert not user.is_staff
    assert not user.is_superuser
    assert user.check_password("senha-forte-123")


def test_email_is_stored_lowercase():
    user = User.objects.create_user("  Ana.Silva@Professor.Educacao.SP.gov.br ", full_name="Ana")

    assert user.email == "ana.silva@professor.educacao.sp.gov.br"


def test_email_is_unique_regardless_of_case():
    User.objects.create_user("ana@escola.sp.gov.br", full_name="Ana")

    with pytest.raises(IntegrityError):
        User.objects.create_user("ANA@escola.sp.gov.br", full_name="Outra Ana")


def test_email_is_required():
    with pytest.raises(ValueError, match="e-mail"):
        User.objects.create_user("", full_name="Sem e-mail")


def test_user_without_password_cannot_log_in_with_password():
    user = User.objects.create_user("microsoft@escola.sp.gov.br", full_name="Só Microsoft")

    assert not user.has_usable_password()


def test_login_by_email_ignores_case():
    User.objects.create_user("bruno@escola.sp.gov.br", "senha-forte-123", full_name="Bruno")

    user = authenticate(username="BRUNO@Escola.sp.gov.br", password="senha-forte-123")

    assert user is not None


def test_create_superuser_is_admin():
    user = User.objects.create_superuser(
        "dono@escola.sp.gov.br", "senha-forte-123", full_name="Dono"
    )

    assert user.role == User.Role.ADMIN
    assert user.is_staff
    assert user.is_superuser


@pytest.mark.parametrize("role", [User.Role.STAFF, User.Role.EDITOR])
def test_only_admin_role_accesses_django_admin(role):
    user = User.objects.create_user("x@escola.sp.gov.br", full_name="X", role=role)
    user.is_staff = True
    user.is_superuser = True
    user.save()

    user.refresh_from_db()
    assert not user.is_staff
    assert not user.is_superuser


def test_demoting_admin_removes_admin_access_with_update_fields():
    user = User.objects.create_superuser("dono@escola.sp.gov.br", full_name="Dono")

    user.role = User.Role.EDITOR
    user.save(update_fields=["role"])

    user.refresh_from_db()
    assert user.role == User.Role.EDITOR
    assert not user.is_staff
    assert not user.is_superuser


def test_public_name_falls_back_to_full_name():
    user = User(email="c@escola.sp.gov.br", full_name="Carla Mendes")
    assert user.public_name == "Carla Mendes"

    user.display_name = "Profa. Carla"
    assert user.public_name == "Profa. Carla"
    assert str(user) == "Profa. Carla <c@escola.sp.gov.br>"


def test_passwords_use_argon2(settings):
    # Os testes usam MD5 por velocidade; aqui vale a configuração real de base.py.
    from config.settings import base

    settings.PASSWORD_HASHERS = base.PASSWORD_HASHERS
    user = User.objects.create_user("d@escola.sp.gov.br", "senha-forte-123", full_name="D")

    assert user.password.startswith("argon2")
