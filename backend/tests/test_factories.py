import pytest

from apps.accounts.models import User
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_user_factory_creates_staff_with_password():
    user = UserFactory()

    assert user.pk is not None
    assert user.role == User.Role.STAFF
    assert user.check_password(DEFAULT_PASSWORD)


def test_user_factory_traits():
    assert UserFactory(editor=True).role == User.Role.EDITOR
    assert UserFactory(admin=True).is_superuser
    assert not UserFactory(microsoft_only=True).has_usable_password()


def test_user_factory_emails_are_unique():
    emails = {user.email for user in UserFactory.create_batch(5)}

    assert len(emails) == 5
