import pytest
from django.urls import reverse

from apps.publications import media, rendering, services
from apps.publications.models import MediaAsset
from tests.factories import ArticleFactory, UserFactory

from .conftest import as_upload, make_image_bytes

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


def figure(asset_id, **attrs):
    return {"type": "figure", "attrs": {"assetId": asset_id, **attrs}}


@pytest.fixture
def draft(staff_user):
    return services.create_article(staff_user)


@pytest.fixture
def asset(staff_user):
    return media.process_upload(as_upload(make_image_bytes()), staff_user)


# --- documento do editor ---


def test_render_adds_server_src_to_figures(asset):
    result = rendering.render(
        {"type": "doc", "content": [figure(asset.pk, src="https://evil.example/x.png", alt="Foto")]}
    )

    attrs = result.document["content"][0]["attrs"]
    assert attrs["src"] == asset.variant_url("w960")
    assert "evil" not in str(result.document)
    assert 'srcset="' in result.html


def test_render_drops_figures_without_asset_from_document():
    result = rendering.render({"type": "doc", "content": [figure(99999)]})

    assert result.document == {"type": "doc", "content": []}


def test_saved_body_keeps_src_for_reopening(staff_user, draft, asset):
    services.update_article(
        staff_user, draft, body_json={"type": "doc", "content": [figure(asset.pk, alt="Foto")]}
    )

    draft.refresh_from_db()
    assert draft.body_json["content"][0]["attrs"]["src"] == asset.variant_url("w960")
    assert "srcset=" in draft.body_html


# --- upload ligado à publicação ---


def test_upload_with_article_links_asset(client, staff_user, draft):
    client.force_login(staff_user)

    response = client.post(
        reverse("publications:media_upload"),
        {"file": as_upload(make_image_bytes()), "article": draft.pk},
    )

    assert response.status_code == 201
    assert MediaAsset.objects.get(pk=response.json()["id"]).article == draft


def test_upload_to_article_of_someone_else_is_denied(client, draft):
    client.force_login(UserFactory())

    response = client.post(
        reverse("publications:media_upload"),
        {"file": as_upload(make_image_bytes()), "article": draft.pk},
    )

    assert response.status_code == 403
    assert not MediaAsset.objects.exists()


def test_coauthor_can_edit_image_uploaded_by_author(client, staff_user, draft):
    coauthor = UserFactory()
    services.add_staff_credit(staff_user, draft, coauthor)
    asset = media.process_upload(as_upload(make_image_bytes()), staff_user, article=draft)
    client.force_login(coauthor)

    response = client.patch(
        reverse("publications:media_detail", args=[asset.pk]),
        data='{"alt_text": "Descrição"}',
        content_type="application/json",
    )

    assert response.status_code == 200


# --- capa ---


def test_upload_cover(client, staff_user, draft):
    client.force_login(staff_user)

    response = client.post(
        reverse("publications:save_cover", args=[draft.pk]),
        {"file": as_upload(make_image_bytes()), "cover_caption": "Feira"},
        **HTMX,
    )

    draft.refresh_from_db()
    assert response.status_code == 200
    assert draft.cover is not None
    assert draft.cover.article == draft
    assert draft.cover_caption == "Feira"
    html = response.content.decode()
    assert 'id="editor-cover"' in html
    assert "HX-Trigger" in response


def test_choose_existing_image_as_cover_and_remove(client, staff_user, draft, asset):
    client.force_login(staff_user)
    url = reverse("publications:save_cover", args=[draft.pk])

    client.post(url, {"asset": asset.pk}, **HTMX)
    draft.refresh_from_db()
    assert draft.cover == asset

    client.post(url, {"remove": "1"}, **HTMX)
    draft.refresh_from_db()
    assert draft.cover is None
    assert draft.cover_caption == ""


def test_cannot_use_image_from_other_person_as_cover(client, staff_user, draft):
    someone_elses = media.process_upload(as_upload(make_image_bytes()), UserFactory())
    client.force_login(staff_user)

    response = client.post(
        reverse("publications:save_cover", args=[draft.pk]), {"asset": someone_elses.pk}, **HTMX
    )

    assert response.status_code == 403
    draft.refresh_from_db()
    assert draft.cover is None


def test_invalid_cover_upload_shows_error(client, staff_user, draft):
    client.force_login(staff_user)

    response = client.post(
        reverse("publications:save_cover", args=[draft.pk]),
        {"file": as_upload(b"nao e imagem", "x.jpg")},
        **HTMX,
    )

    assert "não é uma imagem válida" in response.content.decode()


def test_cover_with_people_blocks_publication(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    cover = media.process_upload(as_upload(make_image_bytes()), staff_user)
    cover.has_people = True
    cover.save()
    services.set_cover(staff_user, article, cover)

    with pytest.raises(services.ChecklistError):
        services.publish(staff_user, article)


def test_cover_section_refresh_lists_new_images(client, staff_user, draft):
    client.force_login(staff_user)
    media.process_upload(as_upload(make_image_bytes()), staff_user, article=draft)

    response = client.get(reverse("publications:save_cover", args=[draft.pk]), **HTMX)

    assert response.status_code == 200
    assert 'title="Usar como capa"' in response.content.decode()


def test_editor_page_has_image_dialog_and_media_url(client, staff_user, draft):
    client.force_login(staff_user)

    html = client.get(reverse("publications:edit", args=[draft.pk])).content.decode()

    assert "data-image-dialog" in html
    assert '"mediaUrl": "/x/media/"' in html
    assert 'data-cmd="image"' in html
