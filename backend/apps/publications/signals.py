from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import MediaAsset


@receiver(post_delete, sender=MediaAsset, dispatch_uid="publications_delete_media_files")
def delete_media_files(sender: type[MediaAsset], instance: MediaAsset, **kwargs: Any) -> None:
    """Apagar a imagem apaga o original e as variantes, depois que a transação confirmar."""
    paths = instance.all_paths()

    def remove() -> None:
        for path in paths:
            default_storage.delete(path)

    transaction.on_commit(remove)
