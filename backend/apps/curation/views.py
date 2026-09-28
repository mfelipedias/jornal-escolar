"""Tela de sugestões de pauta no painel (E48; docs/15 "Sugestões e Pautas", docs/21).

- GET /painel/sugestoes/: abas Para você, Salvas e Ignoradas; filtros por tópico, fonte e
  idioma (GET, funcionam sem JavaScript).
- POST /x/sugestoes/<id>/<acao>/: ignorar, salvar, interessante, restaurar. Com HTMX devolve o
  card atualizado; sem JavaScript volta para a tela com uma mensagem.

Pautas (E49; docs/15, docs/21 "Da sugestão à publicação"):
- POST /x/sugestoes/<id>/virar-pauta/: cria a pauta atribuída a quem clicou.
- GET /painel/pautas/: quadro Abertas, Atribuídas, Em produção, Concluídas (?minhas=1 filtra);
  POST /painel/pautas/nova/ cria uma pauta à mão.
- GET e POST /painel/pautas/<id>/editar/.
- POST /x/pautas/<id>/<acao>/: pegar, devolver, rascunho (abre o editor), excluir.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.templatetags.ui import PAGE_PARAM
from apps.editorial import permissions

from . import ideas, recommend, selectors
from .forms import StoryIdeaForm
from .models import NewsRecommendation, StoryIdea

PAGE_SIZE = 20


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _back(request: HttpRequest) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("curation:suggestions")


@never_cache
@require_GET
@login_required
def suggestions(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not permissions.can_view_suggestions(user):
        raise PermissionDenied
    current = request.GET.get("aba", "")
    if current not in selectors.TABS:
        current = selectors.DEFAULT_TAB
    filters = selectors.parse_filters(request.GET)
    counts = selectors.tab_counts(user, filters)
    page = Paginator(selectors.recommendations(user, current, filters), PAGE_SIZE).get_page(
        request.GET.get(PAGE_PARAM)
    )
    query = filters.query()
    base = reverse("curation:suggestions")
    profile = getattr(user, "profile", None)
    context = {
        "tabs": [
            {
                "key": key,
                "label": label,
                "count": counts[key],
                "active": key == current,
                "url": f"{base}?aba={key}{'&' + query if query else ''}",
            }
            for key, (label, _) in selectors.TABS.items()
        ],
        "current": current,
        "filters": filters,
        "options": selectors.filter_options(user),
        "languages": selectors.LANGUAGES,
        "page_obj": page,
        "cards": selectors.cards(user, list(page.object_list)),
        "next_url": request.get_full_path(),
        "has_interests": bool(
            profile and (profile.topics.exists() or profile.disciplines.exists())
        ),
    }
    return render(request, "curation/suggestions.html", context)


@require_POST
@login_required
def suggestion_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    if action not in recommend.ACTIONS:
        raise Http404
    user = request.user
    if not permissions.can_view_suggestions(user):
        raise PermissionDenied
    rec = get_object_or_404(
        NewsRecommendation.objects.select_related("item__source"), pk=pk, user=user
    )
    try:
        done = recommend.act(user, rec, action)
        error = ""
    except ValueError as exc:
        done, error = "", str(exc)
    if not _is_htmx(request):
        if error:
            messages.error(request, error)
        else:
            messages.success(request, done)
        return redirect(_back(request))
    context = {
        "card": selectors.cards(user, [rec])[0],
        "done": done,
        "error": error,
        "next_url": _back(request),
    }
    return render(request, "curation/partials/suggestion_card.html", context)


@require_POST
@login_required
def suggestion_to_idea(request: HttpRequest, pk: int) -> HttpResponse:
    user = request.user
    if not permissions.can_create_story_idea(user):
        raise PermissionDenied
    rec = get_object_or_404(
        NewsRecommendation.objects.select_related("item__source"), pk=pk, user=user
    )
    idea = ideas.idea_from_recommendation(user, rec)
    rec.refresh_from_db()
    if not _is_htmx(request):
        messages.success(request, f"Pauta criada: “{idea.title}”.")
        return redirect("curation:story_ideas")
    context = {
        "card": selectors.cards(user, [rec])[0],
        "done": "Virou pauta. Está no quadro de pautas, com você.",
        "error": "",
        "next_url": _back(request),
    }
    return render(request, "curation/partials/suggestion_card.html", context)


# --- pautas ---


def _board_context(request: HttpRequest, form: StoryIdeaForm | None = None) -> dict:
    only_mine = request.GET.get("minhas") == "1"
    return {
        "columns": selectors.board(request.user, only_mine),
        "only_mine": only_mine,
        "form": form or StoryIdeaForm(),
        "form_open": form is not None,
    }


@never_cache
@require_GET
@login_required
def story_ideas(request: HttpRequest) -> HttpResponse:
    if not permissions.can_create_story_idea(request.user):
        raise PermissionDenied
    return render(request, "curation/story_ideas.html", _board_context(request))


@require_POST
@login_required
def story_idea_create(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not permissions.can_create_story_idea(user):
        raise PermissionDenied
    form = StoryIdeaForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        idea = ideas.create_idea(
            user,
            title=data["title"],
            notes=data["notes"],
            topics=data["topics"],
            disciplines=data["disciplines"],
            keep=data["keep"],
        )
        messages.success(request, f"Pauta criada: “{idea.title}”.")
        return redirect("curation:story_ideas")
    context = _board_context(request, form)
    return render(request, "curation/story_ideas.html", context, status=400)


@never_cache
@login_required
def story_idea_edit(request: HttpRequest, pk: int) -> HttpResponse:
    user = request.user
    idea = get_object_or_404(StoryIdea.objects.select_related("item__source"), pk=pk)
    if not permissions.can_edit_story_idea(user, idea):
        raise PermissionDenied
    can_assign = permissions.can_assign_story_idea(user, idea)
    initial = {
        "title": idea.title,
        "notes": idea.notes,
        "topics": list(idea.topics.all()),
        "disciplines": list(idea.disciplines.all()),
        "assigned_to": idea.assigned_to,
    }
    if request.method == "POST":
        form = StoryIdeaForm(request.POST, creating=False, can_assign=can_assign)
        if form.is_valid():
            data = form.cleaned_data
            extra = {"assigned_to": data["assigned_to"]} if can_assign else {}
            try:
                ideas.update_idea(
                    user,
                    idea,
                    title=data["title"],
                    notes=data["notes"],
                    topics=data["topics"],
                    disciplines=data["disciplines"],
                    **extra,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Pauta atualizada.")
                return redirect("curation:story_ideas")
        status = 400
    else:
        form = StoryIdeaForm(initial=initial, creating=False, can_assign=can_assign)
        status = 200
    context = {"idea": idea, "form": form}
    return render(request, "curation/story_idea_edit.html", context, status=status)


IDEA_ACTIONS = {
    "pegar": (ideas.take, "A pauta agora está com você."),
    "devolver": (ideas.release, "A pauta voltou para as abertas."),
    "excluir": (ideas.delete, "Pauta excluída."),
}


@require_POST
@login_required
def story_idea_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    user = request.user
    idea = get_object_or_404(StoryIdea, pk=pk)
    if action == "rascunho":
        article = ideas.start_draft(user, idea)
        messages.success(request, "Rascunho criado com a fonte da pauta. Bom texto!")
        return redirect("publications:edit", article.pk)
    if action not in IDEA_ACTIONS:
        raise Http404
    service, message = IDEA_ACTIONS[action]
    service(user, idea)
    messages.success(request, message)
    return redirect(_board_back(request))


def _board_back(request: HttpRequest) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("curation:story_ideas")
