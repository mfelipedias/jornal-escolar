"""Duplicar como rascunho (E24, docs/15): texto, créditos e cópia independente das imagens."""

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage

from apps.publications import media, services
from apps.publications.models import Article, ArticleContributor, MediaAsset
from tests.factories import ArticleFactory, DisciplineFactory, UserFactory

from .conftest import as_upload, make_image_bytes

pytestmark = pytest.mark.django_db


def figure(asset_id):
    return {"type": "figure", "attrs": {"assetId": asset_id}}


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


@pytest.fixture
def source(staff_user):
    article = ArticleFactory(author=staff_user, created_by=staff_user, title="Feira")
    body_image = media.process_upload(as_upload(make_image_bytes()), staff_user, article)
    cover = media.process_upload(as_upload(make_image_bytes()), staff_user, article)
    MediaAsset.objects.filter(pk=body_image.pk).update(alt_text="Estande", has_people=True)
    services.update_article(
        staff_user,
        article,
        body_json={"type": "doc", "content": [paragraph("Olá"), figure(body_image.pk)]},
    )
    services.set_cover(staff_user, article, cover, "Legenda")
    article.disciplines.add(DisciplineFactory())
    return article


def test_copies_images_as_new_assets(staff_user, source):
    duplicate = services.duplicate_article(staff_user, source)

    original_ids = set(source.media_assets.values_list("pk", flat=True))
    copies = list(duplicate.media_assets.all())
    assert len(copies) == 2
    assert not original_ids & {asset.pk for asset in copies}
    for asset in copies:
        assert asset.uploaded_by == staff_user
        for path in asset.all_paths():
            assert default_storage.exists(path)
    assert duplicate.cover_id in {asset.pk for asset in copies}
    assert duplicate.cover_caption == "Legenda"
    assert "<figure" in duplicate.body_html
    body_copy = MediaAsset.objects.get(article=duplicate, alt_text="Estande")
    assert body_copy.has_people
    assert f"/{body_copy.file.name.rsplit('.', 1)[0]}" in duplicate.body_html


def test_later_edits_keep_copied_images(staff_user, source):
    duplicate = services.duplicate_article(staff_user, source)

    services.update_article(staff_user, duplicate, body_json=duplicate.body_json)

    duplicate.refresh_from_db()
    assert "<figure" in duplicate.body_html


def test_deleting_copy_does_not_touch_original_files(staff_user, source):
    duplicate = services.duplicate_article(staff_user, source)
    copied_paths = {p for a in duplicate.media_assets.all() for p in a.all_paths()}
    original_paths = {p for a in source.media_assets.all() for p in a.all_paths()}

    assert not copied_paths & original_paths


def test_credits_and_status(staff_user, source):
    colleague = UserFactory()
    ArticleContributor.objects.create(
        article=source, user=colleague, display_name="Colega", role="coauthor", order=1
    )
    ArticleContributor.objects.create(
        article=source, user=UserFactory(), display_name="Revisora", role="reviewer", order=2
    )
    duplicate = services.duplicate_article(staff_user, source)

    assert duplicate.status == Article.Status.DRAFT
    assert duplicate.title == "Feira (cópia)"
    assert list(duplicate.contributors.values_list("display_name", "role")) == [
        (staff_user.public_name, "author"),
        ("Colega", "coauthor"),
    ]


def test_long_title_is_cut(staff_user):
    article = ArticleFactory(author=staff_user, created_by=staff_user, title="x" * 120)
    duplicate = services.duplicate_article(staff_user, article)
    assert len(duplicate.title) <= services.TITLE_MAX
    assert duplicate.title.endswith("(cópia)")


def test_needs_edit_permission(source):
    with pytest.raises(PermissionDenied):
        services.duplicate_article(UserFactory(), source)
