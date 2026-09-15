"""Início do painel e "Minhas publicações" (docs/15). Regras em selectors e permissions."""

from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.accounts.services import ensure_profile
from apps.core.templatetags.ui import PAGE_PARAM
from apps.editorial import alerts, permissions
from apps.publications.models import Article

from . import selectors

PAGE_SIZE = 20


@never_cache
@require_GET
@login_required
def home(request: HttpRequest) -> HttpResponse:
    """/painel/: "o que preciso fazer agora?" em uma olhada."""
    user = request.user
    ensure_profile(user)
    pending, unread_total = selectors.pending_items(user)
    context = {
        "pending": pending,
        "unread_total": unread_total,
        "unread_hidden": max(unread_total - selectors.HOME_NOTIFICATIONS, 0),
        "drafts": selectors.recent_drafts(user),
        "published": selectors.recent_published(user),
        "stats": selectors.stats(user),
        # Editor+ vê quantos alertas o painel editorial tem (E33).
        "editorial_alerts": (
            alerts.alert_count(alerts.editorial_alerts())
            if permissions.can_access_editorial(user)
            else 0
        ),
    }
    return render(request, "dashboard/home.html", context)


@dataclass
class Row:
    """Uma publicação na tabela, com o que a pessoa pode fazer com ela."""

    article: Article
    my_roles: str
    can_edit: bool
    can_duplicate: bool
    can_archive: bool
    can_restore: bool

    @property
    def has_more(self) -> bool:
        return self.can_duplicate or self.can_archive or self.can_restore


def _row(user, article: Article) -> Row:
    can_edit = permissions.can_edit(user, article)
    return Row(
        article=article,
        my_roles=", ".join(c.get_role_display() for c in article.my_credits),
        can_edit=can_edit,
        can_duplicate=permissions.can_duplicate(user, article),
        # Arquivar texto alheio pede motivo: isso fica no editor, não na lista.
        can_archive=permissions.can_archive(user, article)
        and not permissions.archive_requires_note(user, article),
        can_restore=permissions.can_restore(user, article),
    )


@never_cache
@require_GET
@login_required
def my_articles(request: HttpRequest) -> HttpResponse:
    """/painel/publicacoes/: tabela com filtro por estado e ações por linha."""
    user = request.user
    current = request.GET.get("estado", "")
    if current not in selectors.STATUS_FILTERS:
        current = ""
    counts = selectors.status_counts(user)
    chips = [
        {"key": key, "label": label, "count": counts[key], "active": key == current}
        for key, (label, _) in selectors.STATUS_FILTERS.items()
    ]
    page = Paginator(selectors.my_articles(user, current), PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    context = {
        "chips": chips,
        "current": current,
        "current_label": selectors.STATUS_FILTERS[current][0],
        "page_obj": page,
        "rows": [_row(user, article) for article in page.object_list],
        "total": counts[""],
        "next_url": request.get_full_path(),
    }
    return render(request, "dashboard/my_articles.html", context)
