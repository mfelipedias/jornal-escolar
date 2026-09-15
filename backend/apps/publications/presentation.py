"""Montagem dos textos exibidos nas páginas públicas (byline, créditos, área principal, cards)."""

from dataclasses import dataclass, field
from datetime import datetime

from apps.taxonomy.models import KnowledgeArea

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
    url: str = ""  # perfil público, quando existe e está visível

    @property
    def initials(self) -> str:
        return initials(self.name)


def initials(name: str) -> str:
    """ "Carla Souza" → "CS"; "Ana" → "A". Usado quando não há foto."""
    words = [w for w in name.split() if w[:1].isalpha()]
    if not words:
        return name[:1].upper()
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def profile_url(user) -> str:
    """Endereço do perfil público, ou vazio se o perfil estiver oculto."""
    profile = getattr(user, "profile", None)
    return profile.get_absolute_url() if profile and profile.is_public else ""


def join_names(names: list[str]) -> str:
    """["Ana"] → "Ana"; ["Ana", "Rafael S."] → "Ana e Rafael S."; três ou mais com vírgulas."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} e {names[-1]}"


def _detail(contributor: ArticleContributor) -> str:
    if contributor.is_student:
        return f"Aluno, {contributor.class_group}" if contributor.class_group else "Aluno"
    if contributor.user_id:
        if contributor.user.is_anonymized:
            return ""
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
        url=profile_url(contributor.user) if contributor.user_id else "",
    )


def byline_people(article: Article) -> list[Credit]:
    """Autores e coautores na ordem dos créditos (avatares e nomes do componente byline)."""
    return [
        _credit(c)
        for c in article.contributors.all()
        if c.role in ArticleContributor.EDITING_ROLES and c.show_in_credits
    ]


def byline(article: Article) -> str:
    """ "Carla Souza e Rafael S." com autores e coautores na ordem dos créditos."""
    return join_names([person.name for person in byline_people(article)])


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


def main_area(article: Article) -> KnowledgeArea | None:
    """Área da primeira disciplina (etiqueta colorida no topo)."""
    first = next(iter(article.disciplines.all()), None)
    return first.area if first else None


@dataclass
class EventItem:
    """Item de agenda (home e /agenda/)."""

    title: str
    url: str
    event_at: datetime
    location: str = ""
    area: KnowledgeArea | None = None


def event(article: Article) -> EventItem:
    return EventItem(
        title=article.title,
        url=article.get_absolute_url(),
        event_at=article.event_at,
        location=article.event_location,
        area=main_area(article),
    )


def writer(user) -> Credit:
    """Membro da equipe em "Quem escreve": nome, apresentação curta ou cargo, foto."""
    profile = getattr(user, "profile", None)
    return Credit(
        name=user.public_name,
        detail=(profile.headline if profile else "") or user.get_staff_kind_display(),
        is_staff=True,
        avatar_url=user.avatar.variant_url("w480") if user.avatar_id else "",
        url=profile_url(user),
    )


@dataclass
class CardImage:
    """Imagem do card. É decorativa: o título ao lado já diz do que se trata."""

    src: str
    srcset: str = ""
    width: int | None = None
    height: int | None = None


@dataclass
class ArticleCard:
    """Tudo que o componente card precisa, sem consultas no template (docs/09).

    Listas montam com card(article); a página /dev/components/ monta à mão.
    """

    title: str
    url: str
    subtitle: str = ""
    area: KnowledgeArea | None = None
    type_name: str = ""
    people: list[Credit] = field(default_factory=list)
    published_at: datetime | None = None
    reading_minutes: int = 0
    image: CardImage | None = None

    @property
    def byline(self) -> str:
        return join_names([person.name for person in self.people])


def card(article: Article) -> ArticleCard:
    """Card de uma publicação. Use com selectors que já trazem capa, disciplinas e créditos."""
    image = None
    if article.cover_id:
        cover = article.cover
        image = CardImage(
            src=cover.variant_urls.get("w960") or cover.url,
            srcset=cover.srcset,
            width=cover.width,
            height=cover.height,
        )
    return ArticleCard(
        title=article.title,
        url=article.get_absolute_url(),
        subtitle=article.subtitle,
        area=main_area(article),
        type_name=article.type.name if article.type_id else "",
        people=byline_people(article),
        published_at=article.published_at,
        reading_minutes=article.reading_minutes,
        image=image,
    )
