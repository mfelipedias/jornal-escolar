"""Única fonte das regras de permissão editorial (docs/02 "Matriz de permissões", docs/04).

Views, templates e testes usam estas funções; nenhuma regra é repetida em outro lugar.
Todas recebem o usuário (pode ser anônimo) e devolvem bool.

Na E12 cobre rascunho, publicado e arquivado. Revisor designado entra na E30.
"""

from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import User
from apps.core.site_settings import get_setting
from apps.publications.models import Article, ArticleContributor, MediaAsset

AnyUser = User | AnonymousUser


def is_staff_member(user: AnyUser) -> bool:
    """Tem conta ativa na equipe (qualquer papel)."""
    return bool(user.is_authenticated and user.is_active)


def is_editor(user: AnyUser) -> bool:
    """Editor ou admin: papéis são hierárquicos (admin ⊃ editor ⊃ staff)."""
    return is_staff_member(user) and user.role in (User.Role.EDITOR, User.Role.ADMIN)


def is_admin(user: AnyUser) -> bool:
    return is_staff_member(user) and user.role == User.Role.ADMIN


def is_author(user: AnyUser, article: Article) -> bool:
    """Autor ou coautor da publicação: os dois têm as mesmas permissões de edição."""
    if not is_staff_member(user):
        return False
    return article.contributors.filter(
        user=user, role__in=ArticleContributor.EDITING_ROLES
    ).exists()


def can_create_article(user: AnyUser) -> bool:
    return is_staff_member(user)


def can_view(user: AnyUser, article: Article) -> bool:
    """Publicado: todo mundo. Rascunho e arquivado: autores e editores."""
    if article.status == Article.Status.PUBLISHED:
        return True
    return is_editor(user) or is_author(user, article)


def can_edit(user: AnyUser, article: Article) -> bool:
    return is_editor(user) or is_author(user, article)


def can_publish(user: AnyUser, article: Article) -> bool:
    if article.status == Article.Status.PUBLISHED:
        return False
    if is_editor(user):
        return True
    # "never" (reservado): toda publicação precisa de outra pessoa (docs/02, "Política editorial").
    if get_setting("editorial.self_publish") == "never":
        return False
    return article.status == Article.Status.DRAFT and is_author(user, article)


def can_archive(user: AnyUser, article: Article) -> bool:
    if article.status == Article.Status.ARCHIVED:
        return False
    return is_editor(user) or is_author(user, article)


def archive_requires_note(user: AnyUser, article: Article) -> bool:
    """Editor ou admin arquivando texto alheio precisa explicar o motivo."""
    return is_editor(user) and not is_author(user, article)


def can_restore(user: AnyUser, article: Article) -> bool:
    if article.status != Article.Status.ARCHIVED:
        return False
    return is_editor(user) or is_author(user, article)


def can_edit_credits(user: AnyUser, article: Article) -> bool:
    return can_edit(user, article)


def can_upload_media(user: AnyUser) -> bool:
    return is_staff_member(user)


def can_edit_media(user: AnyUser, asset: MediaAsset) -> bool:
    """Metadados da imagem: quem enviou, autores da publicação onde ela está, ou editor."""
    if is_editor(user):
        return True
    if not is_staff_member(user):
        return False
    if asset.uploaded_by_id == user.pk:
        return True
    return asset.article_id is not None and is_author(user, asset.article)


def can_feature(user: AnyUser) -> bool:
    """Definir destaques da home."""
    return is_editor(user)
