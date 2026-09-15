from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.site_settings import get_setting

from .models import AccessLink, TeacherProfile, User, normalize_email

# --- Login Microsoft (E09) ---


def microsoft_login_enabled() -> bool:
    """Botão da Microsoft disponível: credenciais no servidor e configuração ligada."""
    return settings.MICROSOFT_LOGIN_CONFIGURED and bool(get_setting("auth.microsoft_enabled"))


def email_domain_allowed(email: str) -> bool:
    _, _, domain = normalize_email(email).rpartition("@")
    return bool(domain) and domain in settings.AUTH_ALLOWED_DOMAINS


def microsoft_verified_email(extra_data: dict[str, Any]) -> str:
    """E-mail confiável de uma conta Microsoft: o userPrincipalName.

    O campo "mail" pode ser preenchido livremente pelo administrador de qualquer
    organização Microsoft; o userPrincipalName só aceita domínios verificados da
    organização da conta. Por isso nunca usamos "mail" para achar o usuário.
    Contas convidadas ("#EXT#") não servem.
    """
    upn = normalize_email(str(extra_data.get("userPrincipalName") or ""))
    if "#ext#" in upn:
        return ""
    return upn


def find_staff_account(email: str) -> User | None:
    """Conta pré-cadastrada pelo admin para este e-mail, se existir."""
    if not email:
        return None
    return User.objects.filter(email=normalize_email(email)).first()


# --- Perfil (E10) ---


def unique_profile_slug(name: str, *, exclude_pk: int | None = None) -> str:
    base = slugify(name)[:80] or "perfil"
    slug, n = base, 2
    others = TeacherProfile.objects.exclude(pk=exclude_pk)
    while others.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def ensure_profile(user: User) -> TeacherProfile:
    """Todo usuário tem um perfil; o endereço nasce do nome e não muda sozinho depois."""
    try:
        return user.profile
    except TeacherProfile.DoesNotExist:
        return TeacherProfile.objects.create(user=user, slug=unique_profile_slug(user.public_name))


# --- Links de acesso (E10) ---


class AccessLinkError(Exception):
    pass


@transaction.atomic
def create_access_link(
    user: User,
    *,
    created_by: User | None = None,
    purpose: str | None = None,
) -> AccessLink:
    """Gera um link novo e cancela os anteriores ainda não usados da mesma pessoa."""
    if not user.is_active:
        raise AccessLinkError("Conta desativada: reative antes de gerar um link.")
    if purpose is None:
        purpose = (
            AccessLink.Purpose.PASSWORD_RESET
            if user.has_usable_password()
            else AccessLink.Purpose.FIRST_ACCESS
        )
    now = timezone.now()
    AccessLink.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).update(
        revoked_at=now
    )
    return AccessLink.objects.create(user=user, purpose=purpose, created_by=created_by)


def access_link_url(link: AccessLink) -> str:
    return urljoin(settings.SITE_URL.rstrip("/") + "/", link.get_absolute_url().lstrip("/"))


@transaction.atomic
def use_access_link(link: AccessLink, raw_password: str) -> User:
    """Define a senha e invalida o link. Chamar só com a senha já validada pelo formulário."""
    link = AccessLink.objects.select_for_update().select_related("user").get(pk=link.pk)
    if not link.is_valid:
        raise AccessLinkError("Link inválido.")
    user = link.user
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    link.used_at = timezone.now()
    link.save(update_fields=["used_at"])
    return user


# --- Ativação de contas (E10) ---


def deactivate_user(user: User) -> None:
    user.is_active = False
    user.deactivated_at = timezone.now()
    user.save(update_fields=["is_active", "deactivated_at"])
    AccessLink.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).update(
        revoked_at=user.deactivated_at
    )


def reactivate_user(user: User) -> None:
    if user.anonymized_at is not None:
        raise AccessLinkError("Conta anonimizada: não pode ser reativada.")
    user.is_active = True
    user.deactivated_at = None
    user.save(update_fields=["is_active", "deactivated_at"])


# --- Configuração de perfil e assistente de primeiro acesso (E23) ---

AVATAR_MAX_BYTES = 5 * 1024 * 1024
LINKS_LIMIT = 4
EDUCATION_LIMIT = 6


def needs_onboarding(user: User) -> bool:
    """O assistente aparece até a pessoa concluí-lo ou pulá-lo até o fim."""
    return ensure_profile(user).onboarded_at is None


def complete_onboarding(user: User) -> None:
    profile = ensure_profile(user)
    if profile.onboarded_at is None:
        profile.onboarded_at = timezone.now()
        profile.save(update_fields=["onboarded_at", "updated_at"])


def set_avatar(user: User, uploaded: Any) -> None:
    """Troca a foto: passa pelo mesmo tratamento das imagens do editor, recortada em quadrado.

    Levanta publications.media.MediaError com a mensagem para mostrar.
    """
    from apps.publications import media

    asset = media.process_upload(uploaded, user, max_bytes=AVATAR_MAX_BYTES, square=True)
    asset.alt_text = f"Foto de {user.full_name}"[:250]
    asset.has_people = True
    asset.consent_ok = True  # a própria pessoa envia a própria foto
    asset.save(update_fields=["alt_text", "has_people", "consent_ok"])
    previous = user.avatar
    user.avatar = asset
    user.save(update_fields=["avatar"])
    _discard_avatar(user, previous)


def remove_avatar(user: User) -> None:
    previous = user.avatar
    if previous is None:
        return
    user.avatar = None
    user.save(update_fields=["avatar"])
    _discard_avatar(user, previous)


def _discard_avatar(user: User, asset: Any) -> None:
    """Apaga a foto antiga se foi enviada como foto de perfil e não é usada em outro lugar."""
    if asset is None or asset.uploaded_by_id != user.pk or asset.article_id:
        return
    from apps.publications.models import Article

    if Article.objects.filter(cover=asset).exists():
        return
    if User.objects.filter(avatar=asset).exists():
        return
    asset.delete()


def suggest_topic(name: str) -> Any:
    """Tópico sugerido pela equipe. Novo entra inativo até o admin aprovar (docs/14).

    Devolve o tópico ativo que já existia (para marcar na hora) ou None.
    """
    from apps.taxonomy.models import Topic

    name = " ".join(name.split())[:80]
    slug = slugify(name)
    if not slug:
        return None
    existing = Topic.objects.filter(name__iexact=name).first() or (
        Topic.objects.filter(slug=slug).first()
    )
    if existing:
        return existing if existing.is_active else None
    Topic.objects.create(name=name, slug=slug, is_active=False)
    return None


@transaction.atomic
def update_past_credits(user: User) -> int:
    """Leva o nome de exibição novo aos créditos já existentes.

    Por padrão o crédito guarda o nome do momento em que foi dado (docs/14, "Regras").
    Cada publicação alterada ganha um EditorialEvent de créditos.
    """
    from apps.editorial import events
    from apps.publications.models import ArticleContributor
    from apps.publications.search import update_search_vectors

    credits = (
        ArticleContributor.objects.filter(user=user, is_student=False)
        .exclude(display_name=user.public_name)
        .select_related("article")
    )
    changed = 0
    articles = {}
    for credit in credits:
        credit.display_name = user.public_name
        credit.save(update_fields=["display_name"])  # o sinal renova o cache público
        articles[credit.article_id] = credit.article
        changed += 1
    for article in articles.values():
        events.record(
            article,
            user,
            events.Kind.CONTRIBUTOR_CHANGED,
            note=f"Nome no crédito atualizado para {user.public_name}.",
        )
    update_search_vectors(articles)  # o nome novo também vale na busca
    return changed


@transaction.atomic
def save_profile(
    user: User,
    *,
    user_fields: dict[str, Any] | None = None,
    profile_fields: dict[str, Any] | None = None,
    disciplines: Any = None,
    areas: Any = None,
    topics: Any = None,
    update_credits: bool = False,
) -> TeacherProfile:
    """Grava o que a própria pessoa pode mudar. Cargo, papel e e-mail ficam com o admin.

    None em disciplines/areas/topics significa "não mexer". Áreas vazias com disciplinas
    marcadas são derivadas das disciplinas (docs/14, "Atuação").
    """
    profile = ensure_profile(user)
    allowed_user = {"display_name"}
    user_fields = {k: v for k, v in (user_fields or {}).items() if k in allowed_user}
    if user_fields:
        for key, value in user_fields.items():
            setattr(user, key, value)
        user.save(update_fields=list(user_fields))

    protected = {"id", "user", "user_id", "created_at", "updated_at", "onboarded_at"}
    for key, value in (profile_fields or {}).items():
        if key in protected:
            continue
        setattr(profile, key, value)
    profile.full_clean(exclude=["user"])
    profile.save()

    if disciplines is not None:
        profile.disciplines.set(disciplines)
    if areas is not None:
        chosen = list(areas)
        if not chosen and disciplines:
            chosen = sorted({d.area_id for d in disciplines})
        profile.areas.set(chosen)
    if topics is not None:
        profile.topics.set(topics)
    if update_credits:
        update_past_credits(user)
    return profile


# --- Sessões (docs/23, "Sessões") ---


def user_sessions(user: User) -> list[Any]:
    """Sessões ainda válidas desta pessoa. Poucas contas: decodificar todas é barato."""
    from django.contrib.sessions.models import Session

    sessions = []
    for session in Session.objects.filter(expire_date__gt=timezone.now()).order_by("-expire_date"):
        if str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
            sessions.append(session)
    return sessions


def end_other_sessions(user: User, keep_session_key: str | None) -> int:
    """Sair de todas as outras sessões": apaga as sessões da pessoa, menos a atual."""
    ended = 0
    for session in user_sessions(user):
        if session.session_key != keep_session_key:
            session.delete()
            ended += 1
    return ended
