"""Regras de negócio das publicações (docs/04). Views chamam estas funções; nada de regra na view.

Toda função que muda estado confere a permissão em apps/editorial/permissions.py e levanta
PermissionDenied quando o usuário não pode agir.
"""

import copy as copy_module
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Max, Q
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.editorial import events, notifications, permissions
from apps.editorial import selectors as editorial_selectors
from apps.editorial import services as editorial_services
from apps.taxonomy.models import ArticleType, Discipline, Topic

from . import rendering
from .cache import invalidate_public_content
from .credits import generic_student_name, student_name_error
from .media import copy_asset
from .models import Article, ArticleContributor, ArticleRevision, MediaAsset

Status = Article.Status
EventKind = events.Kind

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


COPIED_FIELDS = (
    "subtitle",
    "type",
    "cover_caption",
    "event_at",
    "event_location",
    "sources",
    "comments_enabled",
)
COPY_SUFFIX = " (cópia)"


@transaction.atomic
def duplicate_article(user: User, article: Article) -> Article:
    """Duplicar como rascunho (docs/15, "Minhas publicações").

    Copia texto, capa, tipo, disciplinas, tópicos, evento e fontes. As imagens viram cópias
    novas, porque cada imagem pertence a uma publicação só. Quem duplica vira autor; os outros
    créditos (coautores, alunos, convidados) vêm junto, sem revisão e edição.
    Pode levantar media.MediaError se a cópia das imagens passar da cota.
    """
    if not permissions.can_duplicate(user, article):
        raise PermissionDenied
    title = article.title[: TITLE_MAX - len(COPY_SUFFIX)].rstrip() + COPY_SUFFIX
    duplicate = Article.objects.create(
        title=title,
        created_by=user,
        last_edited_by=user,
        **{name: getattr(article, name) for name in COPIED_FIELDS},
    )
    duplicate.disciplines.set(article.disciplines.all())
    duplicate.topics.set(article.topics.all())

    wanted = rendering.collect_asset_ids(rendering.normalize(article.body_json))
    if article.cover_id:
        wanted.add(article.cover_id)
    mapping = {
        asset.pk: copy_asset(asset, user, duplicate).pk
        for asset in MediaAsset.objects.filter(pk__in=wanted)
    }
    body = copy_module.deepcopy(article.body_json or {})
    _remap_figures(body, mapping)
    result = rendering.render(body, set(mapping.values()))
    duplicate.body_json = result.document
    duplicate.body_html = result.html
    duplicate.body_text = result.text
    duplicate.reading_minutes = result.reading_minutes
    duplicate.cover_id = mapping.get(article.cover_id)
    if duplicate.cover_id is None:
        duplicate.cover_caption = ""
    duplicate.save()

    ArticleContributor.objects.create(
        article=duplicate,
        user=user,
        display_name=user.public_name,
        role=ArticleContributor.Role.AUTHOR,
    )
    skipped_roles = (ArticleContributor.Role.REVIEWER, ArticleContributor.Role.EDITOR)
    for credit in article.contributors.exclude(role__in=skipped_roles).order_by("order", "pk"):
        if credit.user_id == user.pk:
            continue
        ArticleContributor.objects.create(
            article=duplicate,
            user_id=credit.user_id,
            display_name=credit.display_name,
            role=credit.role,
            is_student=credit.is_student,
            class_group=credit.class_group,
            consent_ok=credit.consent_ok,
            contribution_note=credit.contribution_note,
            show_in_credits=credit.show_in_credits,
            anonymized_at=credit.anonymized_at,
            order=credit.order + 1,
        )
    return duplicate


def _remap_figures(node: dict, mapping: dict[int, int]) -> None:
    """Troca os ids das imagens do documento pelos das cópias (sem cópia, a figura some)."""
    if not isinstance(node, dict):
        return
    attrs = node.get("attrs")
    if node.get("type") == "figure" and isinstance(attrs, dict):
        attrs["assetId"] = mapping.get(attrs.get("assetId"), 0)
    for child in node.get("content", []) or []:
        _remap_figures(child, mapping)


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
    if current.status == Status.PUBLISHED:
        record_edit_revision(current, user)
        events.record_edit(current, user, EventKind.EDITED_AFTER_PUBLISH)
    _after_edit(current, user)
    _sync(article, current, [*columns, "status", "updated_at"])
    return current


def _after_edit(article: Article, user: User) -> None:
    """Efeitos de qualquer edição: aviso e evento quando quem edita não assina o texto
    (editor, admin ou revisor); aviso ao revisor quando o autor mexe durante a revisão."""
    if permissions.is_author(user, article):
        if article.status == Status.IN_REVIEW:
            reviewer = permissions.reviewer_credit(article)
            if reviewer is not None:
                notifications.edited_during_review(article, user, reviewer.user)
        return
    notifications.article_edited_by_other(article, user)
    events.record_edit(article, user, EventKind.EDITED_BY_THIRD_PARTY)


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
    if role == ArticleContributor.Role.REVIEWER:
        raise ValidationError("Para convidar um revisor, use “Pedir revisão”.")
    notifications.article_edited_by_other(article, user)
    contributor, created = ArticleContributor.objects.get_or_create(
        article=article,
        user=member,
        role=role,
        defaults={"display_name": member.public_name, "order": _next_order(article)},
    )
    if created:
        _credit_event(article, user, contributor, "adicionado")
    return contributor


def _credit_event(article: Article, user: User, credit: ArticleContributor, action: str) -> None:
    """Evento de créditos. Nome só de quem é da equipe; aluno e convidado ficam sem nome
    na auditoria (docs/23: o crédito pode ser anonimizado depois)."""
    role = credit.get_role_display()
    if credit.user_id:
        what = f"{credit.display_name} ({role})"
    elif credit.is_student:
        what = f"Crédito de aluno ({role})"
    else:
        what = f"Crédito sem conta ({role})"
    events.record(article, user, EventKind.CONTRIBUTOR_CHANGED, note=f"{what} {action}.")


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
    credit = ArticleContributor.objects.create(
        article=article,
        display_name=" ".join(name.split()),
        role=role,
        is_student=True,
        class_group=class_group.strip(),
        consent_ok=consent_ok,
        order=_next_order(article),
    )
    _credit_event(article, user, credit, "adicionado")
    return credit


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
    credit = ArticleContributor.objects.create(
        article=article,
        display_name=name[:80],
        role=role,
        contribution_note=" ".join(contribution_note.split())[:80],
        order=_next_order(article),
    )
    _credit_event(article, user, credit, "adicionado")
    return credit


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
    if contributor.role == ArticleContributor.Role.REVIEWER and article.status == Status.IN_REVIEW:
        raise ValidationError("Para trocar o revisor, cancele o pedido de revisão.")
    notifications.article_edited_by_other(article, user)
    _credit_event(article, user, contributor, "removido")
    contributor.delete()


@transaction.atomic
def anonymize_student_credit(
    user: User, contributor: ArticleContributor, *, request: Any = None
) -> ArticleContributor:
    """Troca o nome do aluno por um crédito genérico, sem despublicar (docs/23, docs/18).

    Para quando a família pede a retirada do nome ou revoga a autorização. A turma sai; fica
    só a série ("Aluno da 2ª série"). Um crédito anonimizado não identifica ninguém, então
    deixa de exigir autorização na checklist e nos alertas. Não dá para desfazer.
    """
    from apps.core import audit

    if not permissions.can_anonymize(user):
        raise PermissionDenied
    contributor = ArticleContributor.objects.select_for_update().get(pk=contributor.pk)
    if not contributor.is_student:
        raise ValidationError("Só créditos de aluno são anonimizados aqui.")
    if contributor.anonymized_at is not None:
        return contributor
    contributor.display_name = generic_student_name(contributor.class_group)
    contributor.class_group = ""
    contributor.anonymized_at = timezone.now()
    contributor.save(update_fields=["display_name", "class_group", "anonymized_at"])
    events.record(
        contributor.article,
        user,
        EventKind.CREDIT_ANONYMIZED,
        note=f"Crédito de aluno ({contributor.get_role_display()}) anonimizado.",
    )
    audit.record(
        audit.Action.CREDIT_ANONYMIZED,
        actor=user,
        target=contributor,
        changes={"article": contributor.article_id},
        request=request,
    )
    return contributor


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
    _after_edit(current, user)
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
    _after_edit(current, user)
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
    if article.contributors.filter(
        is_student=True, consent_ok=False, anonymized_at__isnull=True
    ).exists():
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


def _set_status(
    current: Article, user: User, status: str, fields: list[str], note: str = ""
) -> None:
    """Grava a mudança de estado e o evento dela (docs/04: toda transição gera
    EditorialEvent). fields são as outras colunas alteradas antes da chamada."""
    from_status = current.status
    current.status = status
    current.save(update_fields=list(dict.fromkeys(["status", *fields, "updated_at"])))
    events.status_change(current, user, from_status, note)


def _publish_locked(user: User, current: Article) -> list[str]:
    """Publica a publicação já travada. Devolve as colunas alteradas."""
    blocking = [item for item in checklist(current) if item.blocking]
    if blocking:
        raise ChecklistError(blocking)
    if not current.slug:
        current.slug = unique_article_slug(current)  # definitivo a partir daqui
    current.published_at = current.published_at or timezone.now()
    current.archived_at = None
    fields = ["slug", "published_at", "archived_at"]
    _set_status(current, user, Status.PUBLISHED, fields)
    create_revision(current, user, ArticleRevision.Reason.PUBLISHED)
    notifications.article_published(current, user)
    return ["status", *fields, "updated_at"]


@transaction.atomic
def publish(user: User, article: Article) -> Article:
    current = _locked(article)
    if not permissions.can_publish(user, current):
        raise PermissionDenied
    _sync(article, current, _publish_locked(user, current))
    return current


@transaction.atomic
def archive(user: User, article: Article, note: str = "") -> Article:
    """Retira do ar ou abandona. Editor arquivando texto alheio precisa de nota (docs/04)."""
    current = _locked(article)
    if not permissions.can_archive(user, current):
        raise PermissionDenied
    if permissions.archive_requires_note(user, current) and not note.strip():
        raise ValidationError({"note": "Explique por que está arquivando o texto de outra pessoa."})
    current.archived_at = timezone.now()
    current.is_featured = False
    current.featured_order = None
    fields = ["archived_at", "is_featured", "featured_order"]
    _set_status(current, user, Status.ARCHIVED, fields, note)
    notifications.article_archived(current, user, note)
    _sync(article, current, ["status", *fields, "updated_at"])
    return current


@transaction.atomic
def restore(user: User, article: Article) -> Article:
    current = _locked(article)
    if not permissions.can_restore(user, current):
        raise PermissionDenied
    current.archived_at = None
    _set_status(current, user, Status.DRAFT, ["archived_at"])
    _sync(article, current, ["status", "archived_at", "updated_at"])
    return current


# --- revisão por colega (docs/04, docs/17) ---

CHANGES_WITHOUT_COMMENT = "Deixe ao menos um comentário antes de sugerir alterações."


@transaction.atomic
def request_review(
    user: User, article: Article, reviewer: User, *, note: str = "", can_publish: bool = False
) -> Article:
    """Pede (ou reenvia) a revisão a um colega (docs/04, "pedir revisão").

    Há um revisor por vez: escolher outro colega substitui o anterior. can_publish é o
    "pode publicar por mim" do autor.
    """
    current = _locked(article)
    if not permissions.can_request_review(user, current):
        raise PermissionDenied
    if reviewer.pk == user.pk or not permissions.can_be_reviewer(reviewer, current):
        raise ValidationError({"reviewer": "Escolha um colega ativo que não assine este texto."})
    note = note.strip()
    previous = current.contributors.filter(role=ArticleContributor.Role.REVIEWER)
    for old in previous.exclude(user=reviewer):
        _credit_event(current, user, old, "removido")
        old.delete()
    credit, _ = ArticleContributor.objects.get_or_create(
        article=current,
        user=reviewer,
        role=ArticleContributor.Role.REVIEWER,
        defaults={"display_name": reviewer.public_name, "order": _next_order(current)},
    )
    if credit.can_publish != can_publish:
        credit.can_publish = can_publish
        credit.save(update_fields=["can_publish"])

    current.submitted_at = timezone.now()
    _set_status(current, user, Status.IN_REVIEW, ["submitted_at"], note)
    create_revision(current, user, ArticleRevision.Reason.SUBMITTED)
    permission = "pode publicar" if can_publish else "só devolve ao autor"
    events.record(
        current, user, EventKind.REVIEWER_ASSIGNED, note=f"{reviewer.public_name} ({permission})."
    )
    notifications.review_requested(current, user, reviewer, note)
    _sync(article, current, ["status", "submitted_at", "updated_at"])
    return current


def _remove_reviewer(current: Article, user: User, reason: str) -> User | None:
    credit = permissions.reviewer_credit(current)
    if credit is None:
        return None
    events.record(
        current, user, EventKind.REVIEWER_REMOVED, note=f"{credit.display_name}: {reason}"
    )
    reviewer = credit.user
    credit.delete()
    return reviewer


@transaction.atomic
def reassign_reviewer(user: User, article: Article, reviewer: User, note: str = "") -> Article:
    """Editor troca o revisor de um texto em revisão (docs/18, "reatribuir revisor").

    O estado não muda. O "pode publicar por mim" foi dado pelo autor a um colega específico,
    então não passa para o novo revisor.
    """
    current = _locked(article)
    if not permissions.can_reassign_reviewer(user, current):
        raise PermissionDenied
    if not permissions.can_be_reviewer(reviewer, current):
        raise ValidationError({"reviewer": "Escolha um colega ativo que não assine este texto."})
    old_credit = permissions.reviewer_credit(current)
    if old_credit is not None and old_credit.user_id == reviewer.pk:
        raise ValidationError({"reviewer": "Este colega já é o revisor."})
    old = _remove_reviewer(current, user, "revisão passada para outro colega.")
    ArticleContributor.objects.create(
        article=current,
        user=reviewer,
        role=ArticleContributor.Role.REVIEWER,
        display_name=reviewer.public_name,
        order=_next_order(current),
    )
    events.record(
        current,
        user,
        EventKind.REVIEWER_ASSIGNED,
        note=f"{reviewer.public_name} (só devolve ao autor). {note.strip()}".strip(),
    )
    # Sem salvar a publicação: mudar updated_at acusaria conflito no editor de quem escreve.
    notifications.reviewer_replaced(current, user, old, reviewer, note)
    return current


@transaction.atomic
def cancel_review(user: User, article: Article) -> Article:
    """O autor desiste do pedido: volta a rascunho e o revisor é avisado."""
    current = _locked(article)
    if not permissions.can_cancel_review(user, current):
        raise PermissionDenied
    _set_status(current, user, Status.DRAFT, [])
    reviewer = _remove_reviewer(current, user, "pedido cancelado.")
    if reviewer is not None:
        notifications.review_cancelled(current, user, reviewer)
    _sync(article, current, ["status", "updated_at"])
    return current


@transaction.atomic
def decline_review(user: User, article: Article, note: str = "") -> Article:
    """O revisor não pode revisar: volta a rascunho para o autor escolher outro colega."""
    current = _locked(article)
    if not permissions.can_decline_review(user, current):
        raise PermissionDenied
    _set_status(current, user, Status.DRAFT, [], note)
    _remove_reviewer(current, user, "revisão recusada.")
    notifications.review_declined(current, user, note)
    _sync(article, current, ["status", "updated_at"])
    return current


@transaction.atomic
def request_changes(user: User, article: Article, note: str = "") -> Article:
    """Sugerir alterações: devolve aos autores com ao menos um comentário aberto (docs/17).

    A nota, se houver, vira um comentário geral aberto e fica no evento da mudança de estado.
    """
    current = _locked(article)
    if not permissions.can_review(user, current):
        raise PermissionDenied
    note = note.strip()
    if not note and not editorial_selectors.open_comment_count(current):
        raise ValidationError({"note": CHANGES_WITHOUT_COMMENT})
    if note:
        editorial_services.add_note_comment(user, current, note)
    _set_status(current, user, Status.CHANGES_REQUESTED, [], note)
    notifications.changes_requested(
        current, user, note, editorial_selectors.open_comment_count(current)
    )
    _sync(article, current, ["status", "updated_at"])
    return current


@transaction.atomic
def approve(user: User, article: Article, note: str = "") -> Article:
    """Aprovar: volta a rascunho com o selo "revisado"; o autor publica quando quiser."""
    current = _locked(article)
    if not permissions.can_review(user, current):
        raise PermissionDenied
    _set_status(current, user, Status.DRAFT, [])
    events.record(current, user, EventKind.APPROVED, note=note)
    notifications.review_approved(current, user, note)
    _sync(article, current, ["status", "updated_at"])
    return current


@transaction.atomic
def approve_and_publish(user: User, article: Article, note: str = "") -> Article:
    """Aprovar e publicar: revisor com "pode publicar por mim", editor ou admin."""
    current = _locked(article)
    if not permissions.can_approve_and_publish(user, current):
        raise PermissionDenied
    columns = _publish_locked(user, current)  # checklist primeiro: sem ela, nada é gravado
    events.record(current, user, EventKind.APPROVED, note=note)
    _sync(article, current, columns)
    return current


@transaction.atomic
def resume(user: User, article: Article) -> Article:
    """Depois de alterações sugeridas, o autor retoma o texto como rascunho."""
    current = _locked(article)
    if not permissions.can_resume(user, current):
        raise PermissionDenied
    _set_status(current, user, Status.DRAFT, [])
    _sync(article, current, ["status", "updated_at"])
    return current


# --- destaques da home (docs/10, docs/18) ---

MAX_FEATURED = 3


def featured_ids() -> list[int]:
    """Destaques marcados hoje, na ordem da home (sem as mais recentes que completam o bloco)."""
    return list(
        Article.objects.filter(status=Article.Status.PUBLISHED, is_featured=True)
        .order_by(F("featured_order").asc(nulls_last=True), "-published_at")
        .values_list("pk", flat=True)
    )


@transaction.atomic
def set_featured(user: User, article_ids: list[int]) -> list[int]:
    """Define os destaques da home, na ordem dada. Quem sai da lista deixa de ser destaque.

    Só publicações no ar entram. Quem entra agora precisa ter capa (docs/18); um destaque
    antigo sem capa pode continuar e ser reordenado (a home usa o layout tipográfico).
    """
    if not permissions.can_feature(user):
        raise PermissionDenied
    ids = list(dict.fromkeys(article_ids))
    if len(ids) > MAX_FEATURED:
        raise ValidationError(f"A página inicial mostra até {MAX_FEATURED} destaques.")
    current = set(featured_ids())
    articles = Article.objects.select_for_update().in_bulk(ids)
    for pk in ids:
        article = articles.get(pk)
        if article is None or article.status != Article.Status.PUBLISHED:
            raise ValidationError("Só publicações que estão no ar podem ser destaque.")
        if pk not in current and not article.cover_id:
            raise ValidationError(
                f"“{article.title}” não tem imagem de capa. Destaques precisam de capa."
            )
    # .update() não dispara sinais nem mexe em updated_at (não gera conflito no editor);
    # por isso a versão do conteúdo público sobe aqui.
    Article.objects.filter(is_featured=True).exclude(pk__in=ids).update(
        is_featured=False, featured_order=None
    )
    for order, pk in enumerate(ids, start=1):
        Article.objects.filter(pk=pk).update(is_featured=True, featured_order=order)
    invalidate_public_content()
    return ids


def feature(user: User, article: Article) -> list[int]:
    ids = featured_ids()
    if article.pk in ids:
        return ids
    if len(ids) >= MAX_FEATURED:
        raise ValidationError(
            f"Já há {MAX_FEATURED} destaques. Remova um antes de adicionar outro."
        )
    return set_featured(user, [*ids, article.pk])


def unfeature(user: User, article: Article) -> list[int]:
    return set_featured(user, [pk for pk in featured_ids() if pk != article.pk])


def move_featured(user: User, article: Article, step: int) -> list[int]:
    """Sobe (step=-1) ou desce (step=1) um lugar na ordem dos destaques."""
    ids = featured_ids()
    if article.pk not in ids:
        raise ValidationError("Esta publicação não está nos destaques.")
    index = ids.index(article.pk)
    target = index + step
    if 0 <= target < len(ids):
        ids[index], ids[target] = ids[target], ids[index]
    return set_featured(user, ids)
