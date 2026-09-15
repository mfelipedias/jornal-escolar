from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from apps.accounts.models import User

from . import services
from .models import Comment


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


@receiver(post_delete, sender=Comment, dispatch_uid="engagement_comment_deleted_recount")
def comment_deleted(sender: type[Comment], instance: Comment, **kwargs: Any) -> None:
    """Comentário apagado (admin, limpeza): refaz o total de aprovados da publicação.

    Na exclusão em cascata da própria publicação o update não encontra nada, sem erro.
    """
    if instance.status != Comment.Status.APPROVED:
        return
    article_id = instance.article_id
    transaction.on_commit(lambda: services.recount_comments(article_id))
