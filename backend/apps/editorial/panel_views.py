"""Painel editorial (docs/18, E33): visão geral com alertas, todas as publicações e ações em
massa. Só editor e admin (permissions.can_access_editorial). Contas novas do cadastro próprio
(Fase 4b, C2): aprovar ou recusar."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts import approval
from apps.accounts.models import User
from apps.core import audit
from apps.core.templatetags.ui import PAGE_PARAM
from apps.publications import presentation, services
from apps.publications.models import Article, ArticleContributor
from apps.taxonomy.models import ArticleType, KnowledgeArea

from . import alerts, permissions, selectors

PAGE_SIZE = 25
BULK_LIMIT = 100

# ?acao= das ações em massa → (resultado no singular, no plural).
BULK_ACTIONS = {
    "arquivar": ("publicação arquivada", "publicações arquivadas"),
    "trocar-revisor": ("publicação com revisor trocado", "publicações com revisor trocado"),
}


def _require_editorial(request: HttpRequest) -> None:
    if not permissions.can_access_editorial(request.user):
        raise PermissionDenied


@never_cache
@require_GET
@login_required
def overview(request: HttpRequest) -> HttpResponse:
    """/painel/editorial/: contadores por estado, rascunhos por autor e alertas."""
    _require_editorial(request)
    groups = alerts.editorial_alerts()
    context = {
        "section": "overview",
        "counts": selectors.editorial_counts(),
        "published_label": f"Publicadas nos últimos {selectors.RECENT_PUBLISHED_DAYS} dias",
        "draft_authors": selectors.draft_authors(),
        "alert_groups": groups,
        "alert_total": alerts.alert_count(groups),
        "can_anonymize": permissions.can_anonymize(request.user),
        "pending_accounts": approval.pending_count(),
    }
    return render(request, "editorial/overview.html", context)


@never_cache
@require_GET
@login_required
def articles(request: HttpRequest) -> HttpResponse:
    """/painel/editorial/publicacoes/: tabela com filtros; clicar leva à tela de revisão."""
    _require_editorial(request)
    filters = selectors.parse_article_filters(request.GET)
    page = Paginator(selectors.all_articles(filters), PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    authors, reviewers = selectors.filter_people()
    rows = [
        {
            "article": article,
            "authors": presentation.byline(article),
            "reviewer": next(
                (
                    c
                    for c in article.contributors.all()
                    if c.role == ArticleContributor.Role.REVIEWER
                ),
                None,
            ),
        }
        for article in page.object_list
    ]
    context = {
        "section": "articles",
        "filters": filters,
        "page_obj": page,
        "rows": rows,
        "statuses": [
            (key, Article.Status(value).label) for key, value in selectors.EDITORIAL_STATUS.items()
        ],
        "periods": [(key, label) for key, (label, _) in selectors.PERIODS.items()],
        "types": ArticleType.objects.order_by("order", "name"),
        "areas": KnowledgeArea.objects.order_by("order", "name"),
        "authors": authors,
        "reviewers": reviewers,
        "reviewer_options": User.objects.filter(is_active=True).order_by("full_name"),
        "next_url": request.get_full_path(),
    }
    return render(request, "editorial/articles.html", context)


def _back(request: HttpRequest) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("editorial:articles")


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    return "sem permissão."


@require_POST
@login_required
def bulk_action(request: HttpRequest) -> HttpResponse:
    """POST /painel/editorial/publicacoes/acoes/: arquivar ou trocar o revisor das marcadas.

    Cada publicação passa pelo serviço normal (permissão, evento, avisos). As que não puderem
    são listadas no aviso de erro; as outras seguem.
    """
    _require_editorial(request)
    back = _back(request)
    action = request.POST.get("acao", "")
    ids = list(dict.fromkeys(int(v) for v in request.POST.getlist("ids") if v.isdigit()))
    note = request.POST.get("note", "").strip()
    if action not in BULK_ACTIONS:
        messages.error(request, "Escolha uma ação.")
        return redirect(back)
    if not ids:
        messages.error(request, "Marque ao menos uma publicação.")
        return redirect(back)
    if len(ids) > BULK_LIMIT:
        messages.error(request, f"Marque no máximo {BULK_LIMIT} publicações por vez.")
        return redirect(back)
    reviewer = None
    if action == "arquivar" and not note:
        messages.error(request, "Explique o motivo do arquivamento: ele vai no aviso aos autores.")
        return redirect(back)
    if action == "trocar-revisor":
        reviewer_id = request.POST.get("reviewer", "")
        reviewer = User.objects.filter(
            pk=int(reviewer_id) if reviewer_id.isdigit() else 0, is_active=True
        ).first()
        if reviewer is None:
            messages.error(request, "Escolha o colega que vai revisar.")
            return redirect(back)

    done, failed, done_ids = 0, [], []
    for article in Article.objects.filter(pk__in=ids).order_by("pk"):
        try:
            if action == "arquivar":
                if article.status == Article.Status.ARCHIVED:
                    raise ValidationError("já está arquivada.")
                services.archive(request.user, article, note=note)
            else:
                if article.status != Article.Status.IN_REVIEW:
                    raise ValidationError("não está em revisão.")
                services.reassign_reviewer(request.user, article, reviewer, note=note)
            done += 1
            done_ids.append(article.pk)
        except (PermissionDenied, ValidationError) as exc:
            failed.append(f"“{article.title}”: {_error_text(exc)}")
    if done:
        changes = {"articles": done_ids}
        if reviewer is not None:
            changes["reviewer"] = reviewer.pk
        audit.record(
            audit.Action.ARTICLES_ARCHIVED
            if action == "arquivar"
            else audit.Action.REVIEWER_REASSIGNED,
            actor=request.user,
            changes=changes,
            request=request,
        )
        one, many = BULK_ACTIONS[action]
        messages.success(request, f"{done} {one if done == 1 else many}.")
    if failed:
        messages.error(request, "Não foi possível em " + " ".join(failed))
    return redirect(back)


# --- contas novas (Fase 4b, C2) ---

ACCOUNT_ACTIONS = {
    "aprovar": (approval.approve, "Conta de {name} aprovada. A pessoa foi avisada."),
    "recusar": (approval.reject, "Cadastro de {name} recusado e apagado."),
}


@never_cache
@require_GET
@login_required
def accounts(request: HttpRequest) -> HttpResponse:
    """/painel/editorial/contas/: cadastros próprios aguardando aprovação."""
    if not permissions.can_approve_accounts(request.user):
        raise PermissionDenied
    context = {"section": "accounts", "people": approval.pending_accounts()}
    return render(request, "editorial/accounts.html", context)


@require_POST
@login_required
def account_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    if action not in ACCOUNT_ACTIONS:
        raise PermissionDenied
    person = User.objects.filter(pk=pk).first()
    if person is None:
        messages.info(request, "Esta conta já foi decidida por outra pessoa.")
        return redirect("editorial:accounts")
    service, message = ACCOUNT_ACTIONS[action]
    name = person.public_name
    try:
        service(request.user, person, request)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, message.format(name=name))
    return redirect("editorial:accounts")
