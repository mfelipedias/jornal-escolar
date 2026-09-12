"""Regras de negócio das publicações (docs/04). Views chamam estas funções; nada de regra na view.

Toda função que muda estado confere a permissão em apps/editorial/permissions.py e levanta
PermissionDenied quando o usuário não pode agir.
"""

import contextlib
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.editorial import permissions

from .credits import student_name_error
from .models import Article, ArticleContributor, ArticleRevision, MediaAsset

TITLE_MAX = 120

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
def update_article(user: User, article: Article, **fields: Any) -> Article:
    """Salva alterações. Editar algo já publicado gera uma versão (docs/04, "editar publicada")."""
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Campos não editáveis: {sorted(unknown)}")
    current = _locked(article)
    if not permissions.can_edit(user, current):
        raise PermissionDenied
    if "title" in fields and len(fields["title"] or "") > TITLE_MAX:
        raise ValidationError({"title": f"O título pode ter até {TITLE_MAX} caracteres."})

    for name, value in fields.items():
        setattr(current, name, value)
    columns = [Article._meta.get_field(name).attname for name in fields]
    current.save(update_fields=[*columns, "updated_at"])
    if current.status == Article.Status.PUBLISHED:
        create_revision(current, user, ArticleRevision.Reason.EDITED_AFTER_PUBLISH)
    _sync(article, current, [*columns, "status", "updated_at"])
    return current


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
    return ArticleContributor.objects.create(
        article=article,
        display_name=" ".join(name.split()),
        role=role,
        is_student=True,
        class_group=class_group.strip(),
        consent_ok=consent_ok,
        order=_next_order(article),
    )


def _next_order(article: Article) -> int:
    return (article.contributors.aggregate(n=Max("order"))["n"] or 0) + 1


# --- corpo ---


def body_has_text(body_json: dict) -> bool:
    """O documento do editor tem algum texto ou imagem? (renderizador completo na E13)"""
    stack = [body_json] if isinstance(body_json, dict) else []
    while stack:
        node = stack.pop()
        if node.get("type") == "text" and str(node.get("text", "")).strip():
            return True
        if node.get("type") in ("image", "figure"):
            return True
        stack.extend(child for child in node.get("content", []) if isinstance(child, dict))
    return False


def body_asset_ids(body_json: dict) -> set[int]:
    ids: set[int] = set()
    stack = [body_json] if isinstance(body_json, dict) else []
    while stack:
        node = stack.pop()
        asset_id = (node.get("attrs") or {}).get("assetId")
        if asset_id is not None:
            with contextlib.suppress(TypeError, ValueError):
                ids.add(int(asset_id))
        stack.extend(child for child in node.get("content", []) if isinstance(child, dict))
    return ids


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
    if not body_has_text(article.body_json):
        add("body_empty", "Escreva o texto da publicação.")
    if article.contributors.filter(is_student=True, consent_ok=False).exists():
        add("student_consent_missing", "Marque a autorização de todos os alunos creditados.")

    asset_ids = body_asset_ids(article.body_json)
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
    # A nota vai para EditorialEvent quando o modelo existir (E29); a notificação, na E17.
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
