"""Matriz de permissões da E12 (docs/02). Cada linha: quem, estado, ação, resultado."""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.core.models import SiteSetting
from apps.editorial import permissions as p
from apps.publications.models import Article, ArticleContributor
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

D, P, A = Article.Status.DRAFT, Article.Status.PUBLISHED, Article.Status.ARCHIVED


@pytest.fixture
def people():
    author = UserFactory()
    return {
        "anon": AnonymousUser(),
        "author": author,
        "coauthor": UserFactory(),
        "collaborator": UserFactory(),
        "other_staff": UserFactory(),
        "editor": UserFactory(editor=True),
        "admin": UserFactory(admin=True),
        "inactive_author": UserFactory(is_active=False),
    }


def article_for(people, status):
    article = ArticleFactory(author=people["author"], created_by=people["author"], status=status)
    ArticleContributor.objects.create(
        article=article, user=people["coauthor"], display_name="Co", role="coauthor"
    )
    ArticleContributor.objects.create(
        article=article, user=people["collaborator"], display_name="Col", role="collaborator"
    )
    ArticleContributor.objects.create(
        article=article, user=people["inactive_author"], display_name="Ex", role="author"
    )
    return article


MATRIX = [
    # (quem, estado, função, esperado)
    ("anon", P, "can_view", True),
    ("anon", D, "can_view", False),
    ("other_staff", D, "can_view", False),
    ("collaborator", D, "can_view", False),
    ("author", D, "can_view", True),
    ("editor", D, "can_view", True),
    ("anon", D, "can_edit", False),
    ("author", D, "can_edit", True),
    ("coauthor", D, "can_edit", True),
    ("collaborator", D, "can_edit", False),
    ("other_staff", D, "can_edit", False),
    ("inactive_author", D, "can_edit", False),
    ("editor", D, "can_edit", True),
    ("admin", D, "can_edit", True),
    ("author", P, "can_edit", True),
    ("other_staff", P, "can_edit", False),
    # Aceite da E12: staff publica o próprio, não publica alheio, editor publica qualquer.
    ("author", D, "can_publish", True),
    ("coauthor", D, "can_publish", True),
    ("other_staff", D, "can_publish", False),
    ("collaborator", D, "can_publish", False),
    ("editor", D, "can_publish", True),
    ("admin", D, "can_publish", True),
    ("anon", D, "can_publish", False),
    ("author", P, "can_publish", False),
    ("author", A, "can_publish", False),
    ("editor", A, "can_publish", True),
    ("author", P, "can_archive", True),
    ("author", D, "can_archive", True),
    ("other_staff", P, "can_archive", False),
    ("editor", P, "can_archive", True),
    ("author", A, "can_archive", False),
    ("author", A, "can_restore", True),
    ("other_staff", A, "can_restore", False),
    ("editor", A, "can_restore", True),
    ("author", D, "can_restore", False),
    ("author", D, "can_edit_credits", True),
    ("other_staff", D, "can_edit_credits", False),
]


@pytest.mark.parametrize(("who", "status", "func", "expected"), MATRIX)
def test_matrix(people, who, status, func, expected):
    article = article_for(people, status)

    assert getattr(p, func)(people[who], article) is expected


def test_create_article(people):
    assert p.can_create_article(people["other_staff"])
    assert not p.can_create_article(people["anon"])
    assert not p.can_create_article(people["inactive_author"])


def test_feature_only_editors(people):
    assert p.can_feature(people["editor"])
    assert p.can_feature(people["admin"])
    assert not p.can_feature(people["author"])


def test_archive_note_required_only_for_editor_on_others_text(people):
    article = article_for(people, P)

    assert p.archive_requires_note(people["editor"], article)
    assert not p.archive_requires_note(people["author"], article)
    editor_article = ArticleFactory(author=people["editor"], created_by=people["editor"])
    assert not p.archive_requires_note(people["editor"], editor_article)


def test_self_publish_never_blocks_staff_but_not_editors(people):
    SiteSetting.objects.create(key="editorial.self_publish", value="never")
    article = article_for(people, D)

    assert not p.can_publish(people["author"], article)
    assert p.can_publish(people["editor"], article)


def test_media_permissions(people):
    from apps.publications.models import MediaAsset

    asset = MediaAsset(
        uploaded_by=people["author"], width=1, height=1, size_bytes=1, mime="image/png"
    )

    assert p.can_edit_media(people["author"], asset)
    assert not p.can_edit_media(people["other_staff"], asset)
    assert p.can_edit_media(people["editor"], asset)
    assert not p.can_edit_media(people["anon"], asset)
    asset.article = article_for(people, D)
    assert p.can_edit_media(people["coauthor"], asset)
