"""Anonimizar o crédito de um aluno a pedido da família (docs/23, docs/18; E34)."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.core.models import AuditLog
from apps.editorial.models import EditorialEvent
from apps.publications import services
from apps.publications.credits import generic_student_name
from apps.publications.models import ArticleContributor
from tests.factories import ArticleFactory, UserFactory

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.mark.parametrize(
    ("class_group", "expected"),
    [
        ("2ª série B", "Aluno da 2ª série"),
        ("3a serie A", "Aluno da 3ª série"),
        ("1ª Série", "Aluno da 1ª série"),
        ("9º ano C", "Aluno do 9º ano"),
        ("Grêmio", "Aluno"),
        ("", "Aluno"),
    ],
)
def test_generic_student_name(class_group, expected):
    assert generic_student_name(class_group) == expected


@pytest.fixture
def author():
    return UserFactory(full_name="Carla Souza")


@pytest.fixture
def article(author):
    article = ArticleFactory(ready=True, author=author, created_by=author, title="Feira")
    services.publish(author, article)
    article.refresh_from_db()
    return article


@pytest.fixture
def student(article):
    return ArticleContributor.objects.create(
        article=article,
        display_name="Rafael S.",
        is_student=True,
        class_group="2ª série B",
        consent_ok=False,
        order=2,
    )


def test_admin_anonymizes_student_credit(article, student, admin_user, client):
    services.anonymize_student_credit(admin_user, student)

    student.refresh_from_db()
    assert student.display_name == "Aluno da 2ª série"
    assert student.class_group == ""
    assert student.anonymized_at is not None
    html = client.get(article.get_absolute_url()).content.decode()
    assert "Rafael" not in html
    assert "Aluno da 2ª série" in html
    event = EditorialEvent.objects.get(kind=EditorialEvent.Kind.CREDIT_ANONYMIZED)
    assert "Rafael" not in event.note
    log = AuditLog.objects.get(action=AuditLog.Action.CREDIT_ANONYMIZED)
    assert log.changes == {"article": article.pk}
    # Crédito anonimizado não identifica ninguém: deixa de exigir autorização.
    codes = [item.code for item in services.checklist(article)]
    assert "student_consent_missing" not in codes


def test_only_admin_and_only_students(article, student, editor_user, author, admin_user):
    with pytest.raises(PermissionDenied):
        services.anonymize_student_credit(editor_user, student)
    with pytest.raises(PermissionDenied):
        services.anonymize_student_credit(author, student)
    staff_credit = article.contributors.get(user=author)
    with pytest.raises(ValidationError):
        services.anonymize_student_credit(admin_user, staff_credit)


def test_alert_offers_anonymize_to_admin_and_goes_away(client, student, editor_user, admin_user):
    client.force_login(editor_user)
    assert "data-anonymize-credit" not in client.get("/painel/editorial/").content.decode()

    client.force_login(admin_user)
    html = client.get("/painel/editorial/").content.decode()
    assert f'data-anonymize-credit="{student.pk}"' in html
    assert "Rafael" not in html

    url = reverse("publications:anonymize_contributor", args=[student.article_id, student.pk])
    response = client.post(url, {"next": "/painel/editorial/"})

    assert response.status_code == 302
    assert response.url == "/painel/editorial/"
    html = client.get("/painel/editorial/").content.decode()
    assert 'data-alert-group="alunos-sem-autorizacao"' not in html


def test_editor_sidebar_button_for_admin(client, article, student, editor_user, admin_user):
    url = reverse("publications:anonymize_contributor", args=[article.pk, student.pk])
    client.force_login(editor_user)
    assert url not in client.get(reverse("publications:edit", args=[article.pk])).content.decode()
    assert client.post(url, **HX).status_code == 403

    client.force_login(admin_user)
    assert url in client.get(reverse("publications:edit", args=[article.pk])).content.decode()
    response = client.post(url, **HX)

    assert response.status_code == 200
    body = response.content.decode()
    assert "Aluno da 2ª série" in body
    assert "anonimizado" in body
    assert url not in body
