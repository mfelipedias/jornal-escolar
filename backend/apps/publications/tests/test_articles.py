from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.core.models import SiteSetting
from apps.publications import services
from apps.publications.credits import student_name_error
from apps.publications.models import Article, ArticleContributor, ArticleRevision, MediaAsset
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db


def codes(article):
    return {item.code for item in services.checklist(article) if item.blocking}


# --- criar e editar ---


def test_create_article_makes_creator_author(staff_user):
    article = services.create_article(staff_user)

    assert article.status == Article.Status.DRAFT
    assert article.title == "Sem título"
    assert article.slug is None
    contributor = article.contributors.get()
    assert contributor.user == staff_user
    assert contributor.role == ArticleContributor.Role.AUTHOR
    assert contributor.display_name == staff_user.public_name


def test_anonymous_cannot_create():
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(PermissionDenied):
        services.create_article(AnonymousUser())


def test_update_rejects_unknown_fields(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(ValueError, match="status"):
        services.update_article(staff_user, article, status="published")


def test_update_by_other_staff_is_denied(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(PermissionDenied):
        services.update_article(UserFactory(), article, title="Invasão")


def test_title_limit(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(ValidationError):
        services.update_article(staff_user, article, title="x" * 121)


def test_stale_object_cannot_unpublish(staff_user, editor_user):
    """Regressão: salvar com uma cópia antiga em memória não pode desfazer a publicação."""
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    stale = Article.objects.get(pk=article.pk)  # carregado ainda como rascunho
    services.publish(editor_user, article)

    services.update_article(staff_user, stale, subtitle="Editado com cópia antiga")

    fresh = Article.objects.get(pk=article.pk)
    assert fresh.status == Article.Status.PUBLISHED
    assert fresh.subtitle == "Editado com cópia antiga"
    assert stale.status == Article.Status.PUBLISHED


def test_editing_draft_does_not_create_revision(staff_user):
    article = services.create_article(staff_user)

    services.update_article(staff_user, article, title="Novo título")

    assert not article.revisions.exists()


# --- checklist ---


def test_checklist_of_empty_draft(staff_user):
    article = services.create_article(staff_user)

    assert codes(article) == {"title_missing", "discipline_missing", "type_missing", "body_empty"}


def test_ready_article_passes_checklist():
    article = ArticleFactory(ready=True)

    assert codes(article) == set()


def test_event_type_requires_date():
    article = ArticleFactory(ready=True)
    article.type = ArticleTypeFactory(has_event_date=True)
    article.save()

    assert "event_date_missing" in codes(article)
    article.event_at = timezone.now() + timedelta(days=3)
    article.save()
    assert "event_date_missing" not in codes(article)


def test_whitespace_body_is_empty():
    article = ArticleFactory(ready=True, body_json=text_doc("   "))

    assert "body_empty" in codes(article)


def test_student_without_consent_blocks(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.add_student_credit(staff_user, article, name="Rafael S.", class_group="2ª B")

    assert "student_consent_missing" in codes(article)


def test_image_with_people_without_consent_blocks(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    asset = MediaAsset.objects.create(
        uploaded_by=staff_user,
        width=10,
        height=10,
        size_bytes=1,
        mime="image/jpeg",
        has_people=True,
    )
    article.body_json = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Oi"}]},
            {"type": "figure", "attrs": {"assetId": asset.pk}},
        ],
    }
    article.save()

    assert "image_consent_missing" in codes(article)
    asset.consent_ok = True
    asset.save()
    assert "image_consent_missing" not in codes(article)


def test_cover_with_people_without_consent_blocks(staff_user):
    article = ArticleFactory(ready=True)
    article.cover = MediaAsset.objects.create(
        uploaded_by=staff_user, width=1, height=1, size_bytes=1, mime="image/jpeg", has_people=True
    )
    article.save()

    items = {item.code: item for item in services.checklist(article)}
    assert items["image_consent_missing"].blocking
    assert not items["cover_alt_missing"].blocking


def test_missing_subtitle_is_only_a_warning():
    article = ArticleFactory(ready=True, subtitle="")

    items = {item.code: item for item in services.checklist(article)}
    assert not items["subtitle_missing"].blocking
    assert codes(article) == set()


# --- publicar ---


def test_author_publishes_own_article(staff_user):
    article = ArticleFactory(
        ready=True, author=staff_user, created_by=staff_user, title="Feira de Ciências 2026"
    )

    services.publish(staff_user, article)

    article.refresh_from_db()
    assert article.status == Article.Status.PUBLISHED
    assert article.slug == "feira-de-ciencias-2026"
    assert article.published_at is not None
    assert article.revisions.get().reason == ArticleRevision.Reason.PUBLISHED


def test_staff_cannot_publish_others_article(staff_user):
    article = ArticleFactory(ready=True)

    with pytest.raises(PermissionDenied):
        services.publish(staff_user, article)


def test_editor_publishes_any_article(editor_user):
    article = ArticleFactory(ready=True)

    services.publish(editor_user, article)

    assert Article.objects.get(pk=article.pk).is_published


def test_publish_blocked_by_checklist(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(services.ChecklistError) as exc:
        services.publish(staff_user, article)

    assert {item.code for item in exc.value.items} >= {"title_missing", "body_empty"}
    assert Article.objects.get(pk=article.pk).status == Article.Status.DRAFT


def test_slugs_are_unique_and_permanent(editor_user):
    first = ArticleFactory(ready=True, title="Mesmo título")
    second = ArticleFactory(ready=True, title="Mesmo título")
    services.publish(editor_user, first)
    services.publish(editor_user, second)
    second.refresh_from_db()
    assert second.slug == "mesmo-titulo-2"

    services.update_article(editor_user, second, title="Título mudou")

    second.refresh_from_db()
    assert second.slug == "mesmo-titulo-2"


def test_editing_published_creates_revision(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)

    services.update_article(staff_user, article, subtitle="Linha fina corrigida")

    reasons = list(article.revisions.order_by("number").values_list("reason", flat=True))
    assert reasons == ["published", "edited_after_publish"]
    assert article.revisions.first().number == 2


def test_self_publish_never_setting(staff_user):
    SiteSetting.objects.create(key="editorial.self_publish", value="never")
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)

    with pytest.raises(PermissionDenied):
        services.publish(staff_user, article)


# --- arquivar e restaurar ---


def test_author_archives_and_restores(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)

    services.archive(staff_user, article)
    article.refresh_from_db()
    assert article.status == Article.Status.ARCHIVED
    assert article.archived_at is not None

    services.restore(staff_user, article)
    article.refresh_from_db()
    assert article.status == Article.Status.DRAFT
    assert article.slug  # continua reservado para a republicação


def test_editor_needs_note_to_archive_others_text(editor_user):
    article = ArticleFactory(ready=True)
    services.publish(editor_user, article)

    with pytest.raises(ValidationError):
        services.archive(editor_user, article)
    services.archive(editor_user, article, note="Dados pessoais expostos.")

    assert Article.objects.get(pk=article.pk).status == Article.Status.ARCHIVED


def test_republish_keeps_original_date(editor_user):
    article = ArticleFactory(ready=True)
    services.publish(editor_user, article)
    first_date = Article.objects.get(pk=article.pk).published_at
    services.archive(editor_user, article, note="Revisão")
    services.restore(editor_user, article)

    services.publish(editor_user, article)

    assert Article.objects.get(pk=article.pk).published_at == first_date


def test_archiving_removes_featured(editor_user):
    article = ArticleFactory(ready=True, is_featured=True)
    services.publish(editor_user, article)

    services.archive(editor_user, article, note="Fim do destaque")

    assert not Article.objects.get(pk=article.pk).is_featured


# --- créditos ---


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("Rafael S.", True),
        ("Ana Clara M.", True),
        ("João P.", True),
        ("Rafael Souza", False),
        ("rafael s.", False),
        ("Rafael", False),
        ("", False),
    ],
)
def test_student_name_policy(name, ok):
    assert (student_name_error(name) is None) is ok


def test_full_name_allowed_with_explicit_authorization():
    assert student_name_error("Rafael Souza", full_name_authorized=True) is None


def test_full_name_policy_setting():
    SiteSetting.objects.create(key="credits.student_name_policy", value="full")

    assert student_name_error("Rafael Souza Lima") is None


def test_add_student_credit_validates_name(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(ValidationError):
        services.add_student_credit(staff_user, article, name="Rafael Souza")

    credit = services.add_student_credit(
        staff_user, article, name=" Rafael  S. ", class_group="2ª série B", consent_ok=True
    )
    assert credit.display_name == "Rafael S."
    assert credit.is_student
    assert credit.user is None


def test_staff_credit_freezes_name(staff_user):
    article = services.create_article(staff_user)
    colleague = UserFactory(full_name="Bruno Lima")

    credit = services.add_staff_credit(staff_user, article, colleague)
    colleague.full_name = "Bruno Lima Souza"
    colleague.save()

    credit.refresh_from_db()
    assert credit.display_name == "Bruno Lima"
    assert services.add_staff_credit(staff_user, article, colleague) == credit


def test_student_credit_cannot_have_user(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(IntegrityError):
        ArticleContributor.objects.create(
            article=article, user=staff_user, display_name="X", is_student=True
        )


def test_other_staff_cannot_edit_credits(staff_user):
    article = services.create_article(staff_user)

    with pytest.raises(PermissionDenied):
        services.add_student_credit(UserFactory(), article, name="Rafael S.")


def test_disciplines_via_factory():
    discipline = DisciplineFactory(name="Física", slug="fisica")
    article = ArticleFactory(ready=True, disciplines=[discipline])

    assert list(article.disciplines.all()) == [discipline]


def test_admin_article_pages(admin_client):
    from django.urls import reverse

    article = ArticleFactory(ready=True)

    assert admin_client.get(reverse("admin:publications_article_changelist")).status_code == 200
    assert (
        admin_client.get(
            reverse("admin:publications_article_change", args=[article.pk])
        ).status_code
        == 200
    )
