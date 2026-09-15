"""Telas e endpoints do editor de publicações (docs/16, docs/07)."""

import json
from datetime import datetime
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import User
from apps.core.http import json_error
from apps.core.ratelimit import hit
from apps.editorial import permissions
from apps.editorial import selectors as editorial_selectors

from . import media, selectors, services
from .models import Article, ArticleContributor, MediaAsset
from .views import login_required_json

# --- telas ---


@login_required
@require_http_methods(["GET", "POST"])
def create(request: HttpRequest) -> HttpResponse:
    """/painel/publicacoes/nova/: GET mostra o convite; POST cria o rascunho e abre o editor."""
    if not permissions.can_create_article(request.user):
        raise PermissionDenied
    if request.method == "POST":
        article = services.create_article(request.user)
        return redirect("publications:edit", pk=article.pk)
    return render(request, "publications/create.html")


def _editable_article(request: HttpRequest, pk: int) -> Article:
    article = get_object_or_404(Article.objects.select_related("type"), pk=pk)
    if not permissions.can_edit(request.user, article):
        raise PermissionDenied
    return article


def sidebar_context(request: HttpRequest, article: Article, **extra: Any) -> dict[str, Any]:
    items = services.checklist(article)
    blocking = [item for item in items if item.blocking]
    return {
        "article": article,
        "types": selectors.active_types(),
        "areas": selectors.areas_with_disciplines(),
        "topics": selectors.active_topics(),
        "selected_disciplines": set(article.disciplines.values_list("pk", flat=True)),
        "selected_topics": set(article.topics.values_list("pk", flat=True)),
        "contributors": selectors.contributors(article),
        "roles": [
            r for r in ArticleContributor.Role.choices if r[0] != ArticleContributor.Role.REVIEWER
        ],
        "student_roles": [
            r
            for r in ArticleContributor.Role.choices
            if r[0] in ("author", "coauthor", "collaborator")
        ],
        "article_images": article.media_assets.order_by("-created_at")[:24],
        "checklist": items,
        "blocking": blocking,
        "can_publish": permissions.can_publish(request.user, article),
        "can_archive": permissions.can_archive(request.user, article),
        "can_restore": permissions.can_restore(request.user, article),
        "can_anonymize": permissions.can_anonymize(request.user),
        "archive_requires_note": permissions.archive_requires_note(request.user, article),
        **review_context(request, article),
        "event_at_local": (
            timezone.localtime(article.event_at).strftime("%Y-%m-%dT%H:%M")
            if article.event_at
            else ""
        ),
        **extra,
    }


def review_context(request: HttpRequest, article: Article) -> dict[str, Any]:
    """Revisão por colega no editor: estado, quem revisa e o que a pessoa pode fazer."""
    user = request.user
    can_request = permissions.can_request_review(user, article)
    summary = editorial_selectors.review_summary(article)
    profile = getattr(user, "profile", None)
    return {
        "review": summary,
        "can_request_review": can_request,
        "can_cancel_review": permissions.can_cancel_review(user, article),
        "can_review": permissions.can_review(user, article),
        "can_resume": permissions.can_resume(user, article),
        "reviewer_candidates": (
            editorial_selectors.reviewer_candidates(article, user) if can_request else []
        ),
        "current_reviewer_id": summary.reviewer.user_id if summary.reviewer else None,
        "default_can_publish": (
            summary.reviewer.can_publish
            if summary.reviewer
            else bool(profile and profile.reviewers_may_publish)
        ),
    }


@login_required
def edit(request: HttpRequest, pk: int) -> HttpResponse:
    """/painel/publicacoes/<id>/editar/"""
    article = _editable_article(request, pk)
    editor_data = {
        "articleId": article.pk,
        "title": "" if article.title == "Sem título" else article.title,
        "subtitle": article.subtitle,
        "body": article.body_json or {"type": "doc", "content": []},
        "updatedAt": article.updated_at.isoformat(),
        "saveUrl": reverse("publications:save_body", args=[article.pk]),
        "mediaUrl": reverse("publications:media_upload"),
        "status": article.status,
    }
    context = sidebar_context(request, article, editor_data=editor_data)
    return render(request, "publications/editor.html", context)


# --- autosave do corpo ---


def _payload(request: HttpRequest) -> dict[str, Any] | JsonResponse:
    if len(request.body) > settings.EDITOR_MAX_BODY_BYTES:
        return json_error("too_large", "O texto ficou grande demais para salvar.", 413)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)
    if not isinstance(payload, dict):
        return json_error("invalid_json", "Corpo da requisição inválido.", 400)
    return payload


@require_http_methods(["PUT"])
@login_required_json
def save_body(request: HttpRequest, pk: int) -> JsonResponse:
    """PUT /x/articles/<id>/body/: autosave de título, linha fina e corpo (docs/16, "Autosave")."""
    article = get_object_or_404(Article, pk=pk)
    payload = _payload(request)
    if isinstance(payload, JsonResponse):
        return payload

    fields: dict[str, Any] = {}
    if "title" in payload:
        fields["title"] = " ".join(str(payload["title"] or "").split()) or "Sem título"
    if "subtitle" in payload:
        fields["subtitle"] = " ".join(str(payload["subtitle"] or "").split())[:220]
    if "body_json" in payload:
        fields["body_json"] = payload["body_json"]
    expected = parse_datetime(str(payload.get("updated_at") or ""))

    try:
        saved = services.update_article(
            request.user, article, expected_updated_at=expected, **fields
        )
    except PermissionDenied:
        return json_error("forbidden", "Você não pode editar esta publicação.", 403)
    except services.ConflictError:
        return json_error(
            "conflict",
            "Este texto foi alterado por outra pessoa. Recarregue para ver as mudanças.",
            409,
        )
    except ValidationError as exc:
        return json_error("invalid", "Revise os campos.", 400, fields=exc.message_dict)

    return JsonResponse(
        {
            "saved_at": timezone.localtime(saved.updated_at).strftime("%H:%M"),
            "updated_at": saved.updated_at.isoformat(),
            "reading_minutes": saved.reading_minutes,
            "status": saved.status,
        }
    )


# --- painel lateral (HTMX) ---


def _with_updated_at(response: HttpResponse, article: Article) -> HttpResponse:
    """Avisa o editor do novo updated_at (evita falso conflito no próximo autosave)."""
    article.refresh_from_db(fields=["updated_at"])
    response["HX-Trigger"] = json.dumps(
        {"articleUpdated": {"updatedAt": article.updated_at.isoformat()}}
    )
    return response


def _int_list(data: QueryDict, key: str) -> list[int]:
    return [int(v) for v in data.getlist(key) if str(v).isdigit()]


def _parse_local_datetime(value: str) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValidationError({"event_at": "Data inválida."})
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


@require_POST
@login_required
def save_meta(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/meta/ → formulário de metadados + checklist (OOB)."""
    article = _editable_article(request, pk)
    data = request.POST
    sources = [
        {"title": t, "url": u, "publisher": p}
        for t, u, p in zip(
            data.getlist("source_title"),
            data.getlist("source_url"),
            data.getlist("source_publisher"),
            strict=False,
        )
    ]
    errors: dict[str, list[str]] = {}
    try:
        services.set_metadata(
            request.user,
            article,
            type_id=int(data["type"]) if data.get("type", "").isdigit() else None,
            discipline_ids=_int_list(data, "disciplines"),
            topic_ids=_int_list(data, "topics"),
            event_at=_parse_local_datetime(data.get("event_at", "")),
            event_location=" ".join(data.get("event_location", "").split()),
            sources=sources,
            comments_enabled=data.get("comments_enabled") == "on",
        )
    except ValidationError as exc:
        errors = exc.message_dict
    article.refresh_from_db()
    context = sidebar_context(
        request, article, meta_errors=errors, meta_sources=sources if errors else None
    )
    response = render(request, "publications/partials/meta_response.html", context)
    return _with_updated_at(response, article)


@require_http_methods(["GET", "POST"])
@login_required
def save_cover(request: HttpRequest, pk: int) -> HttpResponse:
    """/x/articles/<id>/cover/: GET atualiza a seção (novas imagens no texto); POST envia nova
    capa (file), escolhe uma imagem (asset) ou remove (remove)."""
    article = _editable_article(request, pk)
    if request.method == "GET":
        return render(
            request, "publications/partials/cover.html", sidebar_context(request, article)
        )
    error = ""
    try:
        if request.POST.get("remove"):
            services.set_cover(request.user, article, None)
        elif request.FILES.get("file"):
            if not hit(
                f"media-upload:{request.user.pk}",
                limit=settings.MEDIA_UPLOADS_PER_HOUR,
                period=3600,
            ):
                raise media.MediaError("rate_limited", "Muitos envios em pouco tempo.", 429)
            asset = media.process_upload(request.FILES["file"], request.user, article=article)
            services.set_cover(request.user, article, asset, request.POST.get("cover_caption", ""))
        else:
            asset = get_object_or_404(MediaAsset, pk=request.POST.get("asset"))
            services.set_cover(request.user, article, asset, request.POST.get("cover_caption", ""))
    except media.MediaError as exc:
        error = exc.message
    article.refresh_from_db()
    context = sidebar_context(request, article, cover_error=error)
    return _with_updated_at(
        render(request, "publications/partials/cover_response.html", context), article
    )


@require_GET
@login_required
def checklist(request: HttpRequest, pk: int) -> HttpResponse:
    """GET /x/articles/<id>/checklist/ (atualizado depois de cada autosave)."""
    article = _editable_article(request, pk)
    return render(
        request, "publications/partials/checklist_response.html", sidebar_context(request, article)
    )


@require_POST
@login_required
def add_contributor(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/contributors/ (kind = staff | student | guest)."""
    article = _editable_article(request, pk)
    data = request.POST
    kind = data.get("kind")
    error = ""
    try:
        if kind == "staff":
            member = get_object_or_404(User, pk=data.get("user_id"), is_active=True)
            role = data.get("staff_role") or data.get("role") or ArticleContributor.Role.COAUTHOR
            if role not in ArticleContributor.Role.values:
                raise ValidationError("Papel inválido.")
            services.add_staff_credit(request.user, article, member, role)
        elif kind == "student":
            services.add_student_credit(
                request.user,
                article,
                name=data.get("name", ""),
                class_group=data.get("class_group", ""),
                consent_ok=data.get("consent_ok") == "on",
                role=data.get("role")
                if data.get("role") in ("author", "coauthor", "collaborator")
                else "author",
                full_name_authorized=data.get("full_name_authorized") == "on",
            )
        elif kind == "guest":
            services.add_guest_credit(
                request.user,
                article,
                name=data.get("name", ""),
                role=data.get("role") or ArticleContributor.Role.COLLABORATOR,
                contribution_note=data.get("contribution_note", ""),
            )
        else:
            raise ValidationError("Tipo de crédito inválido.")
    except ValidationError as exc:
        error = " ".join(exc.messages)
    # Com erro, o formulário reabre preenchido; com sucesso, fecha.
    context = sidebar_context(
        request,
        article,
        credit_error=error,
        credit_kind=kind if error else "",
        credit_data=data if error else None,
    )
    return _with_updated_at(
        render(request, "publications/partials/credits_response.html", context), article
    )


@require_http_methods(["DELETE"])
@login_required
def remove_contributor(request: HttpRequest, pk: int, cid: int) -> HttpResponse:
    article = _editable_article(request, pk)
    contributor = get_object_or_404(ArticleContributor, pk=cid, article=article)
    error = ""
    try:
        services.remove_credit(request.user, article, contributor)
    except ValidationError as exc:
        error = " ".join(exc.messages)
    context = sidebar_context(request, article, credit_error=error)
    return _with_updated_at(
        render(request, "publications/partials/credits_response.html", context), article
    )


@require_POST
@login_required
def anonymize_contributor(request: HttpRequest, pk: int, cid: int) -> HttpResponse:
    """POST /x/articles/<id>/contributors/<cid>/anonymize/: só admin (docs/23, docs/18).

    Do editor (HTMX) devolve os créditos atualizados; do alerta "Alunos sem autorização" no
    painel editorial (formulário comum) volta para a página de origem com um aviso.
    """
    article = get_object_or_404(Article, pk=pk)
    contributor = get_object_or_404(ArticleContributor, pk=cid, article=article)
    if not permissions.can_anonymize(request.user):
        raise PermissionDenied
    error = ""
    try:
        services.anonymize_student_credit(request.user, contributor, request=request)
    except ValidationError as exc:
        error = " ".join(exc.messages)
    if request.headers.get("HX-Request") == "true":
        context = sidebar_context(request, article, credit_error=error)
        return _with_updated_at(
            render(request, "publications/partials/credits_response.html", context), article
        )
    if error:
        messages.error(request, error)
    else:
        messages.success(request, f"Crédito de aluno anonimizado em “{article.title}”.")
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse("publications:edit", args=[article.pk])
    return redirect(target)


@require_GET
@login_required
def search_users(request: HttpRequest) -> HttpResponse:
    """GET /x/users/search/?q=&article=<id>: colegas para creditar."""
    article = _editable_article(request, int(request.GET.get("article", "0") or 0))
    results = selectors.search_staff_for_credit(article, request.GET.get("q", ""))
    return render(
        request,
        "publications/partials/user_search_results.html",
        {"article": article, "results": results, "query": request.GET.get("q", "")},
    )


# ação → (serviço, mensagem de sucesso)
TRANSITIONS = {
    "publish": (services.publish, "Publicado! A publicação já está no ar."),
    "archive": (services.archive, "Publicação arquivada. Ela não aparece mais no site."),
    "restore": (services.restore, "Publicação restaurada como rascunho."),
    "request_review": (
        services.request_review,
        "Revisão pedida. O colega foi avisado no painel.",
    ),
    "cancel_review": (services.cancel_review, "Pedido de revisão cancelado."),
    "request_changes": (
        services.request_changes,
        "Alterações sugeridas. Os autores foram avisados.",
    ),
    "approve": (services.approve, "Revisão aprovada. Os autores publicam quando quiserem."),
    "approve_publish": (services.approve_and_publish, "Aprovado e publicado!"),
    "decline_review": (services.decline_review, "Revisão recusada. Os autores foram avisados."),
    "resume": (services.resume, "O texto voltou a ser rascunho."),
}


@require_POST
@login_required
def transition(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    """POST /x/articles/<id>/transition/<action>/ (docs/04).

    Ações: publish, archive, restore; revisão: request_review, cancel_review, request_changes,
    approve, approve_publish, decline_review, resume.
    Volta ao editor ou, com next= (ex.: "Minhas publicações"), ao endereço interno indicado.
    Quem deixa de poder editar (o revisor, depois de decidir) volta ao painel.
    """
    article = get_object_or_404(Article, pk=pk)
    if action not in TRANSITIONS:
        return HttpResponse(status=404)
    user, note = request.user, request.POST.get("note", "")
    try:
        if action == "request_review":
            reviewer = User.objects.filter(
                pk=int(request.POST.get("reviewer") or 0), is_active=True
            ).first()
            if reviewer is None:
                raise ValidationError("Escolha o colega que vai revisar.")
            services.request_review(
                user,
                article,
                reviewer,
                note=note,
                can_publish=request.POST.get("can_publish") == "on",
            )
        elif action == "archive":
            services.archive(user, article, note=note)
        elif action in ("request_changes", "approve", "approve_publish", "decline_review"):
            TRANSITIONS[action][0](user, article, note)
        else:
            TRANSITIONS[action][0](user, article)
        messages.success(request, TRANSITIONS[action][1])
    except PermissionDenied:
        raise
    except services.ChecklistError as exc:
        messages.error(request, "Ainda falta: " + " ".join(item.message for item in exc.items))
    except (ValidationError, ValueError) as exc:
        text = " ".join(exc.messages) if isinstance(exc, ValidationError) else "Dados inválidos."
        messages.error(request, text)

    article.refresh_from_db()
    fallback = (
        reverse("publications:edit", args=[article.pk])
        if permissions.can_edit(user, article)
        else reverse("dashboard:home")
    )
    edit_url = _next_url(request, fallback)
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = edit_url
        return response
    return redirect(edit_url)


@require_POST
@login_required
def duplicate(request: HttpRequest, pk: int) -> HttpResponse:
    """POST /x/articles/<id>/duplicate/: cria um rascunho igual e abre o editor (docs/15)."""
    article = get_object_or_404(Article, pk=pk)
    try:
        copy = services.duplicate_article(request.user, article)
    except media.MediaError as exc:
        messages.error(request, exc.message)
        return redirect("dashboard:my_articles")
    messages.success(request, "Cópia criada como rascunho.")
    return redirect("publications:edit", pk=copy.pk)


def _next_url(request: HttpRequest, default: str) -> str:
    """next= só vale para endereços deste site; qualquer outro volta ao padrão."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default
