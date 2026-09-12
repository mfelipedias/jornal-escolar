import pytest
from django.urls import reverse

from apps.editorial import notifications
from apps.editorial.models import Notification
from apps.publications import services
from tests.factories import ArticleFactory, DisciplineFactory, UserFactory, text_doc

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def author():
    return UserFactory(full_name="Ana Autora")


@pytest.fixture
def article(author):
    return ArticleFactory(ready=True, author=author, created_by=author, title="Feira")


def inbox(user):
    return list(Notification.objects.filter(user=user).values_list("kind", flat=True))


# --- quando notifica ---


def test_editor_editing_others_text_notifies_author(article, author, editor_user):
    """Aceite da E17: editor edita texto alheio, autor vê aviso."""
    services.update_article(editor_user, article, body_json=text_doc("Corrigido pelo editor"))

    notification = Notification.objects.get(user=author)
    assert notification.kind == Notification.Kind.EDITED_BY_OTHER
    assert notification.actor == editor_user
    assert "editou “Feira”" in notification.message
    assert notification.url == reverse("publications:edit", args=[article.pk])


def test_repeated_autosaves_do_not_flood(article, author, editor_user):
    for i in range(10):
        services.update_article(editor_user, article, subtitle=f"versão {i}")

    assert Notification.objects.filter(user=author).count() == 1


def test_new_notice_after_author_read_previous(article, author, editor_user):
    services.update_article(editor_user, article, subtitle="a")
    notifications.mark_all_read(author)

    services.update_article(editor_user, article, subtitle="b")

    assert Notification.objects.filter(user=author).count() == 2


def test_author_editing_own_text_does_not_notify(article, author):
    services.update_article(author, article, subtitle="eu mesma")

    assert not Notification.objects.exists()


def test_coauthor_editing_does_not_notify_as_third_party(article, author):
    coauthor = UserFactory()
    services.add_staff_credit(author, article, coauthor)

    services.update_article(coauthor, article, subtitle="coautor")

    assert not Notification.objects.filter(kind=Notification.Kind.EDITED_BY_OTHER).exists()


def test_publish_notifies_other_authors(article, author):
    coauthor = UserFactory()
    services.add_staff_credit(author, article, coauthor)

    services.publish(author, article)

    assert inbox(coauthor) == [Notification.Kind.PUBLISHED_BY_OTHER]
    assert inbox(author) == []


def test_editor_publishing_notifies_author(article, author, editor_user):
    services.publish(editor_user, article)

    assert inbox(author) == [Notification.Kind.PUBLISHED_BY_OTHER]


def test_editor_archiving_notifies_with_reason(article, author, editor_user):
    services.publish(author, article)

    services.archive(editor_user, article, note="Foto sem autorização")

    notification = Notification.objects.get(user=author, kind=Notification.Kind.ARCHIVED_BY_OTHER)
    assert "Motivo: Foto sem autorização" in notification.message


def test_metadata_credit_and_cover_changes_by_editor_notify(article, author, editor_user):
    services.set_metadata(
        editor_user,
        article,
        type_id=article.type_id,
        discipline_ids=[DisciplineFactory().pk],
        topic_ids=[],
        event_at=None,
        event_location="",
        sources=[],
    )
    services.add_guest_credit(editor_user, article, name="Grêmio")

    assert (
        Notification.objects.filter(user=author, kind=Notification.Kind.EDITED_BY_OTHER).count()
        == 1
    )


def test_inactive_authors_are_not_notified(article, author, editor_user):
    author.is_active = False
    author.save()

    services.update_article(editor_user, article, subtitle="x")

    assert not Notification.objects.exists()


# --- telas ---


def test_bell_shows_unread_count(client, article, author, editor_user):
    services.update_article(editor_user, article, subtitle="x")
    client.force_login(author)

    html = client.get("/").content.decode()

    assert 'id="notification-bell"' in html
    assert "(1 não lidas)" in html


def test_dropdown_lists_only_own_notifications(client, article, author, editor_user):
    services.update_article(editor_user, article, subtitle="x")
    stranger = UserFactory()
    client.force_login(stranger)

    html = client.get(reverse("editorial:notification_dropdown"), **HTMX).content.decode()

    assert "Nenhuma notificação" in html


def test_open_marks_read_and_redirects(client, article, author, editor_user):
    services.update_article(editor_user, article, subtitle="x")
    notification = Notification.objects.get(user=author)
    client.force_login(author)

    response = client.get(reverse("editorial:notification_open", args=[notification.pk]))

    assert response.status_code == 302
    assert response.url == reverse("publications:edit", args=[article.pk])
    notification.refresh_from_db()
    assert notification.is_read


def test_cannot_open_someone_elses_notification(client, article, author, editor_user):
    services.update_article(editor_user, article, subtitle="x")
    notification = Notification.objects.get(user=author)
    client.force_login(UserFactory())

    response = client.get(reverse("editorial:notification_open", args=[notification.pk]))

    assert response.status_code == 404


def test_open_never_redirects_outside(client, author):
    notification = notifications.notify(author, "system", "Teste", url="https://evil.example/")
    client.force_login(author)

    response = client.get(reverse("editorial:notification_open", args=[notification.pk]))

    assert response.url == reverse("editorial:notifications")


def test_read_all(client, article, author, editor_user):
    services.update_article(editor_user, article, subtitle="x")
    client.force_login(author)

    response = client.post(reverse("editorial:notification_read_all"), **HTMX)

    assert response.status_code == 200
    assert notifications.unread_count(author) == 0
    assert "não lidas" not in response.content.decode()


def test_notifications_page(client, article, author, editor_user):
    services.archive(editor_user, article, note="Revisão")
    client.force_login(author)

    response = client.get(reverse("editorial:notifications"))

    assert response.status_code == 200
    assert "arquivou" in response.content.decode()


def test_notifications_require_login(client):
    assert client.get(reverse("editorial:notifications")).status_code == 302
