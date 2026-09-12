from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .cache import bump_public_version
from .models import Article, ArticleContributor, MediaAsset


@receiver(post_delete, sender=MediaAsset, dispatch_uid="publications_delete_media_files")
def delete_media_files(sender: type[MediaAsset], instance: MediaAsset, **kwargs: Any) -> None:
    """Apagar a imagem apaga o original e as variantes, depois que a transação confirmar."""
    paths = instance.all_paths()

    def remove() -> None:
        for path in paths:
            default_storage.delete(path)

    transaction.on_commit(remove)


def _bump() -> None:
    # Agora e de novo depois do commit: quem remontar o cache no meio da transação
    # não deixa guardada a versão antiga.
    bump_public_version()
    transaction.on_commit(bump_public_version)


@receiver(post_save, sender=Article, dispatch_uid="publications_article_public_cache")
@receiver(post_delete, sender=Article, dispatch_uid="publications_article_public_cache_del")
def article_changed(sender: type[Article], instance: Article, **kwargs: Any) -> None:
    """Rascunho que nunca foi ao ar não muda nada no site público."""
    if instance.published_at:
        _bump()


@receiver(
    m2m_changed, sender=Article.disciplines.through, dispatch_uid="publications_disc_public_cache"
)
def article_disciplines_changed(instance: Any, **kwargs: Any) -> None:
    if isinstance(instance, Article) and instance.published_at:
        _bump()


@receiver(post_save, sender=ArticleContributor, dispatch_uid="publications_credit_public_cache")
@receiver(
    post_delete, sender=ArticleContributor, dispatch_uid="publications_credit_public_cache_del"
)
def credit_changed(
    sender: type[ArticleContributor], instance: ArticleContributor, **kwargs
) -> None:
    if Article.objects.filter(pk=instance.article_id, published_at__isnull=False).exists():
        _bump()
