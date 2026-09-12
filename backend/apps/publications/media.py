"""Processamento de imagens enviadas (docs/16 "Upload de imagens", docs/23 "Uploads").

1. Tamanho do arquivo (10 MB) e cota por usuário (1 GB).
2. Tipo real pelo conteúdo (Pillow), não pela extensão: só JPEG, PNG e WebP.
3. Dimensão máxima (6000 px) antes de decodificar, contra "bombas" de descompressão.
4. Aplica a rotação da câmera e reescreve o arquivo sem EXIF, GPS ou outros metadados.
5. Gera variantes WebP de 480, 960 e 1600 px de largura.
"""

import io
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.accounts.models import User

from .models import Article, MediaAsset

ALLOWED_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
WEBP_QUALITY = 82

# O Pillow recusa sozinho imagens com mais do que o dobro deste número de pixels.
Image.MAX_IMAGE_PIXELS = settings.MEDIA_MAX_DIMENSION * settings.MEDIA_MAX_DIMENSION


@dataclass
class MediaError(Exception):
    code: str
    message: str
    status: int = 400


def _check_quota(user: User, incoming: int) -> None:
    used = MediaAsset.objects.filter(uploaded_by=user).aggregate(total=Sum("size_bytes"))["total"]
    if (used or 0) + incoming > settings.MEDIA_USER_QUOTA_BYTES:
        raise MediaError("quota_exceeded", "Você atingiu o limite de espaço para imagens.", 413)


def _open_image(raw: bytes) -> Image.Image:
    try:
        probe = Image.open(io.BytesIO(raw))
        image_format = probe.format
        width, height = probe.size
        probe.verify()  # detecta arquivos truncados ou corrompidos
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise MediaError("invalid_image", "O arquivo não é uma imagem válida.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise MediaError("unsupported_type", "Envie uma imagem JPG, PNG ou WebP.")
    limit = settings.MEDIA_MAX_DIMENSION
    if width > limit or height > limit:
        raise MediaError(
            "too_large_dimensions", f"A imagem pode ter no máximo {limit} pixels de lado."
        )

    try:
        image = Image.open(io.BytesIO(raw))  # verify() inutiliza o objeto; abrir de novo
        image.load()  # decodifica tudo: pega JPEG truncado, que o verify() não detecta
    except (OSError, Image.DecompressionBombError) as exc:
        raise MediaError("invalid_image", "O arquivo não é uma imagem válida.") from exc
    return image


def _normalize(image: Image.Image) -> Image.Image:
    """Aplica a orientação do EXIF e deixa a imagem em um modo que qualquer formato grave."""
    image = ImageOps.exif_transpose(image)
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    return image.convert("RGBA" if has_alpha else "RGB")


def _encode(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    if image_format == "JPEG":
        image.convert("RGB").save(buffer, "JPEG", quality=90, optimize=True, progressive=True)
    elif image_format == "PNG":
        image.save(buffer, "PNG", optimize=True)
    else:
        image.save(buffer, "WEBP", quality=WEBP_QUALITY, method=4)
    return buffer.getvalue()


def _resize(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


@transaction.atomic
def process_upload(
    uploaded: UploadedFile, user: User, article: Article | None = None
) -> MediaAsset:
    if uploaded.size is None or uploaded.size > settings.MEDIA_MAX_UPLOAD_BYTES:
        max_mb = settings.MEDIA_MAX_UPLOAD_BYTES // (1024 * 1024)
        raise MediaError("file_too_large", f"A imagem pode ter no máximo {max_mb} MB.", 413)

    raw = uploaded.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
    if len(raw) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise MediaError("file_too_large", "Arquivo grande demais.", 413)

    source = _open_image(raw)
    image_format = source.format or ""
    extension, mime = ALLOWED_FORMATS[image_format]
    image = _normalize(source)

    original_bytes = _encode(image, image_format)
    variants_bytes = {
        f"w{width}": _encode(_resize(image, width), "WEBP") for width in MediaAsset.VARIANT_WIDTHS
    }
    total = len(original_bytes) + sum(len(b) for b in variants_bytes.values())
    _check_quota(user, total)

    folder = timezone.now().strftime("media/%Y/%m")
    name = uuid.uuid4().hex
    saved: list[str] = []
    try:
        original_path = default_storage.save(
            f"{folder}/{name}.{extension}", ContentFile(original_bytes)
        )
        saved.append(original_path)
        variants: dict[str, str] = {}
        for key, data in variants_bytes.items():
            path = default_storage.save(f"{folder}/{name}-{key}.webp", ContentFile(data))
            saved.append(path)
            variants[key] = path

        asset = MediaAsset(
            variants=variants,
            width=image.width,
            height=image.height,
            size_bytes=total,
            mime=mime,
            uploaded_by=user,
            article=article,
        )
        asset.file.name = original_path
        asset.save()
    except Exception:
        for path in saved:
            default_storage.delete(path)
        raise
    return asset


def serialize(asset: MediaAsset) -> dict:
    return {
        "id": asset.pk,
        "url": asset.url,
        "variants": asset.variant_urls,
        "srcset": asset.srcset,
        "width": asset.width,
        "height": asset.height,
        "alt_text": asset.alt_text,
        "is_decorative": asset.is_decorative,
        "credit": asset.credit,
        "license": asset.license,
        "has_people": asset.has_people,
        "consent_ok": asset.consent_ok,
    }
