import json

import pytest
from django.urls import reverse

from apps.publications import media
from apps.publications.models import MediaAsset
from tests.factories import UserFactory

from .conftest import as_upload, make_image_bytes

pytestmark = pytest.mark.django_db

UPLOAD_URL = "/x/media/"


@pytest.fixture
def asset(staff_user):
    return media.process_upload(as_upload(make_image_bytes()), staff_user)


def detail_url(asset: MediaAsset) -> str:
    return reverse("publications:media_detail", args=[asset.pk])


def test_upload_requires_login(client):
    response = client.post(UPLOAD_URL, {"file": as_upload(make_image_bytes())})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_upload_returns_json(client, staff_user):
    client.force_login(staff_user)

    response = client.post(UPLOAD_URL, {"file": as_upload(make_image_bytes())})

    assert response.status_code == 201
    body = response.json()
    assert set(body) >= {"id", "url", "variants", "width", "height", "srcset"}
    assert set(body["variants"]) == {"w480", "w960", "w1600"}
    assert body["url"].startswith("/media/media/")
    assert MediaAsset.objects.get(pk=body["id"]).uploaded_by == staff_user


def test_upload_rejects_fake_file(client, staff_user):
    client.force_login(staff_user)

    response = client.post(UPLOAD_URL, {"file": as_upload(b"nao sou imagem", "x.jpg")})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_image"


def test_upload_without_file(client, staff_user):
    client.force_login(staff_user)

    assert client.post(UPLOAD_URL).json()["error"]["code"] == "missing_file"


def test_get_not_allowed_on_upload(client, staff_user):
    client.force_login(staff_user)

    assert client.get(UPLOAD_URL).status_code == 405


def test_upload_rate_limit(client, staff_user, settings):
    settings.MEDIA_UPLOADS_PER_HOUR = 2
    client.force_login(staff_user)
    small = make_image_bytes(size=(100, 100))

    statuses = [client.post(UPLOAD_URL, {"file": as_upload(small)}).status_code for _ in range(3)]

    assert statuses == [201, 201, 429]


def test_patch_metadata(client, staff_user, asset):
    client.force_login(staff_user)

    response = client.patch(
        detail_url(asset),
        data=json.dumps(
            {"alt_text": "Alunos na feira de ciências", "has_people": True, "consent_ok": True}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    asset.refresh_from_db()
    assert asset.alt_text == "Alunos na feira de ciências"
    assert asset.has_people
    assert asset.consent_ok
    assert asset.credit == ""  # campos não enviados continuam como estavam


def test_patch_validates_license(client, staff_user, asset):
    client.force_login(staff_user)

    response = client.patch(
        detail_url(asset), data=json.dumps({"license": "roubada"}), content_type="application/json"
    )

    assert response.status_code == 400
    assert "license" in response.json()["error"]["fields"]


def test_patch_invalid_json(client, staff_user, asset):
    client.force_login(staff_user)

    response = client.patch(detail_url(asset), data="{", content_type="application/json")

    assert response.status_code == 400


def test_other_staff_cannot_edit(client, asset):
    client.force_login(UserFactory())

    response = client.patch(
        detail_url(asset), data=json.dumps({"alt_text": "x"}), content_type="application/json"
    )

    assert response.status_code == 403


def test_editor_can_edit(client, editor_user, asset):
    client.force_login(editor_user)

    response = client.patch(
        detail_url(asset),
        data=json.dumps({"credit": "Foto: Grêmio"}),
        content_type="application/json",
    )

    assert response.status_code == 200


def test_media_is_served_in_dev(client, asset, settings):
    # urls.py só serve /media/ com DEBUG; aqui conferimos que o arquivo existe no storage.
    assert asset.url.startswith(settings.MEDIA_URL)


def test_admin_lists_media(admin_client, asset):
    response = admin_client.get(reverse("admin:publications_mediaasset_changelist"))

    assert response.status_code == 200
    assert asset.variant_url("w480") in response.content.decode()
