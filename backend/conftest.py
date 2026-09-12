"""Fixtures compartilhadas por todos os testes (apps/*/tests e tests/)."""

import pytest
from django.core.cache import cache

from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    """Configurações do site ficam em cache; cada teste começa sem nada guardado."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff_user(db):
    return UserFactory()


@pytest.fixture
def editor_user(db):
    return UserFactory(editor=True)


@pytest.fixture
def admin_user(db):
    """Substitui a fixture do pytest-django, que supõe um campo username."""
    return UserFactory(admin=True)


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client
