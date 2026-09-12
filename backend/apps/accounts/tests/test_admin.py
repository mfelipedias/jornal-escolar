import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(
        "dono@escola.sp.gov.br", "senha-forte-123", full_name="Dono"
    )
    client.force_login(admin)
    return client


@pytest.mark.parametrize("url_name", ["admin:accounts_user_changelist", "admin:accounts_user_add"])
def test_admin_user_pages_render(admin_client, url_name):
    response = admin_client.get(reverse(url_name))

    assert response.status_code == 200


def test_admin_change_page_renders(admin_client):
    user = User.objects.create_user("ana@escola.sp.gov.br", full_name="Ana")

    response = admin_client.get(reverse("admin:accounts_user_change", args=[user.pk]))

    assert response.status_code == 200


def test_admin_creates_staff_without_password(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "Novo.Professor@Escola.sp.gov.br",
            "full_name": "Novo Professor",
            "role": User.Role.STAFF,
            "staff_kind": User.StaffKind.TEACHER,
            "usable_password": "false",
        },
    )

    assert response.status_code == 302
    user = User.objects.get(email="novo.professor@escola.sp.gov.br")
    assert not user.has_usable_password()
    assert not user.is_staff


def test_editor_cannot_access_django_admin(client):
    editor = User.objects.create_user("ed@escola.sp.gov.br", full_name="Ed", role=User.Role.EDITOR)
    client.force_login(editor)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
