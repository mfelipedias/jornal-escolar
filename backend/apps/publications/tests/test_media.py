import io
from pathlib import Path

import pytest
from django.core.files.storage import default_storage
from PIL import Image

from apps.publications import media
from apps.publications.models import MediaAsset

from .conftest import as_upload, make_image_bytes

pytestmark = pytest.mark.django_db


def gps_exif() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Fabricante do celular"  # Make
    exif[0x0112] = 1  # Orientation
    gps = {1: "S", 2: (23.0, 32.0, 0.0), 3: "W", 4: (46.0, 47.0, 0.0)}
    exif[0x8825] = gps  # GPSInfo
    return exif.tobytes()


def open_stored(path: str) -> Image.Image:
    with default_storage.open(path) as fh:
        image = Image.open(io.BytesIO(fh.read()))
        image.load()
        return image


def test_jpeg_upload_creates_asset_and_three_webp_variants(staff_user):
    asset = media.process_upload(as_upload(make_image_bytes()), staff_user)

    assert asset.width == 2000
    assert asset.height == 1200
    assert asset.mime == "image/jpeg"
    assert set(asset.variants) == {"w480", "w960", "w1600"}
    for key, expected_width in [("w480", 480), ("w960", 960), ("w1600", 1600)]:
        variant = open_stored(asset.variants[key])
        assert variant.format == "WEBP"
        assert variant.width == expected_width
    assert asset.size_bytes > 0
    assert asset.uploaded_by == staff_user


def test_file_names_are_generated_by_year_and_month(staff_user):
    asset = media.process_upload(
        as_upload(make_image_bytes(), name="../../etc/passwd.jpg"), staff_user
    )

    path = Path(asset.file.name)
    assert path.parts[0] == "media"
    assert len(path.parts[1]) == 4
    assert len(path.parts[2]) == 2
    assert path.stem != "passwd"
    assert len(path.stem) == 32


def test_exif_and_gps_are_removed(staff_user):
    data = make_image_bytes(exif=gps_exif())
    assert Image.open(io.BytesIO(data)).getexif()  # a entrada tem EXIF

    asset = media.process_upload(as_upload(data), staff_user)

    stored = open_stored(asset.file.name)
    assert not stored.getexif()
    assert "exif" not in stored.info
    for path in asset.variants.values():
        assert not open_stored(path).getexif()


def test_camera_rotation_is_applied(staff_user):
    exif = Image.Exif()
    exif[0x0112] = 6  # girar 90° para a direita
    data = make_image_bytes(size=(1200, 800), exif=exif.tobytes())

    asset = media.process_upload(as_upload(data), staff_user)

    assert (asset.width, asset.height) == (800, 1200)


def test_png_transparency_is_kept(staff_user):
    data = make_image_bytes("PNG", size=(600, 400), mode="RGBA", color=(0, 0, 0, 0))

    asset = media.process_upload(as_upload(data, "logo.png", "image/png"), staff_user)

    assert asset.mime == "image/png"
    assert open_stored(asset.file.name).mode == "RGBA"
    assert open_stored(asset.variants["w480"]).mode == "RGBA"


def test_webp_upload(staff_user):
    asset = media.process_upload(
        as_upload(make_image_bytes("WEBP"), "a.webp", "image/webp"), staff_user
    )

    assert asset.mime == "image/webp"


def test_small_image_is_not_upscaled(staff_user):
    asset = media.process_upload(as_upload(make_image_bytes(size=(300, 200))), staff_user)

    assert open_stored(asset.variants["w1600"]).width == 300
    # Sem larguras repetidas no srcset: as três variantes têm 300px, então sobra um item.
    assert ", " not in asset.srcset
    assert asset.srcset.endswith(" 300w")


def test_srcset_lists_each_width_once(staff_user):
    asset = media.process_upload(as_upload(make_image_bytes(size=(1000, 600))), staff_user)

    widths = [item.rsplit(" ", 1)[1] for item in asset.srcset.split(", ")]
    assert widths == ["480w", "960w", "1000w"]


def test_fake_image_with_image_extension_is_rejected(staff_user):
    fake = as_upload(b"#!/bin/sh\nrm -rf /\n" * 50, "foto.jpg", "image/jpeg")

    with pytest.raises(media.MediaError) as exc:
        media.process_upload(fake, staff_user)

    assert exc.value.code == "invalid_image"
    assert not MediaAsset.objects.exists()


def test_html_disguised_as_png_is_rejected(staff_user):
    with pytest.raises(media.MediaError):
        media.process_upload(
            as_upload(b"<svg onload=alert(1)></svg>", "x.png", "image/png"), staff_user
        )


def test_gif_is_rejected(staff_user):
    with pytest.raises(media.MediaError) as exc:
        media.process_upload(
            as_upload(make_image_bytes("GIF", mode="P"), "a.gif", "image/gif"), staff_user
        )

    assert exc.value.code == "unsupported_type"


def test_truncated_image_is_rejected(staff_user):
    data = make_image_bytes()

    with pytest.raises(media.MediaError):
        media.process_upload(as_upload(data[: len(data) // 3]), staff_user)


def test_file_size_limit(staff_user, settings):
    settings.MEDIA_MAX_UPLOAD_BYTES = 1000

    with pytest.raises(media.MediaError) as exc:
        media.process_upload(as_upload(make_image_bytes()), staff_user)

    assert exc.value.code == "file_too_large"
    assert exc.value.status == 413


def test_dimension_limit(staff_user, settings):
    settings.MEDIA_MAX_DIMENSION = 1000

    with pytest.raises(media.MediaError) as exc:
        media.process_upload(as_upload(make_image_bytes(size=(1200, 800))), staff_user)

    assert exc.value.code == "too_large_dimensions"


def test_user_quota(staff_user, settings):
    media.process_upload(as_upload(make_image_bytes()), staff_user)
    settings.MEDIA_USER_QUOTA_BYTES = MediaAsset.objects.get().size_bytes + 10

    with pytest.raises(media.MediaError) as exc:
        media.process_upload(as_upload(make_image_bytes()), staff_user)

    assert exc.value.code == "quota_exceeded"
    assert MediaAsset.objects.count() == 1


def test_deleting_asset_removes_files(staff_user, django_capture_on_commit_callbacks):
    asset = media.process_upload(as_upload(make_image_bytes()), staff_user)
    paths = asset.all_paths()
    assert all(default_storage.exists(p) for p in paths)

    with django_capture_on_commit_callbacks(execute=True):
        asset.delete()

    assert not any(default_storage.exists(p) for p in paths)


def test_needs_consent(staff_user):
    asset = media.process_upload(as_upload(make_image_bytes()), staff_user)

    asset.has_people = True
    assert asset.needs_consent
    asset.consent_ok = True
    assert not asset.needs_consent
