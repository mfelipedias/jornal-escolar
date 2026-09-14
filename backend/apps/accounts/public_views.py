"""Perfil público de um membro da equipe e a lista "Quem escreve" (docs/12, docs/13, E22)."""

import unicodedata
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.publications import presentation
from apps.publications import selectors as publication_selectors
from apps.taxonomy.models import KnowledgeArea

from . import selectors
from .models import TeacherProfile, User

PROFILE_PER_PAGE = 10

TABS = [
    (selectors.TAB_ALL, "Todas"),
    (selectors.TAB_AUTHOR, "Como autor(a)"),
    (selectors.TAB_COLLABORATIONS, "Colaborações"),
]

# Palavras que, no headline, já dizem o cargo (sem acento e em minúsculas).
KIND_WORDS: dict[str, tuple[str, ...]] = {
    User.StaffKind.TEACHER: ("professor",),
    User.StaffKind.MONITOR: ("monitor",),
    User.StaffKind.COORDINATOR: ("coordena",),
    User.StaffKind.PRINCIPAL: ("diret", "direcao"),
    User.StaffKind.LIBRARIAN: ("sala de leitura", "bibliotec"),
}


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def kind_label(user: User, headline: str) -> str:
    """Cargo como etiqueta discreta, só se o headline não o mencionar (docs/13).

    "Outro" nunca aparece: nesse caso o cargo é o próprio headline (docs/02).
    """
    words = KIND_WORDS.get(user.staff_kind)
    if not words:
        return ""
    plain = _plain(headline)
    return "" if any(w in plain for w in words) else user.get_staff_kind_display()


def education_lines(items: list) -> list[str]:
    """[{degree, institution, year}] → ["Licenciatura em Biologia, UFXX, 2012"]."""
    lines = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        parts = [str(item.get(k) or "").strip() for k in ("degree", "institution", "year")]
        line = ", ".join(p for p in parts if p)
        if line:
            lines.append(line)
    return lines


@dataclass
class ProfileLink:
    label: str
    url: str


def safe_links(items: list, limit: int = 4) -> list[ProfileLink]:
    """Só http(s): o JSON vem do admin e não pode virar javascript:."""
    links = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if urlsplit(url).scheme not in ("http", "https"):
            continue
        label = str(item.get("label") or "").strip() or urlsplit(url).netloc
        links.append(ProfileLink(label=label, url=url))
    return links[:limit]


def main_area(profile: TeacherProfile) -> KnowledgeArea | None:
    """Primeira área marcada ou a área da primeira disciplina (cor das iniciais)."""
    area = next(iter(profile.areas.all()), None)
    if area:
        return area
    discipline = next(iter(profile.disciplines.all()), None)
    return discipline.area if discipline else None


@require_GET
def teacher_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """/professores/<slug>/: página de autor, para todos os cargos (docs/13)."""
    profile = selectors.profile_for_page(slug)
    if profile is None:
        raise Http404
    person = profile.user
    is_owner = request.user.is_authenticated and request.user.pk == person.pk
    if not profile.is_public and not is_owner:
        raise Http404

    counts = selectors.profile_tab_counts(profile)
    # Conta desativada: só o crédito histórico continua no ar, sem bio nem contatos.
    if not person.is_active and not counts[selectors.TAB_ALL]:
        raise Http404

    tab = request.GET.get("aba", selectors.TAB_ALL)
    if tab not in selectors.TAB_ROLES:
        tab = selectors.TAB_ALL
    articles = publication_selectors.for_cards(selectors.profile_articles(profile, tab))
    page_obj = Paginator(articles, PROFILE_PER_PAGE).get_page(request.GET.get("pagina"))
    cards = [presentation.card(a) for a in page_obj]
    context = {"page_obj": page_obj, "cards": cards}
    if request.headers.get("HX-Request") == "true" and "pagina" in request.GET:
        return render(request, "accounts/partials/profile_more.html", context)

    area = main_area(profile)
    context.update(
        {
            "profile": profile,
            "person": person,
            "name": person.public_name,
            "initials": presentation.initials(person.public_name),
            "avatar_url": person.avatar.variant_url("w480") if person.avatar_id else "",
            "area": area,
            "kind_label": kind_label(person, profile.headline),
            "show_details": person.is_active,
            "education": education_lines(profile.education),
            "links": safe_links(profile.links),
            "is_owner": is_owner,
            "can_edit": request.user.is_authenticated and request.user.is_staff,
            "tab": tab,
            "tabs": [
                {
                    "key": key,
                    "label": label,
                    "count": counts[key],
                    "url": "?" + urlencode({"aba": key}) if key != selectors.TAB_ALL else "?",
                }
                for key, label in TABS
            ],
            "total": counts[selectors.TAB_ALL],
        }
    )
    response = render(request, "accounts/teacher_detail.html", context)
    if not profile.is_public:
        response["X-Robots-Tag"] = "noindex"
        response["Cache-Control"] = "private, no-store"
    return response


@dataclass
class TeamCard:
    """Card de "Quem escreve": o Credit do membro mais cargo, disciplinas e publicações."""

    person: presentation.Credit
    kind: str
    headline: str
    disciplines: list
    published_count: int


@dataclass
class FilterChip:
    label: str
    url: str
    selected: bool


def _chip_url(query: dict[str, str], **changes: str) -> str:
    merged = {**query, **changes}
    encoded = urlencode({k: v for k, v in merged.items() if v})
    return f"?{encoded}" if encoded else "?"


@require_GET
def teacher_list(request: HttpRequest) -> HttpResponse:
    """/professores/: toda a equipe com perfil público, com filtros por área e cargo (docs/12)."""
    area = None
    if slug := request.GET.get("area"):
        area = KnowledgeArea.objects.filter(is_active=True, slug=slug).first()
    kind = request.GET.get("cargo", "")
    if kind not in selectors.KIND_GROUPS:
        kind = ""
    alphabetical = request.GET.get("ordem") == "nome"
    query = {
        "area": area.slug if area else "",
        "cargo": kind,
        "ordem": "nome" if alphabetical else "",
    }

    people = selectors.team(area=area, kind=kind, alphabetical=alphabetical)
    cards = []
    for user in people:
        headline = user.profile.headline
        cards.append(
            TeamCard(
                person=presentation.writer(user),
                kind=user.get_staff_kind_display() if kind_label(user, headline) else "",
                headline=headline,
                disciplines=list(user.profile.disciplines.all())[:4],
                published_count=user.published_count,
            )
        )

    area_chips = [FilterChip("Todas", _chip_url(query, area=""), area is None)] + [
        FilterChip(a.nav_name, _chip_url(query, area=a.slug), area == a)
        for a in KnowledgeArea.objects.filter(is_active=True)
    ]
    kind_chips = [FilterChip("Toda a equipe", _chip_url(query, cargo=""), not kind)] + [
        FilterChip(label, _chip_url(query, cargo=key), kind == key)
        for key, (label, _) in selectors.KIND_GROUPS.items()
    ]
    context = {
        "cards": cards,
        "area": area,
        "area_chips": area_chips,
        "kind_chips": kind_chips,
        "alphabetical": alphabetical,
        "order_recent_url": _chip_url(query, ordem=""),
        "order_name_url": _chip_url(query, ordem="nome"),
        "has_filters": bool(area or kind),
    }
    return render(request, "accounts/teacher_list.html", context)
