"""Exportar, pedir exclusão e anonimizar contas da equipe (docs/23, docs/14 "Conta"; E34).

Aceite: anonimizar mantém um crédito genérico.
"""

import io
import json
import zipfile

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from PIL import Image

from apps.accounts import privacy, services
from apps.accounts.models import AccessLink, User
from apps.core.models import AuditLog
from apps.editorial.models import EditorialEvent, Notification
from apps.publications import services as article_services
from apps.publications.models import ArticleContributor, MediaAsset
from tests.factories import DEFAULT_PASSWORD, ArticleFactory, DisciplineFactory, UserFactory

pytestmark = pytest.mark.django_db

ACCOUNT_URL = "/painel/conta/"
A = AuditLog.Action


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def png() -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 600), (20, 120, 80)).save(buffer, "PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")


@pytest.fixture
def carla():
    """Professora com perfil completo, foto, publicação no ar e histórico editorial."""
    user = UserFactory(full_name="Carla Souza Lima", email="carla@professor.educacao.sp.gov.br")
    services.save_profile(
        user,
        profile_fields={"headline": "Professora de Biologia", "bio": "Gosto de hortas."},
        disciplines=[DisciplineFactory(name="Biologia", slug="biologia")],
    )
    services.set_avatar(user, png())
    user.refresh_from_db()
    return user


@pytest.fixture
def carla_article(carla):
    article = ArticleFactory(ready=True, author=carla, created_by=carla, title="Horta da escola")
    article_services.publish(carla, article)
    article.refresh_from_db()
    return article


# --- exportar ---


def test_export_contains_account_profile_credits_and_history(carla, carla_article):
    data = privacy.export_user_data(carla)

    assert data["conta"]["email"] == "carla@professor.educacao.sp.gov.br"
    assert data["conta"]["nome_completo"] == "Carla Souza Lima"
    assert data["perfil"]["apresentacao"] == "Professora de Biologia"
    assert data["perfil"]["disciplinas"] == ["Biologia"]
    assert data["foto_de_perfil"]["arquivo"].startswith("foto-de-perfil.")
    assert data["creditos"][0]["publicacao"]["titulo"] == "Horta da escola"
    assert any(e["publicacao"]["id"] == carla_article.pk for e in data["eventos_editoriais"])
    assert data["imagens_enviadas"]
    text = json.dumps(data)
    assert "password" not in text
    assert "ip_hash" not in text
    json.dumps(data, ensure_ascii=False)  # serializável


def test_account_page_downloads_own_data_as_json_and_zip(client, carla):
    client.force_login(carla)

    page = client.get(ACCOUNT_URL).content.decode()
    assert "Baixar meus dados (JSON)" in page
    assert "Pedir exclusão da conta" in page

    response = client.post(ACCOUNT_URL, {"action": "export", "formato": "json"})
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert "attachment;" in response["Content-Disposition"]
    assert "no-store" in response["Cache-Control"]
    assert json.loads(response.content)["conta"]["email"] == carla.email

    response = client.post(ACCOUNT_URL, {"action": "export", "formato": "zip"})
    assert response["Content-Type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert "dados.json" in names
    assert any(name.startswith("foto-de-perfil.") for name in names)

    exports = AuditLog.objects.filter(action=A.DATA_EXPORTED, actor=carla)
    assert sorted(log.changes["format"] for log in exports) == ["json", "zip"]
    assert all(log.changes["own"] for log in exports)


def test_export_requires_login_and_post(client):
    assert client.post(ACCOUNT_URL, {"action": "export"}).status_code == 302


def test_only_self_or_admin_can_export(carla, staff_user, editor_user, admin_user):
    with pytest.raises(PermissionDenied):
        privacy.export_for(staff_user, carla)
    with pytest.raises(PermissionDenied):
        privacy.export_for(editor_user, carla)
    content, filename, mime = privacy.export_for(admin_user, carla)
    assert json.loads(content)["conta"]["email"] == carla.email
    assert filename.endswith(".json")
    assert mime == "application/json"


def test_admin_exports_one_or_many_users(admin_client, carla, staff_user):
    changelist = reverse("admin:accounts_user_changelist")

    one = admin_client.post(
        changelist, {"action": "export_user_data", "_selected_action": [carla.pk]}
    )
    many = admin_client.post(
        changelist, {"action": "export_user_data", "_selected_action": [carla.pk, staff_user.pk]}
    )

    assert json.loads(one.content)["conta"]["email"] == carla.email
    assert len(zipfile.ZipFile(io.BytesIO(many.content)).namelist()) == 2
    log = AuditLog.objects.filter(action=A.DATA_EXPORTED, target_id=str(carla.pk)).first()
    assert log.changes["own"] is False


def test_export_command(carla, tmp_path):
    out = tmp_path / "carla.zip"

    call_command("export_user_data", carla.email, "--zip", "--output", str(out))

    assert "dados.json" in zipfile.ZipFile(out).namelist()
    assert AuditLog.objects.get(action=A.DATA_EXPORTED).actor is None


# --- pedir exclusão ---


def test_request_deletion_notifies_admins(client, carla, admin_user):
    other_admin = UserFactory(admin=True)
    UserFactory(admin=True, is_active=False)
    client.force_login(carla)

    without_confirmation = client.post(ACCOUNT_URL, {"action": "request_deletion"})
    assert without_confirmation.status_code == 302
    assert not Notification.objects.exists()

    response = client.post(ACCOUNT_URL, {"action": "request_deletion", "confirmar": "sim"})

    assert response.status_code == 302
    notes = Notification.objects.filter(kind=Notification.Kind.SYSTEM)
    assert {n.user for n in notes} == {admin_user, other_admin}
    note = notes.first()
    assert "pediu a exclusão" in note.message
    assert note.url == reverse("admin:accounts_user_change", args=[carla.pk])
    assert AuditLog.objects.get(action=A.DELETION_REQUESTED).actor == carla
    carla.refresh_from_db()
    assert carla.is_active  # nada é apagado sem o administrador
    assert "Você pediu a exclusão em" in client.get(ACCOUNT_URL).content.decode()


# --- anonimizar (aceite) ---


def test_anonymize_keeps_generic_credit_and_removes_personal_data(
    client, carla, carla_article, admin_user
):
    profile_url = carla.profile.get_absolute_url()
    avatar_pk = carla.avatar_id
    avatar_path = MediaAsset.objects.get(pk=avatar_pk).file.name
    SocialAccount.objects.create(user=carla, provider="microsoft", uid="carla-uid")
    services.create_access_link(carla)
    Client().force_login(carla)  # outra sessão aberta
    other = UserFactory(full_name="Marcos Lima")
    Notification.objects.create(
        user=other, kind=Notification.Kind.SYSTEM, actor=carla, message="Carla Souza Lima publicou."
    )
    Notification.objects.create(user=carla, kind=Notification.Kind.SYSTEM, message="Para Carla")
    events_before = EditorialEvent.objects.filter(actor=carla).count()
    assert events_before > 0
    assert client.get(profile_url).status_code == 200

    privacy.anonymize_user(admin_user, carla)

    carla.refresh_from_db()
    # Crédito genérico: a publicação continua no ar, com o crédito sem nome.
    credit = ArticleContributor.objects.get(article=carla_article, user=carla)
    assert credit.display_name == privacy.ANONYMIZED_CREDIT
    page = client.get(carla_article.get_absolute_url())
    assert page.status_code == 200
    html = page.content.decode()
    assert "Ex-membro da equipe" in html
    assert "Carla" not in html
    assert profile_url not in html
    # Perfil público some.
    assert client.get(profile_url).status_code == 404
    assert not carla.profile.is_public
    assert carla.profile.bio == ""
    assert carla.profile.headline == ""
    assert not carla.profile.disciplines.exists()
    # Conta sem dados pessoais e sem forma de entrar.
    assert carla.full_name == privacy.ANONYMIZED_NAME
    assert carla.email == f"removido-{carla.pk}@anonimo.invalid"
    assert not carla.is_active
    assert carla.is_anonymized
    assert not carla.has_usable_password()
    assert not SocialAccount.objects.filter(user=carla).exists()
    assert not AccessLink.objects.filter(user=carla).exists()
    assert not any(
        str(s.get_decoded().get("_auth_user_id")) == str(carla.pk) for s in Session.objects.all()
    )
    login = Client().post(
        "/entrar/", {"login": "carla@professor.educacao.sp.gov.br", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 200
    # Foto apagada.
    assert carla.avatar_id is None
    assert not MediaAsset.objects.filter(pk=avatar_pk).exists()
    assert avatar_path  # o sinal de MediaAsset apaga os arquivos
    # Eventos mantidos, apontando para a conta anonimizada; nomes trocados nos textos.
    assert EditorialEvent.objects.filter(actor=carla).count() == events_before
    assert Notification.objects.get(user=other).message == "Usuário removido publicou."
    assert not Notification.objects.filter(user=carla).exists()
    log = AuditLog.objects.get(action=A.USER_ANONYMIZED)
    assert log.actor == admin_user
    assert log.target_id == str(carla.pk)
    assert "Carla" not in json.dumps(privacy.export_user_data(carla), ensure_ascii=False)


def test_anonymize_rules(carla, admin_user, editor_user):
    with pytest.raises(PermissionDenied):
        privacy.anonymize_user(editor_user, carla)
    with pytest.raises(ValidationError):
        privacy.anonymize_user(admin_user, admin_user)

    privacy.anonymize_user(admin_user, carla)

    carla.refresh_from_db()
    with pytest.raises(ValidationError):
        privacy.anonymize_user(admin_user, carla)
    with pytest.raises(services.AccessLinkError):
        services.reactivate_user(carla)


def test_admin_action_asks_confirmation_then_anonymizes(admin_client, carla):
    changelist = reverse("admin:accounts_user_changelist")
    selected = {"action": "anonymize_users", "_selected_action": [carla.pk]}

    confirm = admin_client.post(changelist, selected)

    assert confirm.status_code == 200
    assert "Sim, anonimizar" in confirm.content.decode()
    carla.refresh_from_db()
    assert not carla.is_anonymized

    done = admin_client.post(changelist, {**selected, "confirmar": "sim"})

    assert done.status_code == 302
    carla.refresh_from_db()
    assert carla.is_anonymized
    reactivate = {"action": "reactivate_users", "_selected_action": [carla.pk]}
    admin_client.post(changelist, reactivate)
    carla.refresh_from_db()
    assert not carla.is_active


def test_anonymize_command(carla):
    call_command("anonymize_user", carla.email, "--yes")

    carla.refresh_from_db()
    assert carla.is_anonymized
    assert User.objects.filter(email=carla.email).exists()
    assert AuditLog.objects.get(action=A.USER_ANONYMIZED).actor is None
