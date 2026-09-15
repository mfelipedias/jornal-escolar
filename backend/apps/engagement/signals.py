from typing import Any

from django.db import transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.accounts.models import User

from . import services


@receiver(pre_delete, sender=User, dispatch_uid="engagement_user_reactions_recount")
def user_deleted(sender: type[User], instance: User, **kwargs: Any) -> None:
    """Conta apagada leva as reações junto (CASCADE): refaz o total dessas publicações."""
    article_ids = list(instance.reactions.values_list("article_id", flat=True))
    if not article_ids:
        return

    def refresh() -> None:
        for article_id in article_ids:
            services.recount(article_id)

    transaction.on_commit(refresh)
