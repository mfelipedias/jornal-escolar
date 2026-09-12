import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.publications import services
from apps.publications.models import Article, ArticleContributor
from tests.factories import (
    ArticleFactory,
    ArticleTypeFactory,
    DisciplineFactory,
    UserFactory,
    text_doc,
)

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def draft(staff_user):
    return services.create_article(staff_user)


@pytest.fixture
def author_client(client, staff_user):
    client.force_login(staff_user)
    return client


# --- conflito e versões (ajustes da E15) ---


def test_own_parallel_saves_do_not_conflict(staff_user, draft):
    loaded = draft.updated_at
    services.set_metadata(
        staff_user,
        draft,
        type_id=None,
        discipline_ids=[],
        topic_ids=[],
        event_at=None,
        event_location="",
        sources=[],
    )

    services.update_article(staff_user, draft, expected_updated_at=loaded, title="Sem conflito")

    assert Article.objects.get(pk=draft.pk).title == "Sem conflito"


def test_other_person_still_conflicts(staff_user, editor_user, draft):
    loaded = draft.updated_at
    services.update_article(editor_user, draft, subtitle="Editor")

    with pytest.raises(services.ConflictError):
        services.update_article(staff_user, draft, expected_updated_at=loaded, title="Autor")


def test_autosaves_of_published_text_share_one_revision(staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)

    for i in range(5):
        services.update_article(staff_user, article, body_json=text_doc(f"versão {i}"))

    revisions = list(article.revisions.order_by("number"))
    assert [r.reason for r in revisions] == ["published", "edited_after_publish"]
    assert "versão 4" in json.dumps(revisions[-1].body_json, ensure_ascii=False)


def test_new_revision_after_window_or_other_editor(staff_user, editor_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)
    services.update_article(staff_user, article, subtitle="a")
    article.revisions.filter(reason="edited_after_publish").update(
        created_at=timezone.now() - timedelta(minutes=20)
    )

    services.update_article(staff_user, article, subtitle="b")
    services.update_article(editor_user, article, subtitle="c")

    assert article.revisions.count() == 4


# --- metadados ---


def test_set_metadata(staff_user, draft):
    event_type = ArticleTypeFactory(has_event_date=True)
    physics, math = DisciplineFactory(), DisciplineFactory()
    when = timezone.now() + timedelta(days=5)

    services.set_metadata(
        staff_user,
        draft,
        type_id=event_type.pk,
        discipline_ids=[physics.pk, math.pk],
        topic_ids=[],
        event_at=when,
        event_location="Quadra",
        sources=[
            {"title": "INEP", "url": "https://www.gov.br/inep", "publisher": "Gov"},
            {"title": "", "url": ""},
        ],
        comments_enabled=False,
    )

    draft.refresh_from_db()
    assert draft.type == event_type
    assert set(draft.disciplines.all()) == {physics, math}
    assert draft.event_at == when
    assert draft.event_location == "Quadra"
    assert draft.sources == [
        {"title": "INEP", "url": "https://www.gov.br/inep", "publisher": "Gov"}
    ]
    assert not draft.comments_enabled


def test_event_fields_cleared_for_non_event_type(staff_user, draft):
    services.set_metadata(
        staff_user,
        draft,
        type_id=ArticleTypeFactory(has_event_date=False).pk,
        discipline_ids=[],
        topic_ids=[],
        event_at=timezone.now(),
        event_location="Quadra",
        sources=[],
    )

    draft.refresh_from_db()
    assert draft.event_at is None
    assert draft.event_location == ""


def test_inactive_taxonomy_is_ignored(staff_user, draft):
    inactive = DisciplineFactory(is_active=False)

    services.set_metadata(
        staff_user,
        draft,
        type_id=None,
        discipline_ids=[inactive.pk],
        topic_ids=[],
        event_at=None,
        event_location="",
        sources=[],
    )

    assert not draft.disciplines.exists()


@pytest.mark.parametrize(
    "source",
    [
        {"title": "", "url": "https://a.com"},
        {"title": "X", "url": "javascript:alert(1)"},
        {"title": "X", "url": "/interno"},
    ],
)
def test_invalid_sources(source):
    with pytest.raises(ValidationError):
        services.clean_sources([source])


# --- créditos ---


def test_guest_credit(staff_user, draft):
    credit = services.add_guest_credit(
        staff_user, draft, name=" Grêmio  Estudantil ", contribution_note="fotos"
    )

    assert credit.display_name == "Grêmio Estudantil"
    assert credit.role == ArticleContributor.Role.COLLABORATOR
    assert credit.user is None


def test_guest_cannot_be_reviewer(staff_user, draft):
    with pytest.raises(ValidationError):
        services.add_guest_credit(staff_user, draft, name="X", role="reviewer")


def test_cannot_remove_last_staff_author(staff_user, draft):
    only_author = draft.contributors.get()

    with pytest.raises(ValidationError):
        services.remove_credit(staff_user, draft, only_author)


def test_can_remove_author_when_another_staff_author_exists(staff_user, draft):
    services.add_staff_credit(staff_user, draft, UserFactory(), role="coauthor")
    original = draft.contributors.get(user=staff_user)

    services.remove_credit(staff_user, draft, original)

    assert not draft.contributors.filter(pk=original.pk).exists()


def test_student_credit_can_be_removed(staff_user, draft):
    student = services.add_student_credit(staff_user, draft, name="Rafael S.", consent_ok=True)

    services.remove_credit(staff_user, draft, student)

    assert not draft.contributors.filter(is_student=True).exists()


# --- endpoints ---


def test_editor_page_has_sidebar(author_client, draft):
    html = author_client.get(reverse("publications:edit", args=[draft.pk])).content.decode()

    assert 'id="editor-meta"' in html
    assert 'id="editor-credits"' in html
    assert 'id="editor-checklist"' in html
    assert "Dê um título à publicação." in html
    assert "Publicar" in html


def test_meta_endpoint_saves_and_returns_fragments(author_client, draft):
    discipline = DisciplineFactory()
    article_type = ArticleTypeFactory()

    response = author_client.post(
        reverse("publications:save_meta", args=[draft.pk]),
        {
            "type": str(article_type.pk),
            "disciplines": [str(discipline.pk)],
            "source_title": ["Fonte"],
            "source_url": ["https://exemplo.org"],
            "source_publisher": [""],
            "comments_enabled": "on",
        },
        **HTMX,
    )

    html = response.content.decode()
    assert response.status_code == 200
    assert 'id="editor-meta"' in html
    assert 'id="editor-checklist"' in html
    assert 'hx-swap-oob="true"' in html
    trigger = json.loads(response["HX-Trigger"])
    draft.refresh_from_db()
    assert trigger["articleUpdated"]["updatedAt"] == draft.updated_at.isoformat()
    assert draft.type == article_type
    assert "Escolha ao menos uma disciplina." not in html


def test_meta_endpoint_shows_source_errors(author_client, draft):
    response = author_client.post(
        reverse("publications:save_meta", args=[draft.pk]),
        {"source_title": [""], "source_url": ["https://x.org"], "source_publisher": [""]},
        **HTMX,
    )

    assert "informe o título" in response.content.decode()


def test_meta_event_datetime_local(author_client, draft):
    event_type = ArticleTypeFactory(has_event_date=True)

    author_client.post(
        reverse("publications:save_meta", args=[draft.pk]),
        {"type": str(event_type.pk), "event_at": "2026-10-05T19:30", "event_location": "Auditório"},
        **HTMX,
    )

    draft.refresh_from_db()
    assert timezone.localtime(draft.event_at).strftime("%d/%m %H:%M") == "05/10 19:30"


def test_meta_denied_to_other_staff(client, draft):
    client.force_login(UserFactory())

    response = client.post(reverse("publications:save_meta", args=[draft.pk]), {}, **HTMX)

    assert response.status_code == 403


def test_add_student_via_endpoint_with_error(author_client, draft):
    response = author_client.post(
        reverse("publications:add_contributor", args=[draft.pk]),
        {"kind": "student", "name": "Rafael Souza", "class_group": "2ª B"},
        **HTMX,
    )

    html = response.content.decode()
    assert "Use primeiro nome e inicial" in html
    assert 'value="Rafael Souza"' in html
    assert not draft.contributors.filter(is_student=True).exists()


def test_add_student_via_endpoint(author_client, draft):
    author_client.post(
        reverse("publications:add_contributor", args=[draft.pk]),
        {"kind": "student", "name": "Rafael S.", "class_group": "2ª B", "consent_ok": "on"},
        **HTMX,
    )

    credit = draft.contributors.get(is_student=True)
    assert credit.consent_ok
    assert credit.class_group == "2ª B"


def test_add_staff_via_search_and_endpoint(author_client, draft):
    colleague = UserFactory(full_name="Bruno Lima")

    search = author_client.get(
        reverse("publications:search_users"), {"q": "brun", "article": draft.pk}, **HTMX
    ).content.decode()
    assert "Bruno Lima" in search

    author_client.post(
        reverse("publications:add_contributor", args=[draft.pk]),
        {"kind": "staff", "user_id": colleague.pk, "staff_role": "collaborator"},
        **HTMX,
    )
    assert draft.contributors.get(user=colleague).role == "collaborator"

    search_again = author_client.get(
        reverse("publications:search_users"), {"q": "brun", "article": draft.pk}, **HTMX
    ).content.decode()
    assert "Bruno Lima" not in search_again


def test_search_ignores_inactive_and_short_queries(author_client, draft):
    UserFactory(full_name="Inativa Silva", is_active=False)
    url = reverse("publications:search_users")

    assert (
        "Inativa" not in author_client.get(url, {"q": "inat", "article": draft.pk}).content.decode()
    )
    assert "<li>" not in author_client.get(url, {"q": "a", "article": draft.pk}).content.decode()


def test_remove_contributor_endpoint(author_client, staff_user, draft):
    guest = services.add_guest_credit(staff_user, draft, name="Convidado")

    response = author_client.delete(
        reverse("publications:remove_contributor", args=[draft.pk, guest.pk]), **HTMX
    )

    assert response.status_code == 200
    assert not draft.contributors.filter(pk=guest.pk).exists()


def test_remove_last_author_shows_error(author_client, draft):
    only = draft.contributors.get()

    response = author_client.delete(
        reverse("publications:remove_contributor", args=[draft.pk, only.pk]), **HTMX
    )

    assert "ao menos um autor" in response.content.decode()


def test_publish_endpoint_success(author_client, staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)

    response = author_client.post(
        reverse("publications:transition", args=[article.pk, "publish"]), **HTMX
    )

    assert response.status_code == 204
    assert response["HX-Redirect"] == reverse("publications:edit", args=[article.pk])
    assert Article.objects.get(pk=article.pk).is_published
    page = author_client.get(response["HX-Redirect"]).content.decode()
    assert "Publicado!" in page


def test_publish_endpoint_blocked_by_checklist(author_client, draft):
    response = author_client.post(reverse("publications:transition", args=[draft.pk, "publish"]))

    assert response.status_code == 302
    assert Article.objects.get(pk=draft.pk).status == Article.Status.DRAFT
    assert "Ainda falta" in author_client.get(response.url).content.decode()


def test_publish_endpoint_denied_to_other_staff(client):
    article = ArticleFactory(ready=True)
    client.force_login(UserFactory())

    response = client.post(reverse("publications:transition", args=[article.pk, "publish"]))

    assert response.status_code == 403


def test_archive_and_restore_endpoints(author_client, staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    services.publish(staff_user, article)

    author_client.post(reverse("publications:transition", args=[article.pk, "archive"]))
    assert Article.objects.get(pk=article.pk).status == Article.Status.ARCHIVED

    author_client.post(reverse("publications:transition", args=[article.pk, "restore"]))
    assert Article.objects.get(pk=article.pk).status == Article.Status.DRAFT


def test_unknown_transition(author_client, draft):
    response = author_client.post(reverse("publications:transition", args=[draft.pk, "explode"]))

    assert response.status_code == 404


def test_checklist_endpoint(author_client, draft):
    response = author_client.get(reverse("publications:checklist", args=[draft.pk]), **HTMX)

    html = response.content.decode()
    assert 'id="editor-checklist"' in html
    assert 'id="editor-actions"' in html
