"""Consultas do perfil público e de "Quem escreve" (docs/12, docs/13)."""

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.publications import selectors as publication_selectors
from apps.publications.models import Article, ArticleContributor
from apps.taxonomy.models import Discipline, KnowledgeArea, Topic

from .models import TeacherProfile, User

Role = ArticleContributor.Role

# Abas do perfil: parâmetro ?aba= → papéis nos créditos (docs/13).
TAB_ALL = "todas"
TAB_AUTHOR = "autor"
TAB_COLLABORATIONS = "colaboracoes"
TAB_ROLES: dict[str, tuple[str, ...]] = {
    TAB_ALL: tuple(Role.values),
    TAB_AUTHOR: (Role.AUTHOR, Role.COAUTHOR),
    TAB_COLLABORATIONS: (Role.COLLABORATOR, Role.REVIEWER, Role.EDITOR),
}

# Filtro por cargo em "Quem escreve": ?cargo= → staff_kind (docs/12).
KIND_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "professores": ("Professores", (User.StaffKind.TEACHER,)),
    "monitores": ("Monitores", (User.StaffKind.MONITOR,)),
    "coordenacao": (
        "Coordenação e direção",
        (User.StaffKind.COORDINATOR, User.StaffKind.PRINCIPAL),
    ),
    "outros": ("Outros", (User.StaffKind.LIBRARIAN, User.StaffKind.OTHER)),
}


def profile_for_page(slug: str) -> TeacherProfile | None:
    return (
        TeacherProfile.objects.select_related("user", "user__avatar")
        .prefetch_related(
            Prefetch("areas", queryset=KnowledgeArea.objects.filter(is_active=True)),
            Prefetch(
                "disciplines",
                queryset=Discipline.objects.filter(
                    is_active=True, area__is_active=True
                ).select_related("area"),
            ),
            Prefetch("topics", queryset=Topic.objects.filter(is_active=True)),
        )
        .filter(slug=slug)
        .first()
    )


def _visible_credits(profile: TeacherProfile, roles: tuple[str, ...]) -> QuerySet:
    """Créditos que aparecem na publicação, sem revisão se a pessoa pediu para ocultar."""
    credits = ArticleContributor.objects.filter(
        user_id=profile.user_id, show_in_credits=True, role__in=roles
    )
    if not profile.show_reviewer_credit:
        credits = credits.exclude(role=Role.REVIEWER)
    return credits


def profile_articles(profile: TeacherProfile, tab: str) -> QuerySet[Article]:
    """Publicadas em que a pessoa aparece nos créditos, filtradas pela aba."""
    roles = TAB_ROLES.get(tab, TAB_ROLES[TAB_ALL])
    article_ids = _visible_credits(profile, roles).values("article_id")
    return publication_selectors.published().filter(pk__in=article_ids)


def credited_profiles() -> list[TeacherProfile]:
    """Perfis públicos de contas ativas com crédito visível em alguma publicação no ar.

    São as opções do filtro "Quem escreveu" das listas (docs/19), em ordem alfabética.
    """
    not_reviewer = [role for role in Role.values if role != Role.REVIEWER]
    # Tudo num filter() só: as condições valem para o mesmo crédito.
    visible = Q(
        user__contributions__show_in_credits=True,
        user__contributions__article__status=Article.Status.PUBLISHED,
    ) & (Q(user__contributions__role__in=not_reviewer) | Q(show_reviewer_credit=True))
    profiles = (
        TeacherProfile.objects.filter(visible, is_public=True, user__is_active=True)
        .select_related("user")
        .distinct()
    )
    return sorted(profiles, key=lambda p: p.user.public_name.lower())


def profile_tab_counts(profile: TeacherProfile) -> dict[str, int]:
    return {tab: profile_articles(profile, tab).count() for tab in TAB_ROLES}


def team(*, area: KnowledgeArea | None = None, kind: str = "", alphabetical: bool = False):
    """Quem escreve: equipe ativa com perfil público, com disciplinas e número de publicações."""
    queryset = User.objects.all()
    if area is not None:
        queryset = queryset.filter(pk__in=publication_selectors.writer_ids_about(area))
    if kind in KIND_GROUPS:
        queryset = queryset.filter(staff_kind__in=KIND_GROUPS[kind][1])
    published_credit = Q(
        contributions__article__status=Article.Status.PUBLISHED,
        contributions__show_in_credits=True,
    ) & (~Q(contributions__role=Role.REVIEWER) | Q(profile__show_reviewer_credit=True))
    people = (
        publication_selectors.writers(limit=None, queryset=queryset)
        .annotate(
            published_count=Count("contributions__article", filter=published_credit, distinct=True)
        )
        .prefetch_related(
            Prefetch(
                "profile__disciplines",
                queryset=Discipline.objects.filter(is_active=True, area__is_active=True),
            )
        )
    )
    if alphabetical:
        people = people.order_by("full_name")
    return people


# --- Configuração de perfil (E23, docs/14) ---


def missing_profile_items(user: User) -> list[str]:
    """O que falta para o aviso "Complete seu perfil": foto, disciplinas ou áreas, bio."""
    profile = user.profile
    missing = []
    if not user.avatar_id:
        missing.append("foto")
    if user.staff_kind == User.StaffKind.TEACHER:
        if not profile.disciplines.exists():
            missing.append("disciplinas")
    elif not profile.areas.exists():
        missing.append("áreas de atuação")
    if not profile.bio.strip():
        missing.append("sobre mim")
    return missing


def areas_with_disciplines() -> QuerySet[KnowledgeArea]:
    return KnowledgeArea.objects.filter(is_active=True).prefetch_related(
        Prefetch("disciplines", queryset=Discipline.objects.filter(is_active=True))
    )


def topics_for_profile(discipline_ids) -> list[Topic]:
    """Tópicos ativos, primeiro os ligados às disciplinas escolhidas (docs/14, passo 3)."""
    ids = list(discipline_ids)
    linked = set(
        Topic.objects.filter(is_active=True, disciplines__in=ids).values_list("pk", flat=True)
    )
    topics = list(Topic.objects.filter(is_active=True))
    return sorted(topics, key=lambda t: (t.pk not in linked, t.name.lower()))
