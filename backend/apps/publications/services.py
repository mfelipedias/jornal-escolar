"""Regras de negócio das publicações (docs/04). Views chamam estas funções; nada de regra na view.

Toda função que muda estado confere a permissão em apps/editorial/permissions.py e levanta
PermissionDenied quando o usuário não pode agir.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.editorial import notifications, permissions
from apps.taxonomy.models import ArticleType, Discipline, Topic

from . import rendering
from .credits import student_name_error
from .models import Article, ArticleContributor, ArticleRevision, MediaAsset

TITLE_MAX = 120
REVISION_WINDOW = timedelta(minutes=15)

# Campos que o editor altera diretamente (os demais têm função própria).
EDITABLE_FIELDS = {
    "title",
    "subtitle",
    "type",
    "body_json",
    "cover",
    "cover_caption",
    "event_at",
    "event_location",
    "sources",
    "comments_enabled",
}


@dataclass(frozen=True)
class ChecklistItem:
    code: str
    message: str
    blocking: bool


class ConflictError(Exception):
    """Outra pessoa salvou a publicação depois da versão que o editor carregou."""


class ChecklistError(Exception):
    def __init__(self, items: list[ChecklistItem]) -> None:
        self.items = items
        super().__init__("; ".join(item.message for item in items))


# --- criação e edição ---


@transaction.atomic
def create_article(user: User, **fields: Any) -> Article:
    """Cria um rascunho; quem cria vira autor (docs/04, "criar")."""
    if not permissions.can_create_article(user):
        raise PermissionDenied
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Campos não editáveis: {sorted(unknown)}")
    article = Article.objects.create(created_by=user, **fields)
    ArticleContributor.objects.create(
        article=article,
        user=user,
        display_name=user.public_name,
        role=ArticleContributor.Role.AUTHOR,
    )
    return article


def _locked(article: Article) -> Article:
    """Relê a publicação travando a linha: decisões usam o estado atual do banco, nunca uma
    cópia antiga em memória (que poderia, por exemplo, despublicar um texto ao salvar)."""
    return Article.objects.select_for_update().get(pk=article.pk)


def _sync(target: Article, source: Article, fields: list[str]) -> None:
    for name in fields:
        setattr(target, name, getattr(source, name))


@transaction.atomic
def update_article(
    user: User, article: Article, *, expected_updated_at: datetime | None = None, **fields: Any
) -> Article:
    """Salva alterações. Editar algo já publicado gera uma versão (docs/04, "editar publicada").

    Com expected_updated_at, recusa (ConflictError) se a publicação mudou desde então.
    """
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Campos não editáveis: {sorted(unknown)}")
    current = _locked(article)
    if not permissions.can_edit(user, current):
        raise PermissionDenied
    _check_conflict(user, current, expected_updated_at)
    if "title" in fields and len(fields["title"] or "") > TITLE_MAX:
        raise ValidationError({"title": f"O título pode ter até {TITLE_MAX} caracteres."})

    for name, value in fields.items():
        setattr(current, name, value)
    columns = [Article._meta.get_field(name).attname for name in fields]
    if "body_json" in fields:
        _render_body(user, current)
        columns += ["body_html", "body_text", "reading_minutes"]
    current.last_edited_by = user
    current.save(update_fields=[*columns, "last_edited_by", "updated_at"])
    if current.status == Article.Status.PUBLISHED:
        record_edit_revision(current, user)
    notifications.article_edited_by_other(current, user)
    _sync(article, current, [*columns, "status", "updated_at"])
    return current


def _check_conflict(user: User, current: Article, expected_updated_at: datetime | None) -> None:
    """Conflito só quando outra pessoa salvou depois da versão carregada no editor.

    Salvamentos da própria pessoa (texto e metadados em paralelo) não geram conflito.
    """
    if expected_updated_at is None or current.updated_at == expected_updated_at:
        return
    if current.last_edited_by_id not in (None, user.pk):
        raise ConflictError


def record_edit_revision(article: Article, user: User) -> ArticleRevision:
    """Edição de texto publicado vira versão. Salvamentos seguidos da mesma pessoa em até
    REVISION_WINDOW atualizam a mesma versão, em vez de criar uma a cada autosave."""
    latest = article.revisions.order_by("-number").first()
    if (
        latest is not None
        and latest.reason == ArticleRevision.Reason.EDITED_AFTER_PUBLISH
        and latest.created_by_id == user.pk
        and timezone.now() - latest.created_at < REVISION_WINDOW
    ):
        latest.title, latest.subtitle, latest.body_json = (
            article.title,
            article.subtitle,
            article.body_json,
        )
        latest.save(update_fields=["title", "subtitle", "body_json"])
        return latest
    return create_revision(article, user, ArticleRevision.Reason.EDITED_AFTER_PUBLISH)


def create_revision(article: Article, user: User | None, reason: str) -> ArticleRevision:
    last = article.revisions.aggregate(n=Max("number"))["n"] or 0
    return ArticleRevision.objects.create(
        article=article,
        number=last + 1,
        title=article.title,
        subtitle=article.subtitle,
        body_json=article.body_json,
        reason=reason,
        created_by=user,
    )


# --- créditos ---


@transaction.atomic
def add_staff_credit(
    user: User, article: Article, member: User, role: str = ArticleContributor.Role.COAUTHOR
) -> ArticleContributor:
    if not permissions.can_edit_credits(user, article):
        raise PermissionDenied
    notifications.article_edited_by_other(article, user)
    contributor, _ = ArticleContributor.objects.get_or_create(
        article=article,
        user=member,
        role=role,
        defaults={"display_name": member.public_name, "order": _next_order(article)},
    )
    return contributor


@transaction.atomic
def add_student_credit(
    user: User,
    article: Article,
    *,
    name: str,
    class_group: str = "",
    consent_ok: bool = False,
    role: str = ArticleContributor.Role.AUTHOR,
    full_name_authorized: bool = False,
) -> ArticleContributor:
    """Crédito de aluno: sem conta, com turma e declaração de autorização (docs/04, docs/23)."""
    if not permissions.can_edit_credits(user, article):
        raise PermissionDenied
    error = student_name_error(name, full_name_authorized=full_name_authorized)
    if error:
        raise ValidationError({"name": error})
    notifications.article_edited_by_other(article, user)
    return ArticleContributor.objects.create(
        article=article,
        display_name=" ".join(name.split()),
        role=role,
        is_student=True,
        class_group=class_group.strip(),
        consent_ok=consent_ok,
        order=_next_order(article),
    )


@transaction.atomic
def add_guest_credit(
    user: User,
    article: Article,
    *,
    name: str,
    role: str = ArticleContributor.Role.COLLABORATOR,
    contribution_note: str = "",
) -> ArticleContributor:
    """Crédito sem conta que não é aluno: turma inteira, convidado, Grêmio (docs/04)."""
    if not permissions.can_edit_credits(user, article):
        raise PermissionDenied
    name = " ".join(name.split())
    if not name:
        raise ValidationError({"name": "Informe o nome."})
    if role not in ArticleContributor.Role.values or role == ArticleContributor.Role.REVIEWER:
        raise ValidationError({"role": "Papel inválido."})
    notifications.article_edited_by_other(article, user)
    return ArticleContributor.objects.create(
        article=article,
        display_name=name[:80],
        role=role,
        contribution_note=" ".join(contribution_note.split())[:80],
        order=_next_order(article),
    )


@transaction.atomic
def remove_credit(user: User, article: Article, contributor: ArticleContributor) -> None:
    """Toda publicação precisa de ao menos um membro da equipe como autor ou coautor (docs/16)."""
    if contributor.article_id != article.pk:
        raise PermissionDenied
    if not permissions.can_edit_credits(user, article):
        raise PermissionDenied
    responsible = article.contributors.filter(
        user__isnull=False, role__in=ArticleContributor.EDITING_ROLES
    ).exclude(pk=contributor.pk)
    is_responsible = contributor.user_id and contributor.role in ArticleContributor.EDITING_ROLES
    if is_responsible and not responsible.exists():
        raise ValidationError("A publicação precisa de ao menos um autor ou coautor da equipe.")
    notifications.article_edited_by_other(article, user)
    contributor.delete()


@transaction.atomic
def set_metadata(
    user: User,
    article: Article,
    *,
    type_id: int | None,
    discipline_ids: list[int],
    topic_ids: list[int],
    event_at: datetime | None,
    event_location: str,
    sources: list[dict],
    comments_enabled: bool = True,
) -> Article:
    """Painel lateral do editor: tipo, disciplinas, tópicos, evento, fontes (docs/16)."""
    current = _locked(article)
    if not permissions.can_edit(user, current):
        raise PermissionDenied

    article_type = (
        ArticleType.objects.filter(pk=type_id, is_active=True).first() if type_id else None
    )
    current.type = article_type
    current.event_at = event_at if article_type and article_type.has_event_date else None
    current.event_location = event_location[:120] if current.event_at else ""
    current.sources = clean_sources(sources)
    current.comments_enabled = comments_enabled
    current.last_edited_by = user
    current.save(
        update_fields=[
            "type",
            "event_at",
            "event_location",
            "sources",
            "comments_enabled",
            "last_edited_by",
            "updated_at",
        ]
    )
    current.disciplines.set(Discipline.objects.filter(pk__in=discipline_ids, is_active=True))
    current.topics.set(Topic.objects.filter(pk__in=topic_ids, is_active=True))
    notifications.article_edited_by_other(current, user)
    _sync(article, current, ["type_id", "event_at", "event_location", "sources", "updated_at"])
    return current


@transaction.atomic
def set_cover(user: User, article: Article, asset: MediaAsset | None, caption: str = "") -> Article:
    """Define ou remove a imagem de capa. Só imagens que a pessoa pode usar neste texto."""
    current = _locked(article)
    if not permissions.can_edit(user, current):
        raise PermissionDenied
    if asset is not None and asset.pk not in usable_asset_ids(user, current, {asset.pk}):
        raise PermissionDenied
    if asset is not None and asset.article_id is None:
        MediaAsset.objects.filter(pk=asset.pk).update(article=current)
    current.cover = asset
    current.cover_caption = " ".join(caption.split())[:200] if asset else ""
    current.last_edited_by = user
    current.save(update_fields=["cover", "cover_caption", "last_edited_by", "updated_at"])
    notifications.article_edited_by_other(current, user)
    _sync(article, current, ["cover_id", "cover_caption", "updated_at"])
    return current


def clean_sources(sources: list[dict]) -> list[dict]:
    """Fontes: título obrigatório e URL http(s) válida; linhas vazias são ignoradas."""
    cleaned: list[dict] = []
    errors: list[str] = []
    for index, source in enumerate(sources[:20], start=1):
        title = " ".join(str(source.get("title", "")).split())[:200]
        url = str(source.get("url", "")).strip()[:500]
        publisher = " ".join(str(source.get("publisher", "")).split())[:120]
        if not (title or url or publisher):
            continue
        if not title:
            errors.append(f"Fonte {index}: informe o título.")
        if url and not rendering.safe_href(url, allow_relative=False):
            errors.append(f"Fonte {index}: use um endereço que comece com https://")
        cleaned.append({"title": title, "url": url, "publisher": publisher})
    if errors:
        raise ValidationError({"sources": errors})
    return cleaned


def _next_order(article: Article) -> int:
    return (article.contributors.aggregate(n=Max("order"))["n"] or 0) + 1


# --- corpo ---


def usable_asset_ids(user: User, article: Article, ids: set[int]) -> set[int]:
    """Imagens que esta pessoa pode pôr neste texto: as que ela enviou e ainda estão soltas,
    ou as que já pertencem à publicação. Editores podem usar qualquer uma."""
    assets = MediaAsset.objects.filter(pk__in=ids)
    if not permissions.is_editor(user):
        assets = assets.filter(Q(article=article) | Q(article__isnull=True, uploaded_by=user))
    return set(assets.values_list("pk", flat=True))


def _render_body(user: User, article: Article) -> None:
    """Limpa o documento, gera HTML/texto/tempo de leitura e liga as imagens à publicação."""
    wanted = rendering.collect_asset_ids(rendering.normalize(article.body_json))
    result = rendering.render(article.body_json, usable_asset_ids(user, article, wanted))
    article.body_json = result.document
    article.body_html = result.html
    article.body_text = result.text
    article.reading_minutes = result.reading_minutes
    MediaAsset.objects.filter(pk__in=result.asset_ids, article__isnull=True).update(article=article)


# --- checklist e transições ---


def checklist(article: Article) -> list[ChecklistItem]:
    """Validações antes de publicar (docs/04). Itens com blocking=True impedem a publicação."""
    items: list[ChecklistItem] = []

    def add(code: str, message: str, blocking: bool = True) -> None:
        items.append(ChecklistItem(code, message, blocking))

    title = (article.title or "").strip()
    if not title or title == "Sem título":
        add("title_missing", "Dê um título à publicação.")
    elif len(title) > TITLE_MAX:
        add("title_too_long", f"O título pode ter até {TITLE_MAX} caracteres.")
    if not article.disciplines.exists():
        add("discipline_missing", "Escolha ao menos uma disciplina.")
    if article.type_id is None:
        add("type_missing", "Escolha o tipo de publicação.")
    elif article.type.has_event_date and article.event_at is None:
        add("event_date_missing", "Informe a data do evento.")
    body = rendering.render(article.body_json)
    if body.is_empty:
        add("body_empty", "Escreva o texto da publicação.")
    if article.contributors.filter(is_student=True, consent_ok=False).exists():
        add("student_consent_missing", "Marque a autorização de todos os alunos creditados.")

    asset_ids = set(body.asset_ids)
    if article.cover_id:
        asset_ids.add(article.cover_id)
    if MediaAsset.objects.filter(pk__in=asset_ids, has_people=True, consent_ok=False).exists():
        add("image_consent_missing", "Há imagem com pessoas sem autorização marcada.")

    if not (article.subtitle or "").strip():
        add("subtitle_missing", "Escreva uma linha fina.", blocking=False)
    if article.cover_id and not (article.cover.alt_text or article.cover.is_decorative):
        add("cover_alt_missing", "Descreva a imagem de capa (texto alternativo).", blocking=False)
    return items


def unique_article_slug(article: Article) -> str:
    base = slugify(article.title)[:120] or f"publicacao-{article.pk}"
    slug, n = base, 2
    others = Article.objects.exclude(pk=article.pk)
    while others.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@transaction.atomic
def publish(user: User, article: Article) -> Article:
    current = _locked(article)
    if not permissions.can_publish(user, current):
        raise PermissionDenied
    blocking = [item for item in checklist(current) if item.blocking]
    if blocking:
        raise ChecklistError(blocking)

    if not current.slug:
        current.slug = unique_article_slug(current)  # definitivo a partir daqui
    current.status = Article.Status.PUBLISHED
    current.published_at = current.published_at or timezone.now()
    current.archived_at = None
    fields = ["slug", "status", "published_at", "archived_at", "updated_at"]
    current.save(update_fields=fields)
    create_revision(current, user, ArticleRevision.Reason.PUBLISHED)
    notifications.article_published(current, user)
    _sync(article, current, fields)
    return current


@transaction.atomic
def archive(user: User, article: Article, note: str = "") -> Article:
    """Retira do ar ou abandona. Editor arquivando texto alheio precisa de nota (docs/04)."""
    current = _locked(article)
    if not permissions.can_archive(user, current):
        raise PermissionDenied
    if permissions.archive_requires_note(user, current) and not note.strip():
        raise ValidationError({"note": "Explique por que está arquivando o texto de outra pessoa."})
    current.status = Article.Status.ARCHIVED
    current.archived_at = timezone.now()
    current.is_featured = False
    fields = ["status", "archived_at", "is_featured", "updated_at"]
    current.save(update_fields=fields)
    # A nota também vai para EditorialEvent quando o modelo existir (E29).
    notifications.article_archived(current, user, note)
    _sync(article, current, fields)
    return current


@transaction.atomic
def restore(user: User, article: Article) -> Article:
    current = _locked(article)
    if not permissions.can_restore(user, current):
        raise PermissionDenied
    current.status = Article.Status.DRAFT
    current.archived_at = None
    fields = ["status", "archived_at", "updated_at"]
    current.save(update_fields=fields)
    _sync(article, current, fields)
    return current
