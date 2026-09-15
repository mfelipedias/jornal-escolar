"""Direitos dos titulares para a equipe (docs/23): exportar dados, anonimizar e pedir exclusão.

- export_user_data: tudo o que o sistema guarda sobre uma conta, em um dicionário pronto para
  JSON. export_zip junta esse JSON e a foto de perfil em um arquivo .zip.
- anonymize_user: apaga os dados pessoais e mantém a história do jornal. Os créditos viram
  "Ex-membro da equipe", o perfil some, o login é desativado, a foto é apagada; eventos,
  comentários da revisão e auditoria continuam apontando para a conta, agora sem nome.
- request_deletion: a própria pessoa pede a exclusão; o administrador recebe um aviso no painel
  e decide (anonimizar é a forma de excluir sem quebrar as publicações).

Toda exportação, anonimização e pedido de exclusão vai para a auditoria (AuditLog).
"""

import io
import json
import zipfile
from typing import Any

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.site_settings import get_setting

from . import services
from .models import AccessLink, TeacherProfile, User

ANONYMIZED_NAME = "Usuário removido"
ANONYMIZED_CREDIT = "Ex-membro da equipe"
ANONYMIZED_EMAIL_DOMAIN = "anonimo.invalid"


def _date(value: Any) -> str | None:
    return timezone.localtime(value).isoformat() if value else None


def _article_ref(article: Any) -> dict[str, Any]:
    return {"id": article.pk, "titulo": article.title, "estado": article.get_status_display()}


# --- exportar ---


def export_user_data(user: User) -> dict[str, Any]:
    """Dados da conta, do perfil e do que a pessoa fez no sistema (docs/23, "Acesso").

    Não inclui o texto das publicações (é público e fica no jornal), nem hash de senha,
    códigos de links de acesso ou hashes de IP.
    """
    from apps.editorial.models import EditorialComment, EditorialEvent, Notification
    from apps.publications.models import Article, ArticleContributor, MediaAsset

    profile = TeacherProfile.objects.filter(user=user).first()
    data: dict[str, Any] = {
        "sobre_este_arquivo": (
            f"Dados guardados pelo {get_setting('site.name')} sobre a sua conta, gerados em "
            f"{timezone.localtime():%d/%m/%Y %H:%M}. Datas no horário de Brasília."
        ),
        "gerado_em": _date(timezone.now()),
        "conta": {
            "email": user.email,
            "nome_completo": user.full_name,
            "nome_publico": user.display_name,
            "papel": user.get_role_display(),
            "cargo": user.get_staff_kind_display(),
            "ativa": user.is_active,
            "cadastrada_em": _date(user.date_joined),
            "ultimo_login": _date(user.last_login),
            "desativada_em": _date(user.deactivated_at),
            "anonimizada_em": _date(user.anonymized_at),
            "entra_com_senha": user.has_usable_password(),
            "entra_com_microsoft": SocialAccount.objects.filter(
                user=user, provider="microsoft"
            ).exists(),
        },
        "perfil": None,
        "foto_de_perfil": None,
    }
    if profile is not None:
        data["perfil"] = {
            "endereco": profile.get_absolute_url(),
            "publico": profile.is_public,
            "apresentacao": profile.headline,
            "sobre_mim": profile.bio,
            "formacao": profile.education,
            "na_escola_desde": profile.since_year,
            "links": profile.links,
            "disciplinas": list(profile.disciplines.values_list("name", flat=True)),
            "areas": list(profile.areas.values_list("name", flat=True)),
            "interesses": list(profile.topics.values_list("name", flat=True)),
            "aceita_sugestoes_em_ingles": profile.accepts_english,
            "mostrar_credito_como_revisor": profile.show_reviewer_credit,
            "revisores_podem_publicar_por_mim": profile.reviewers_may_publish,
            "mostrar_leituras": profile.show_reads,
            "primeiro_acesso_concluido_em": _date(profile.onboarded_at),
        }
    if user.avatar_id:
        data["foto_de_perfil"] = {
            "arquivo": _avatar_filename(user),
            "enviada_em": _date(user.avatar.created_at),
        }

    data["creditos"] = [
        {
            "publicacao": _article_ref(credit.article),
            "papel": credit.get_role_display(),
            "nome_no_credito": credit.display_name,
        }
        for credit in ArticleContributor.objects.filter(user=user)
        .select_related("article")
        .order_by("article_id", "role")
    ]
    data["publicacoes_criadas"] = [
        {**_article_ref(article), "criada_em": _date(article.created_at)}
        for article in Article.objects.filter(created_by=user).order_by("created_at")
    ]
    data["comentarios_da_revisao"] = [
        {
            "publicacao": _article_ref(comment.article),
            "comentario": comment.body,
            "trecho": comment.anchor_text,
            "resposta": comment.parent_id is not None,
            "situacao": comment.get_status_display(),
            "criado_em": _date(comment.created_at),
        }
        for comment in EditorialComment.objects.filter(author=user)
        .select_related("article")
        .order_by("created_at")
    ]
    data["eventos_editoriais"] = [
        {
            "publicacao": _article_ref(event.article),
            "tipo": event.get_kind_display(),
            "de": event.from_status,
            "para": event.to_status,
            "nota": event.note,
            "quando": _date(event.created_at),
        }
        for event in EditorialEvent.objects.filter(actor=user)
        .select_related("article")
        .order_by("created_at")
    ]
    data["notificacoes"] = [
        {
            "mensagem": n.message,
            "tipo": n.get_kind_display(),
            "criada_em": _date(n.created_at),
            "lida_em": _date(n.read_at),
        }
        for n in Notification.objects.filter(user=user).order_by("created_at")
    ]
    data["imagens_enviadas"] = [
        {
            "arquivo": asset.file.name,
            "texto_alternativo": asset.alt_text,
            "credito": asset.credit,
            "licenca": asset.get_license_display(),
            "publicacao_id": asset.article_id,
            "enviada_em": _date(asset.created_at),
        }
        for asset in MediaAsset.objects.filter(uploaded_by=user).order_by("created_at")
    ]
    data["links_de_acesso"] = [
        {
            "finalidade": link.get_purpose_display(),
            "situacao": AccessLink.Status(link.status).label,
            "gerado_em": _date(link.created_at),
            "expira_em": _date(link.expires_at),
            "usado_em": _date(link.used_at),
        }
        for link in AccessLink.objects.filter(user=user).order_by("created_at")
    ]
    data["auditoria"] = [
        {
            "acao": log.get_action_display(),
            "feita_por_voce": log.actor_id == user.pk,
            "detalhes": log.changes,
            "quando": _date(log.created_at),
        }
        for log in (AuditLog.objects.filter(actor=user) | audit.for_target(user)).order_by(
            "created_at", "pk"
        )
    ]
    return data


def _avatar_filename(user: User) -> str:
    extension = user.avatar.file.name.rsplit(".", 1)[-1] if user.avatar.file else "jpg"
    return f"foto-de-perfil.{extension}"


def export_json(user: User) -> bytes:
    return json.dumps(export_user_data(user), ensure_ascii=False, indent=2).encode("utf-8")


def export_zip(user: User) -> bytes:
    """dados.json e, se houver, a foto de perfil original."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dados.json", export_json(user))
        if user.avatar_id and user.avatar.file and default_storage.exists(user.avatar.file.name):
            with default_storage.open(user.avatar.file.name, "rb") as photo:
                archive.writestr(_avatar_filename(user), photo.read())
    return buffer.getvalue()


def export_filename(user: User, extension: str) -> str:
    return f"meus-dados-jornal-{user.pk}-{timezone.localdate():%Y-%m-%d}.{extension}"


def export_for(
    actor: User | None,
    person: User,
    *,
    fmt: str = "json",
    request: HttpRequest | None = None,
) -> tuple[bytes, str, str]:
    """Gera a exportação e registra na auditoria. Devolve (conteúdo, nome, tipo MIME).

    actor None: comando no servidor (export_user_data).
    """
    from apps.editorial import permissions

    if actor is not None and not permissions.can_export_user_data(actor, person):
        raise PermissionDenied
    if fmt not in ("json", "zip"):
        raise ValidationError("Formato inválido.")
    content = export_zip(person) if fmt == "zip" else export_json(person)
    audit.record(
        audit.Action.DATA_EXPORTED,
        actor=actor,
        target=person,
        changes={"format": fmt, "own": actor is not None and actor.pk == person.pk},
        request=request,
    )
    mime = "application/zip" if fmt == "zip" else "application/json"
    return content, export_filename(person, fmt), mime


# --- pedir exclusão ---


def last_deletion_request(user: User) -> AuditLog | None:
    return audit.for_target(user).filter(action=audit.Action.DELETION_REQUESTED).first()


def request_deletion(user: User, *, request: HttpRequest | None = None) -> int:
    """A pessoa pede a exclusão da conta: cada administrador ativo recebe um aviso no painel.

    Não apaga nada sozinho (docs/14). Devolve quantos administradores foram avisados.
    """
    from apps.editorial import notifications
    from apps.editorial.models import Notification

    admins = User.objects.filter(is_active=True, role=User.Role.ADMIN).exclude(pk=user.pk)
    message = (
        f"{user.public_name} pediu a exclusão da conta. Exporte os dados se precisar e "
        "anonimize a conta no admin."
    )
    url = reverse("admin:accounts_user_change", args=[user.pk])
    count = 0
    for admin in admins:
        notifications.notify(admin, Notification.Kind.SYSTEM, message, actor=user, url=url)
        count += 1
    audit.record(audit.Action.DELETION_REQUESTED, actor=user, target=user, request=request)
    return count


# --- anonimizar ---


def _scrub(text: str, names: list[str]) -> str:
    for name in names:
        text = text.replace(name, ANONYMIZED_NAME)
    return text


@transaction.atomic
def anonymize_user(actor: User | None, person: User, *, request: HttpRequest | None = None) -> User:
    """Apaga os dados pessoais de uma conta da equipe sem apagar a história (docs/18, docs/23).

    actor None: comando no servidor (anonymize_user). Não dá para desfazer.
    """
    from apps.editorial import permissions
    from apps.editorial.models import EditorialEvent, Notification
    from apps.publications.models import ArticleContributor

    if actor is not None and not permissions.can_anonymize(actor):
        raise PermissionDenied
    person = User.objects.select_for_update().get(pk=person.pk)
    if actor is not None and actor.pk == person.pk:
        raise ValidationError("Você não pode anonimizar a própria conta.")
    if person.is_anonymized:
        raise ValidationError("Esta conta já foi anonimizada.")

    now = timezone.now()
    names = sorted(
        {n for n in (person.full_name, person.display_name) if len(n.strip()) >= 3},
        key=len,
        reverse=True,
    )
    old_role = person.role

    # Créditos: o nome some, a publicação continua no ar e não aponta para perfil nenhum.
    for credit in ArticleContributor.objects.filter(user=person):
        credit.display_name = ANONYMIZED_CREDIT
        credit.save(update_fields=["display_name"])  # o sinal renova o cache público

    # Eventos e avisos de outras pessoas ficam, com o nome trocado.
    mentions = Q()
    for name in names:
        mentions |= Q(note__contains=name)
    for event in EditorialEvent.objects.filter(mentions) if names else []:
        cleaned = _scrub(event.note, names)
        if cleaned != event.note:
            event.note = cleaned
            event.save(update_fields=["note"])
    mentions = Q()
    for name in names:
        mentions |= Q(message__contains=name)
    for notification in Notification.objects.filter(mentions) if names else []:
        cleaned = _scrub(notification.message, names)
        if cleaned != notification.message:
            notification.message = cleaned
            notification.save(update_fields=["message"])
    Notification.objects.filter(user=person).delete()

    # Foto: apagada (fica só se estiver em uso numa publicação, sem o nome no texto alternativo).
    avatar = person.avatar
    services.remove_avatar(person)
    if avatar is not None and type(avatar).objects.filter(pk=avatar.pk).exists():
        avatar.alt_text = ""
        avatar.save(update_fields=["alt_text"])

    # Perfil público some.
    profile = services.ensure_profile(person)
    profile.slug = f"removido-{person.pk}"
    profile.headline = ""
    profile.bio = ""
    profile.education = []
    profile.links = []
    profile.since_year = None
    profile.is_public = False
    profile.show_reviewer_credit = False
    profile.save()
    profile.disciplines.clear()
    profile.areas.clear()
    profile.topics.clear()

    # Login desativado para sempre: sem senha, sem Microsoft, sem links, sem sessões.
    services.end_other_sessions(person, None)
    AccessLink.objects.filter(user=person).delete()
    SocialAccount.objects.filter(user=person).delete()
    EmailAddress.objects.filter(user=person).delete()

    person.full_name = ANONYMIZED_NAME
    person.display_name = ""
    person.email = f"removido-{person.pk}@{ANONYMIZED_EMAIL_DOMAIN}"
    person.set_unusable_password()
    person.role = User.Role.STAFF
    person.staff_kind = User.StaffKind.OTHER
    person.is_active = False
    person.deactivated_at = person.deactivated_at or now
    person.anonymized_at = now
    person.save()

    audit.record(
        audit.Action.USER_ANONYMIZED,
        actor=actor,
        target=person,
        changes={"role": [old_role, person.role]} if old_role != person.role else {},
        request=request,
    )
    return person
