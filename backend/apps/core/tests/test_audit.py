"""AuditLog (docs/23, "Auditoria"; E34): gravação, IP com hash e ações sensíveis auditadas."""

from datetime import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AccessLink, User
from apps.core import audit, services
from apps.core.models import AuditLog, SiteSetting, StaticPage
from apps.publications import services as article_services
from apps.publications.models import Article, MediaAsset
from tests.factories import DEFAULT_PASSWORD, ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

A = AuditLog.Action


def logs(action):
    return AuditLog.objects.filter(action=action)


# --- gravação ---


def test_ip_is_hashed_with_monthly_salt(rf, admin_user):
    request = rf.get("/", REMOTE_ADDR="203.0.113.7")

    log = audit.record(A.ROLE_CHANGED, actor=admin_user, target=admin_user, request=request)

    assert "203.0.113.7" not in log.ip_hash
    assert len(log.ip_hash) == 64
    september = timezone.make_aware(datetime(2026, 9, 14))
    october = timezone.make_aware(datetime(2026, 10, 1))
    assert audit.hash_ip("203.0.113.7", september) == audit.hash_ip("203.0.113.7", september)
    assert audit.hash_ip("203.0.113.7", september) != audit.hash_ip("203.0.113.7", october)
    assert audit.hash_ip("", september) == ""


def test_record_identifies_target_by_type_and_id(admin_user, staff_user):
    log = audit.record(A.USER_DEACTIVATED, actor=admin_user, target=staff_user)

    assert (log.target_type, log.target_id) == ("accounts.user", str(staff_user.pk))
    assert list(audit.for_target(staff_user)) == [log]


def test_login_is_audited(client):
    user = UserFactory(email="ana@escola.sp.gov.br")

    client.post("/entrar/", {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD})

    log = logs(A.LOGIN).get()
    assert log.actor == user
    assert log.ip_hash  # o cliente de teste manda REMOTE_ADDR 127.0.0.1


# --- Django Admin ---


def test_admin_role_change_and_deactivation_are_audited(admin_client, admin_user):
    person = UserFactory(full_name="Paula Reis")
    url = reverse("admin:accounts_user_change", args=[person.pk])
    data = {
        "email": person.email,
        "full_name": person.full_name,
        "display_name": "",
        "staff_kind": person.staff_kind,
        "role": User.Role.EDITOR,
        "is_active": "",
        "profile-TOTAL_FORMS": "1",
        "profile-INITIAL_FORMS": "1",
        "profile-0-id": person.profile.pk,
        "profile-0-user": person.pk,
        "profile-0-slug": person.profile.slug,
        "profile-0-is_public": "on",
    }

    response = admin_client.post(url, data)

    assert response.status_code == 302, response.content.decode()[:2000]
    role = logs(A.ROLE_CHANGED).get()
    assert role.actor == admin_user
    assert role.changes == {"role": ["staff", "editor"]}
    assert logs(A.USER_DEACTIVATED).get().target_id == str(person.pk)
    person.refresh_from_db()
    assert person.deactivated_at is not None
    assert "Paula" not in str(list(AuditLog.objects.values_list("changes", flat=True)))


def test_admin_user_creation_is_audited(admin_client):
    admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "email": "novo@escola.sp.gov.br",
            "full_name": "Novo Professor",
            "role": User.Role.STAFF,
            "staff_kind": User.StaffKind.TEACHER,
            "usable_password": "false",
        },
    )

    log = logs(A.USER_CREATED).get()
    assert log.target_id == str(User.objects.get(email="novo@escola.sp.gov.br").pk)


def test_admin_actions_are_audited(admin_client, staff_user):
    changelist = reverse("admin:accounts_user_changelist")

    admin_client.post(
        changelist, {"action": "generate_access_links", "_selected_action": [staff_user.pk]}
    )
    admin_client.post(
        changelist, {"action": "deactivate_users", "_selected_action": [staff_user.pk]}
    )
    admin_client.post(
        changelist, {"action": "reactivate_users", "_selected_action": [staff_user.pk]}
    )

    link = logs(A.ACCESS_LINK_CREATED).get()
    assert link.changes == {"purpose": AccessLink.objects.get(user=staff_user).purpose}
    assert logs(A.USER_DEACTIVATED).count() == 1
    assert logs(A.USER_REACTIVATED).count() == 1


def test_access_link_command_is_audited(staff_user):
    from django.core.management import call_command

    call_command("access_link", staff_user.email)

    log = logs(A.ACCESS_LINK_CREATED).get()
    assert log.actor is None
    assert log.target_id == str(staff_user.pk)


def test_site_setting_change_is_audited(admin_client):
    SiteSetting.objects.create(key="site.tagline", value="Antiga")
    url = reverse("admin:core_sitesetting_change", args=["site.tagline"])

    admin_client.post(url, {"value": "Nova linha"})

    log = logs(A.SETTING_CHANGED).get()
    assert log.changes == {"key": "site.tagline", "value": ["Antiga", "Nova linha"]}


def test_media_deletion_in_admin_is_audited(admin_client, staff_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    asset = MediaAsset.objects.create(
        file="media/x.jpg",
        uploaded_by=staff_user,
        width=1,
        height=1,
        size_bytes=1,
        mime="image/jpeg",
    )

    admin_client.post(
        reverse("admin:publications_mediaasset_changelist"),
        {"action": "delete_selected", "_selected_action": [asset.pk], "post": "yes"},
    )

    assert not MediaAsset.objects.exists()
    assert logs(A.MEDIA_DELETED).get().changes["file"] == "media/x.jpg"


def test_audit_log_admin_is_read_only(admin_client, admin_user):
    log = audit.record(A.LOGIN, actor=admin_user, target=admin_user)

    assert admin_client.get(reverse("admin:core_auditlog_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:core_auditlog_change", args=[log.pk])).status_code == 200
    assert admin_client.get(reverse("admin:core_auditlog_add")).status_code == 403
    response = admin_client.post(
        reverse("admin:core_auditlog_delete", args=[log.pk]), {"post": "yes"}
    )
    assert response.status_code == 403
    assert AuditLog.objects.filter(pk=log.pk).exists()


# --- painel ---


def test_static_page_publish_is_audited(client, editor_user):
    services.seed_site()
    client.force_login(editor_user)
    url = reverse("core:page_publish", args=["sobre"])

    client.post(url, {"publicada": "0"})
    client.post(url, {"publicada": "0"})  # sem mudança, sem registro
    client.post(url, {"publicada": "1"})

    page = StaticPage.objects.get(slug="sobre")
    assert logs(A.PAGE_UNPUBLISHED).get().target_id == str(page.pk)
    assert logs(A.PAGE_PUBLISHED).get().actor == editor_user


def test_featured_change_is_audited(client, editor_user, staff_user):
    article = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    article_services.publish(staff_user, article)
    cover = MediaAsset.objects.create(
        file="media/c.jpg", uploaded_by=staff_user, width=1, height=1, size_bytes=1, mime="x"
    )
    Article.objects.filter(pk=article.pk).update(cover=cover)
    client.force_login(editor_user)
    url = reverse("editorial:feature", args=[article.pk])

    client.post(url, {"acao": "adicionar"})
    client.post(url, {"acao": "subir"})  # já é o primeiro: nada muda

    log = logs(A.FEATURED_CHANGED).get()
    assert log.changes == {"action": "adicionar", "featured": [[], [article.pk]]}


def test_bulk_actions_are_audited(client, editor_user, staff_user):
    reviewer = UserFactory()
    new_reviewer = UserFactory()
    draft = ArticleFactory(author=staff_user, created_by=staff_user)
    in_review = ArticleFactory(ready=True, author=staff_user, created_by=staff_user)
    article_services.request_review(staff_user, in_review, reviewer)
    client.force_login(editor_user)
    bulk = reverse("editorial:bulk_action")

    client.post(bulk, {"acao": "arquivar", "ids": [draft.pk], "note": "Duplicada"})
    client.post(
        bulk, {"acao": "trocar-revisor", "ids": [in_review.pk], "reviewer": new_reviewer.pk}
    )

    archived = logs(A.ARTICLES_ARCHIVED).get()
    assert archived.actor == editor_user
    assert archived.changes == {"articles": [draft.pk]}
    swapped = logs(A.REVIEWER_REASSIGNED).get()
    assert swapped.changes == {"articles": [in_review.pk], "reviewer": new_reviewer.pk}
