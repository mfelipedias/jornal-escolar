"""Tela /painel/perfil/ e /painel/conta/ (docs/14, E23)."""

import io

import pytest
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from apps.accounts import selectors, services
from apps.accounts.models import User
from apps.publications.models import ArticleContributor
from apps.taxonomy.models import Topic
from tests.factories import (
    DEFAULT_PASSWORD,
    ArticleFactory,
    DisciplineFactory,
    KnowledgeAreaFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

URL = "/painel/perfil/"
ACCOUNT_URL = "/painel/conta/"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def png(size=(900, 600), extra_bytes: int = 0) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 80)).save(buffer, "PNG")
    data = buffer.getvalue() + b"\0" * extra_bytes
    return SimpleUploadedFile("foto.png", data, content_type="image/png")


@pytest.fixture
def discipline():
    return DisciplineFactory(name="Química", slug="quimica")


@pytest.fixture
def teacher(client):
    user = UserFactory(full_name="Ana Souza")
    client.force_login(user)
    return user


def payload(**changes) -> dict:
    data = {
        "display_name": "Ana Souza",
        "headline": "Professora de Química",
        "bio": "",
        "since_year": "",
        "is_public": "on",
        "slug": "ana-souza",
        "accepts_english": "on",
        "show_reviewer_credit": "on",
        "show_reads": "on",
    }
    data.update(changes)
    return {k: v for k, v in data.items() if v is not None}


def test_requires_login(client):
    assert client.get(URL).status_code == 302
    assert client.get(ACCOUNT_URL).status_code == 302


def test_form_shows_current_data(client, teacher):
    teacher.profile.headline = "Professora de Química"
    teacher.profile.save()

    response = client.get(URL)
    html = response.content.decode()

    assert response.status_code == 200
    assert 'value="Professora de Química"' in html
    assert 'value="ana-souza"' in html
    assert "Complete seu perfil:" in html
    assert 'name="staff_kind"' not in html
    assert 'name="role"' not in html


def test_save_profile(client, teacher, discipline):
    topic = Topic.objects.create(name="Energia", slug="energia")

    response = client.post(
        URL,
        payload(
            bio="Sobre mim.",
            since_year="2015",
            disciplines=[discipline.pk],
            topics=[topic.pk],
            show_reads=None,
            reviewers_may_publish="on",
            link_label_0="Lattes",
            link_url_0="https://lattes.cnpq.br/123",
            edu_degree_0="Licenciatura em Química",
            edu_institution_0="Universidade X",
            edu_year_0="2010",
        ),
    )

    assert response.status_code == 302
    profile = teacher.profile
    profile.refresh_from_db()
    assert profile.headline == "Professora de Química"
    assert profile.bio == "Sobre mim."
    assert profile.since_year == 2015
    assert profile.show_reads is False
    assert profile.reviewers_may_publish is True
    assert profile.links == [{"label": "Lattes", "url": "https://lattes.cnpq.br/123"}]
    assert profile.education == [
        {"degree": "Licenciatura em Química", "institution": "Universidade X", "year": "2010"}
    ]
    assert list(profile.areas.all()) == [discipline.area]
    assert list(profile.topics.all()) == [topic]


def test_links_only_http_and_https(client, teacher, discipline):
    response = client.post(
        URL,
        payload(
            disciplines=[discipline.pk],
            link_label_0="Ruim",
            link_url_0="javascript:alert(1)",
        ),
    )

    assert response.status_code == 200
    assert "use um endereço que comece com https://" in response.content.decode()
    teacher.profile.refresh_from_db()
    assert teacher.profile.links == []


def test_at_most_four_links_and_six_education_rows(client, teacher, discipline):
    data = payload(disciplines=[discipline.pk])
    for i in range(6):
        data[f"link_url_{i}"] = f"https://exemplo.com/{i}"
    for i in range(8):
        data[f"edu_degree_{i}"] = f"Curso {i}"

    client.post(URL, data)

    teacher.profile.refresh_from_db()
    assert len(teacher.profile.links) == 4
    assert len(teacher.profile.education) == 6
    assert teacher.profile.links[0]["label"] == ""


def test_teacher_with_public_profile_needs_discipline(client, teacher):
    response = client.post(URL, payload())

    assert response.status_code == 200
    assert "Marque ao menos uma disciplina." in response.content.decode()


def test_hidden_profile_needs_no_discipline(client, teacher):
    response = client.post(URL, payload(is_public=None))

    assert response.status_code == 302
    teacher.profile.refresh_from_db()
    assert teacher.profile.is_public is False


def test_non_teacher_needs_area(client):
    monitor = UserFactory(staff_kind=User.StaffKind.MONITOR, full_name="Ana Souza")
    client.force_login(monitor)
    area = KnowledgeAreaFactory()

    response = client.post(URL, payload())
    assert "Marque ao menos uma área de atuação." in response.content.decode()

    response = client.post(URL, payload(areas=[area.pk]))
    assert response.status_code == 302


def test_headline_is_required(client, teacher, discipline):
    response = client.post(URL, payload(headline="", disciplines=[discipline.pk]))

    assert response.status_code == 200
    assert "Revise os campos marcados." in response.content.decode()


def test_role_and_kind_cannot_be_changed(client, teacher, discipline):
    client.post(
        URL,
        payload(disciplines=[discipline.pk], role="admin", staff_kind="principal"),
    )

    teacher.refresh_from_db()
    assert teacher.role == User.Role.STAFF
    assert teacher.staff_kind == User.StaffKind.TEACHER
    assert not teacher.is_staff


def test_slug_change_warns_and_must_be_unique(client, teacher, discipline):
    UserFactory(full_name="Pedro Alves")

    response = client.post(URL, payload(disciplines=[discipline.pk], slug="pedro-alves"))
    assert "Este endereço já é usado por outro perfil." in response.content.decode()

    html = client.get(URL).content.decode()
    assert "mudar o endereço quebra links antigos" in html

    response = client.post(
        URL, payload(disciplines=[discipline.pk], slug="Profa Ana Souza"), follow=True
    )
    teacher.profile.refresh_from_db()
    assert teacher.profile.slug == "profa-ana-souza"
    assert "Links antigos para ele não funcionam mais." in response.content.decode()


def test_name_change_keeps_old_credits_by_default(client, teacher, discipline):
    article = ArticleFactory(created_by=teacher)

    client.post(URL, payload(disciplines=[discipline.pk], display_name="Profa. Ana"))

    teacher.refresh_from_db()
    assert teacher.public_name == "Profa. Ana"
    credit = ArticleContributor.objects.get(article=article, user=teacher)
    assert credit.display_name == "Ana Souza"


def test_name_change_can_update_old_credits(client, teacher, discipline):
    article = ArticleFactory(created_by=teacher)
    student = ArticleContributor.objects.create(
        article=article, display_name="Ana S.", is_student=True, role="coauthor"
    )

    client.post(
        URL,
        payload(disciplines=[discipline.pk], display_name="Profa. Ana", update_credits="on"),
    )

    credit = ArticleContributor.objects.get(article=article, user=teacher)
    assert credit.display_name == "Profa. Ana"
    student.refresh_from_db()
    assert student.display_name == "Ana S."


def test_name_equal_to_full_name_is_stored_empty(client, teacher, discipline):
    teacher.display_name = "Aninha"
    teacher.save()

    client.post(URL, payload(disciplines=[discipline.pk], display_name="Ana Souza"))

    teacher.refresh_from_db()
    assert teacher.display_name == ""


def test_topic_suggestion(client, teacher, discipline):
    Topic.objects.create(name="Energia", slug="energia")

    client.post(URL, payload(disciplines=[discipline.pk], new_topic="  energia "))
    assert list(teacher.profile.topics.values_list("slug", flat=True)) == ["energia"]

    response = client.post(
        URL, payload(disciplines=[discipline.pk], new_topic="Mudanças climáticas"), follow=True
    )
    suggested = Topic.objects.get(name="Mudanças climáticas")
    assert suggested.is_active is False
    assert "depois que o administrador aprovar" in response.content.decode()
    assert suggested not in teacher.profile.topics.all()


def test_photo_upload_and_removal(client, teacher, discipline):
    client.post(URL, {**payload(disciplines=[discipline.pk]), "photo": png()})
    teacher.refresh_from_db()
    first = teacher.avatar
    assert first is not None
    assert (first.width, first.height) == (600, 600)
    assert first.uploaded_by == teacher

    client.post(URL, {**payload(disciplines=[discipline.pk]), "photo": png((500, 700))})
    teacher.refresh_from_db()
    assert teacher.avatar.pk != first.pk
    assert not type(first).objects.filter(pk=first.pk).exists()  # foto antiga apagada

    client.post(URL, payload(disciplines=[discipline.pk], remove_photo="on"))
    teacher.refresh_from_db()
    assert teacher.avatar is None


def test_photo_over_5mb_is_rejected(client, teacher, discipline):
    big = png(extra_bytes=5 * 1024 * 1024)

    response = client.post(URL, {**payload(disciplines=[discipline.pk]), "photo": big})

    assert response.status_code == 200
    assert "A foto pode ter no máximo 5 MB." in response.content.decode()
    teacher.refresh_from_db()
    assert teacher.avatar is None


def test_missing_profile_items(teacher, discipline):
    assert selectors.missing_profile_items(teacher) == ["foto", "disciplinas", "sobre mim"]

    teacher.profile.bio = "Oi"
    teacher.profile.save()
    teacher.profile.disciplines.add(discipline)
    assert selectors.missing_profile_items(teacher) == ["foto"]

    monitor = UserFactory(staff_kind=User.StaffKind.MONITOR)
    assert "áreas de atuação" in selectors.missing_profile_items(monitor)


def test_public_page_edit_link(client, teacher):
    other = UserFactory()
    teacher.profile.disciplines.add(DisciplineFactory())

    own = client.get(teacher.profile.get_absolute_url()).content.decode()
    assert 'href="/painel/perfil/"' in own
    assert "Editar perfil" in own

    others = client.get(other.profile.get_absolute_url()).content.decode()
    assert "Editar perfil" not in others


def test_admin_edit_link_goes_to_django_admin(admin_client, staff_user):
    html = admin_client.get(staff_user.profile.get_absolute_url()).content.decode()

    assert f'href="/admin/accounts/user/{staff_user.pk}/change/"' in html


def test_masthead_links_to_profile(client, teacher):
    assert 'href="/painel/perfil/"' in client.get("/").content.decode()


# --- conta ---


def test_account_page_password_account(client, teacher):
    html = client.get(ACCOUNT_URL).content.decode()

    assert "E-mail e senha" in html
    assert "Alterar senha" in html
    assert "Este navegador" in html


def test_change_password_keeps_session(client, teacher):
    new = "Outra-Senha-Forte-2026"
    response = client.post(
        ACCOUNT_URL,
        {
            "action": "password",
            "old_password": DEFAULT_PASSWORD,
            "new_password1": new,
            "new_password2": new,
        },
    )

    assert response.status_code == 302
    teacher.refresh_from_db()
    assert teacher.check_password(new)
    assert client.get(ACCOUNT_URL).status_code == 200  # continua dentro


def test_change_password_wrong_old(client, teacher):
    response = client.post(
        ACCOUNT_URL,
        {
            "action": "password",
            "old_password": "errada",
            "new_password1": "Outra-Senha-Forte-2026",
            "new_password2": "Outra-Senha-Forte-2026",
        },
    )

    assert response.status_code == 200
    assert "A senha atual não confere." in response.content.decode()


def test_microsoft_only_account_has_no_password_form(client):
    user = UserFactory(microsoft_only=True)
    client.force_login(user)

    html = client.get(ACCOUNT_URL).content.decode()
    assert "Alterar senha" not in html
    assert "peça ao administrador um link de acesso" in html

    response = client.post(
        ACCOUNT_URL,
        {"action": "password", "new_password1": "x" * 12, "new_password2": "x" * 12},
    )
    assert response.status_code == 404


def test_end_other_sessions(client, teacher):
    other_device = Client()
    other_device.force_login(teacher)
    someone_else = Client()
    someone_else.force_login(UserFactory())
    client.get(ACCOUNT_URL)  # garante a sessão atual gravada

    assert len(services.user_sessions(teacher)) == 2
    response = client.post(ACCOUNT_URL, {"action": "end_sessions"}, follow=True)

    assert "1 outra(s) sessão(ões) encerrada(s)." in response.content.decode()
    assert len(services.user_sessions(teacher)) == 1
    assert Session.objects.count() == 2
    assert other_device.get(ACCOUNT_URL).status_code == 302
    assert client.get(ACCOUNT_URL).status_code == 200
