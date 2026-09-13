from typing import Any

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .context_processors import NAV_AREAS_KEY
from .models import KnowledgeArea


@receiver(post_save, sender=KnowledgeArea, dispatch_uid="taxonomy_nav_areas_save")
@receiver(post_delete, sender=KnowledgeArea, dispatch_uid="taxonomy_nav_areas_delete")
def area_changed(**kwargs: Any) -> None:
    """Nome, ordem, cor ou ativação mudaram: o cabeçalho remonta a lista."""
    cache.delete(NAV_AREAS_KEY)
