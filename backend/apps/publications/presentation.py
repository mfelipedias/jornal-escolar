"""Montagem dos textos exibidos nas páginas públicas (byline, créditos, área principal)."""

from dataclasses import dataclass

from .models import Article, ArticleContributor

ROLE_HEADINGS = {
    ArticleContributor.Role.COLLABORATOR: "Com colaboração de",
    ArticleContributor.Role.REVIEWER: "Revisão",
    ArticleContributor.Role.EDITOR: "Edição",
}


@dataclass
class Credit:
    name: str
    detail: str
    is_staff: bool
    avatar_url: str = ""


def join_names(names: list[str]) -> str:
    """["Ana"] → "Ana"; ["Ana", "Rafael S."] → "Ana e Rafael S."; três ou mais com vírgulas."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} e {names[-1]}"


def _detail(contributor: ArticleContributor) -> str:
    if contributor.is_student:
        return f"Aluno, {contributor.class_group}" if contributor.class_group else "Aluno"
    if contributor.user_id:
        profile = getattr(contributor.user, "profile", None)
        headline = profile.headline if profile else ""
        return headline or contributor.user.get_staff_kind_display()
    return contributor.contribution_note


def _credit(contributor: ArticleContributor) -> Credit:
    avatar = ""
    if contributor.user_id and contributor.user.avatar_id:
        avatar = contributor.user.avatar.variant_url("w480")
    return Credit(
        name=contributor.display_name,
        detail=_detail(contributor),
        is_staff=bool(contributor.user_id),
        avatar_url=avatar,
    )


def byline(article: Article) -> str:
    """ "Carla Souza e Rafael S." com autores e coautores na ordem dos créditos."""
    names = [
        c.display_name
        for c in article.contributors.all()
        if c.role in ArticleContributor.EDITING_ROLES and c.show_in_credits
    ]
    return join_names(names)


def credit_groups(article: Article) -> list[tuple[str, list[Credit]]]:
    """Quem fez: autores e coautores primeiro; depois colaboração, revisão e edição."""
    contributors = [c for c in article.contributors.all() if c.show_in_credits]
    groups: list[tuple[str, list[Credit]]] = []
    main = [_credit(c) for c in contributors if c.role in ArticleContributor.EDITING_ROLES]
    if main:
        groups.append(("Texto", main))
    for role, heading in ROLE_HEADINGS.items():
        items = [_credit(c) for c in contributors if c.role == role]
        if items:
            groups.append((heading, items))
    return groups


def main_area(article: Article):
    """Área da primeira disciplina (etiqueta colorida no topo)."""
    first = next(iter(article.disciplines.all()), None)
    return first.area if first else None
