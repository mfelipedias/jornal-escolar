import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Cada teste grava imagens numa pasta temporária."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def make_image_bytes(
    image_format: str = "JPEG",
    size: tuple[int, int] = (2000, 1200),
    mode: str = "RGB",
    exif: bytes | None = None,
    color=(200, 30, 80),
) -> bytes:
    buffer = io.BytesIO()
    image = Image.new(mode, size, color)
    kwargs = {"exif": exif} if exif else {}
    image.save(buffer, image_format, **kwargs)
    return buffer.getvalue()


def as_upload(data: bytes, name: str = "foto.jpg", content_type: str = "image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)
