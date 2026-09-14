"""Assistente de primeiro acesso (docs/14, E23): o fluxo completo, de ponta a ponta."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.accounts import services
from apps.accounts.models import User
from apps.taxonomy.models import Topic
from tests.factories import DEFAULT_PASSWORD, DisciplineFactory, KnowledgeAreaFactory, UserFactory

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Uma-Senha-Boa-2026"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def photo_upload(size=(1200, 800), name="foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def step_url(step: int) -> str:
    return reverse("accounts:onboarding", kwargs={"step": step})


@pytest.fixture
def taxonomy():
    natureza = KnowledgeAreaFactory(name="Ciências da Natureza", slug="natureza")
    humanas = KnowledgeAreaFactory(name="Ciências Humanas", slug="humanas", color="coral")
    biologia = DisciplineFactory(name="Biologia", slug="biologia", area=natureza)
    historia = DisciplineFactory(name="História", slug="historia", area=humanas)
    clima = Topic.objects.create(name="Clima", slug="clima")
    clima.disciplines.add(biologia)
    Topic.objects.create(name="Astronomia", slug="astronomia")
    return {"natureza": natureza, "humanas": humanas, "biologia": biologia, "historia": historia}


def test_urls():
    assert step_url(1) == "/painel/primeiro-acesso/1/"
    assert reverse("accounts:onboarding_done") == "/painel/primeiro-acesso/concluir/"
    assert reverse("accounts:profile_edit") == "/painel/perfil/"
    assert reverse("accounts:account_settings") == "/painel/conta/"


def test_requires_login(client):
    response = client.get(step_url(1))

    assert response.status_code == 302
    assert response.url.startswith("/entrar/")


def test_unknown_step_is_404(client, staff_user):
    client.force_login(staff_user)

    assert client.get(step_url(4)).status_code == 404


def test_full_first_access_flow(client, admin_user, taxonomy):
    """Link de primeiro acesso → senha → três passos preenchidos → perfil público pronto."""
    newcomer = UserFactory(
        email="carla@professor.educacao.sp.gov.br",
        full_name="Carla Mendes Souza",
        microsoft_only=True,
    )
    link = services.create_access_link(newcomer, created_by=admin_user)

    # Senha criada: vai para o assistente, não para a home.
    response = client.post(
        reverse("accounts:access_link", kwargs={"token": link.pk}),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    assert response.url == step_url(1)

    # Passo 1: quem é você.
    html = client.get(step_url(1)).content.decode()
    assert "Passo 1 de 3" in html
    assert 'value="Carla Mendes Souza"' in html
    assert "Professor" in html  # cargo só para leitura
    assert 'name="staff_kind"' not in html
    response = client.post(
        step_url(1),
        {
            "action": "save",
            "display_name": "Profa. Carla",
            "headline": "Professora de Biologia",
            "photo": photo_upload(),
        },
    )
    assert response.url == step_url(2)

    # Passo 2: disciplinas agrupadas por área.
    html = client.get(step_url(2)).content.decode()
    assert "Ciências da Natureza" in html
    assert "Biologia" in html
    response = client.post(
        step_url(2), {"action": "save", "disciplines": [taxonomy["biologia"].pk]}
    )
    assert response.url == step_url(3)

    # Passo 3: tópicos ligados às disciplinas aparecem primeiro.
    html = client.get(step_url(3)).content.decode()
    assert html.index("Clima") < html.index("Astronomia")
    clima = Topic.objects.get(slug="clima")
    response = client.post(
        step_url(3),
        {
            "action": "save",
            "topics": [clima.pk],
            "new_topic": "Robótica",
            "bio": "Dou aula de Biologia há dez anos.",
        },
    )
    assert response.url == reverse("accounts:onboarding_done")

    response = client.get(response.url)
    assert response.status_code == 302
    assert response.url == "/"

    newcomer.refresh_from_db()
    profile = newcomer.profile
    assert profile.onboarded_at is not None
    assert newcomer.public_name == "Profa. Carla"
    assert profile.headline == "Professora de Biologia"
    assert profile.bio == "Dou aula de Biologia há dez anos."
    assert list(profile.disciplines.all()) == [taxonomy["biologia"]]
    assert list(profile.areas.all()) == [taxonomy["natureza"]]  # derivada da disciplina
    assert list(profile.topics.all()) == [clima]
    assert Topic.objects.get(name="Robótica").is_active is False
    assert newcomer.avatar is not None
    assert newcomer.avatar.width == newcomer.avatar.height  # recorte quadrado
    assert newcomer.avatar.alt_text == "Foto de Carla Mendes Souza"

    # O perfil público já mostra o que foi preenchido.
    html = client.get(profile.get_absolute_url()).content.decode()
    assert "Profa. Carla" in html
    assert "Dou aula de Biologia há dez anos." in html
    assert 'href="/painel/perfil/"' in html  # "Editar perfil" para o dono

    # Próximos logins não passam mais pelo assistente.
    client.logout()
    response = client.post(
        "/entrar/", {"login": "carla@professor.educacao.sp.gov.br", "password": NEW_PASSWORD}
    )
    assert response.url == "/"


def test_every_step_can_be_skipped(client, taxonomy):
    user = UserFactory(full_name="Bruno Lima")
    client.force_login(user)

    for step in (1, 2, 3):
        response = client.post(step_url(step), {"action": "skip"})
        assert response.status_code == 302
    assert response.url == reverse("accounts:onboarding_done")

    response = client.get(response.url, follow=True)
    user.refresh_from_db()
    assert user.profile.onboarded_at is not None
    assert user.display_name == ""
    assert not user.profile.disciplines.exists()
    assert "complete seu perfil: falta foto, disciplinas, sobre mim" in (response.content.decode())


def test_do_it_later_link_finishes_wizard(client, staff_user):
    client.force_login(staff_user)

    html = client.get(step_url(1)).content.decode()
    assert 'href="/painel/primeiro-acesso/concluir/"' in html

    client.get(reverse("accounts:onboarding_done"))
    staff_user.profile.refresh_from_db()
    assert staff_user.profile.onboarded_at is not None


def test_non_teacher_chooses_areas(client, taxonomy):
    monitor = UserFactory(staff_kind=User.StaffKind.MONITOR)
    client.force_login(monitor)

    html = client.get(step_url(2)).content.decode()
    assert "Marque as áreas em que você atua." in html
    assert 'name="areas"' in html
    assert 'name="disciplines"' not in html

    client.post(step_url(2), {"action": "save", "areas": [taxonomy["humanas"].pk]})
    assert list(monitor.profile.areas.all()) == [taxonomy["humanas"]]


def test_identity_step_requires_name(client, staff_user):
    client.force_login(staff_user)

    response = client.post(step_url(1), {"action": "save", "display_name": "  "})

    assert response.status_code == 200
    assert "Informe como seu nome aparece no jornal." in response.content.decode()


def test_invalid_photo_keeps_step_and_saves_nothing(client, staff_user):
    client.force_login(staff_user)
    fake = SimpleUploadedFile("foto.jpg", b"nao sou imagem", content_type="image/jpeg")

    response = client.post(
        step_url(1), {"action": "save", "display_name": "Outro Nome", "photo": fake}
    )

    assert response.status_code == 200
    assert "O arquivo não é uma imagem válida." in response.content.decode()
    staff_user.refresh_from_db()
    assert staff_user.display_name == ""
    assert staff_user.avatar is None


def test_first_password_login_goes_to_wizard(client):
    UserFactory(email="ana@escola.sp.gov.br")

    response = client.post(
        "/entrar/", {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD}
    )

    assert response.url == step_url(1)


def test_first_login_respects_next(client):
    UserFactory(email="ana@escola.sp.gov.br")

    response = client.post(
        "/entrar/?next=/sobre/",
        {"login": "ana@escola.sp.gov.br", "password": DEFAULT_PASSWORD, "next": "/sobre/"},
    )

    assert response.url == "/sobre/"


def test_password_reset_link_of_onboarded_user_goes_home(client):
    user = UserFactory()
    services.complete_onboarding(user)
    link = services.create_access_link(user)

    response = client.post(
        reverse("accounts:access_link", kwargs={"token": link.pk}),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )

    assert response.url == "/"
