from unittest import mock

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

URL = "/healthz/"


def test_url_name_resolves():
    assert reverse("core:healthz") == URL


def test_ok_returns_status_and_version(client):
    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": settings.APP_VERSION}


def test_version_comes_from_version_file():
    version_file = settings.REPO_DIR / "VERSION"

    assert version_file.read_text(encoding="utf-8").strip() == settings.APP_VERSION


def test_database_down_returns_503(client):
    with mock.patch("apps.core.services.check_database", return_value=False):
        response = client.get(URL)

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": False, "migrations": False}


def test_pending_migrations_returns_503(client):
    with mock.patch("apps.core.services.check_migrations", return_value=False):
        response = client.get(URL)

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_response_has_version_header(client):
    response = client.get(URL)

    assert response["X-App-Version"] == settings.APP_VERSION


def test_post_not_allowed(client):
    response = client.post(URL)

    assert response.status_code == 405


def test_head_allowed_for_external_monitors(client):
    response = client.head(URL)

    assert response.status_code == 200
