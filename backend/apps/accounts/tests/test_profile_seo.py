"""SEO do perfil público: JSON-LD Person e Open Graph (docs/13, E26)."""

import json
import re

import pytest

from apps.publications.models import MediaAsset
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SITE = "https://jornal.exemplo.org"
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def meta(html: str, prop: str) -> str | None:
    match = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', html)
    return match.group(1) if match else None


@pytest.fixture(autouse=True)
def site_url(settings):
    settings.SITE_URL = SITE


@pytest.fixture
def carla():
    user = UserFactory(full_name="Carla Souza", email="carla@professor.educacao.sp.gov.br")
    user.profile.headline = "Professora de Biologia"
    user.profile.bio = "Bio longa."
    user.profile.save()
    return user


def test_person_json_ld(client, carla):
    url = carla.profile.get_absolute_url()

    html = client.get(url).content.decode()

    [block] = JSON_LD_RE.findall(html)
    data = json.loads(block)
    assert data == {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Carla Souza",
        "url": f"{SITE}{url}",
        "jobTitle": "Professora de Biologia",
    }
    assert "worksFor" not in block
    assert "email" not in block
    assert "@professor" not in block
    assert f'<link rel="canonical" href="{SITE}{url}">' in html
    assert meta(html, "og:type") == "profile"
    assert meta(html, "og:title") == "Carla Souza"


def test_job_title_falls_back_to_staff_kind(client):
    user = UserFactory(full_name="Paulo Lima", staff_kind="monitor")

    html = client.get(user.profile.get_absolute_url()).content.decode()

    assert json.loads(JSON_LD_RE.findall(html)[0])["jobTitle"] == "Monitor"


def test_other_staff_kind_without_headline_has_no_job_title(client):
    user = UserFactory(full_name="Ana Reis", staff_kind="other")

    html = client.get(user.profile.get_absolute_url()).content.decode()

    assert "jobTitle" not in json.loads(JSON_LD_RE.findall(html)[0])


def test_photo_is_og_image_and_person_image(client, carla):
    avatar = MediaAsset.objects.create(
        file="media/2026/09/foto.jpg",
        variants={"w480": "media/2026/09/foto-w480.webp"},
        width=1024,
        height=1024,
        size_bytes=1000,
        mime="image/jpeg",
        uploaded_by=carla,
    )
    carla.avatar = avatar
    carla.save()

    html = client.get(carla.profile.get_absolute_url()).content.decode()

    image = f"{SITE}/media/media/2026/09/foto-w480.webp"
    assert meta(html, "og:image") == image
    assert meta(html, "og:image:width") == "480"
    assert json.loads(JSON_LD_RE.findall(html)[0])["image"] == image


def test_hidden_profile_for_owner_is_noindex_without_json_ld(client, carla):
    carla.profile.is_public = False
    carla.profile.save()
    client.force_login(carla)

    html = client.get(carla.profile.get_absolute_url()).content.decode()

    assert '<meta name="robots" content="noindex">' in html
    assert 'rel="canonical"' not in html
    assert JSON_LD_RE.findall(html) == []


def test_teacher_list_has_canonical(client):
    html = client.get("/professores/?cargo=professores").content.decode()

    assert f'<link rel="canonical" href="{SITE}/professores/">' in html
