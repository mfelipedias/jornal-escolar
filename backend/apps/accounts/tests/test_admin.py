import pytest
from django.urls import reverse

from apps.accounts.models import User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("url_name", ["admin:accounts_user_changelist", "admin:accounts_user_add"])
def test_admin_user_pages_render(admin_client, url_name):
    response = admin_client.get(reverse(url_name))

    assert response.status_code == 200


def test_admin_change_page_renders(admin_client, staff_user):
    response = admin_client.get(reverse("admin:accounts_user_change", args=[staff_user.pk]))

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


@pytest.mark.parametrize("trait", [{}, {"editor": True}])
def test_non_admin_cannot_access_django_admin(client, trait):
    client.force_login(UserFactory(**trait))

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
