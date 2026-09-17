from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import TeacherProfile, User
from apps.taxonomy.models import Discipline, Topic

from .cache import invalidate_public_content
from .models import Article, ArticleContributor, MediaAsset
from .search import update_search_vectors


@receiver(post_delete, sender=MediaAsset, dispatch_uid="publications_delete_media_files")
def delete_media_files(sender: type[MediaAsset], instance: MediaAsset, **kwargs: Any) -> None:
    """Apagar a imagem apaga o original e as variantes, depois que a transação confirmar."""
    paths = instance.all_paths()

    def remove() -> None:
        for path in paths:
            default_storage.delete(path)

    transaction.on_commit(remove)


def _bump() -> None:
    invalidate_public_content()


@receiver(post_save, sender=Article, dispatch_uid="publications_article_public_cache")
@receiver(post_delete, sender=Article, dispatch_uid="publications_article_public_cache_del")
def article_changed(sender: type[Article], instance: Article, **kwargs: Any) -> None:
    """Rascunho que nunca foi ao ar não muda nada no site público."""
    if instance.published_at:
        _bump()


@receiver(
    m2m_changed, sender=Article.disciplines.through, dispatch_uid="publications_disc_public_cache"
)
@receiver(
    m2m_changed, sender=Article.topics.through, dispatch_uid="publications_topic_public_cache"
)
def article_taxonomy_changed(instance: Any, **kwargs: Any) -> None:
    """Disciplinas e tópicos mudam listas, página de tópico e "Leia também"."""
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


@receiver(post_save, sender=TeacherProfile, dispatch_uid="publications_profile_public_cache")
def profile_changed(sender: type[TeacherProfile], instance: TeacherProfile, **kwargs) -> None:
    """Headline, endereço e "perfil público" aparecem em "Quem escreve" da home."""
    _bump()


@receiver(post_save, sender=User, dispatch_uid="publications_user_public_cache")
def user_changed(sender: type[User], instance: User, created: bool, **kwargs) -> None:
    """Nome, foto, cargo e ativação aparecem em "Quem escreve"; login sozinho não muda nada."""
    update_fields = kwargs.get("update_fields")
    if created or (update_fields is not None and set(update_fields) <= {"last_login", "password"}):
        return
    _bump()


@receiver(post_save, sender=Topic, dispatch_uid="publications_topic_public_cache_save")
def topic_changed(sender: type[Topic], instance: Topic, created: bool, **kwargs) -> None:
    """Nome e "ativo" do tópico aparecem nas etiquetas e na página de tópico."""
    if not created:
        _bump()


@receiver(post_save, sender=Discipline, dispatch_uid="publications_discipline_search")
@receiver(post_save, sender=Topic, dispatch_uid="publications_topic_search")
def taxonomy_renamed(sender: Any, instance: Any, created: bool, **kwargs) -> None:
    """Disciplina ou tópico renomeado no admin: o nome novo passa a valer na busca.

    As publicações em si são indexadas pelos services (apps/publications/search.py).
    """
    if created:
        return
    update_search_vectors(instance.articles.values_list("pk", flat=True))
