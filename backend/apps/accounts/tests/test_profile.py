import pytest
from django.urls import reverse

from apps.accounts.models import TeacherProfile, User
from apps.accounts.services import ensure_profile, unique_profile_slug
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_profile_is_created_with_user():
    user = UserFactory(full_name="Ana Souza")

    assert user.profile.slug == "ana-souza"
    assert user.profile.is_public
    assert user.profile.education == []


def test_profile_slug_uses_display_name():
    user = UserFactory(full_name="Carla Mendes Oliveira", display_name="Profa. Carla")

    assert user.profile.slug == "profa-carla"


def test_profile_slugs_are_unique():
    first = UserFactory(full_name="João Silva")
    second = UserFactory(full_name="João Silva")
    third = UserFactory(full_name="João Silva")

    assert [first.profile.slug, second.profile.slug, third.profile.slug] == [
        "joao-silva",
        "joao-silva-2",
        "joao-silva-3",
    ]


def test_slug_does_not_change_on_rename():
    user = UserFactory(full_name="Ana Souza")
    user.full_name = "Ana Souza Lima"
    user.save()

    user.profile.refresh_from_db()
    assert user.profile.slug == "ana-souza"


def test_ensure_profile_is_idempotent():
    user = UserFactory()

    assert ensure_profile(user) == ensure_profile(user)
    assert TeacherProfile.objects.filter(user=user).count() == 1


def test_createsuperuser_path_gets_profile():
    user = User.objects.create_superuser(
        "dono@escola.sp.gov.br", "senha-forte-123", full_name="Dono"
    )

    assert TeacherProfile.objects.filter(user=user).exists()


def test_unique_slug_fallback_for_empty_name():
    assert unique_profile_slug("!!!") == "perfil"


def test_admin_user_change_page_has_profile_inline(admin_client, staff_user):
    response = admin_client.get(reverse("admin:accounts_user_change", args=[staff_user.pk]))

    assert response.status_code == 200
    assert "profile-0-headline" in response.content.decode()
