"""Dados prontos para os templates: barra de reações (engagement/partials/reaction_bar.html) e
contagem de leituras da página da publicação."""

from dataclasses import dataclass

from apps.publications.models import ArticleContributor

from .models import EMOJIS, Reaction

# "143 leituras" só aparece a partir deste total (docs/20, docs/11).
MIN_READS_TO_SHOW = 10


@dataclass(frozen=True)
class ReactionButton:
    kind: str
    label: str
    emoji: str
    count: int
    pressed: bool


@dataclass(frozen=True)
class ReactionBar:
    article_id: int
    buttons: list[ReactionButton]
    notice: str = ""


def reaction_bar(article, current: str | None, *, notice: str = "") -> ReactionBar:
    counts = article.reactions_count or {}
    buttons = [
        ReactionButton(
            kind=kind.value,
            label=kind.label,
            emoji=EMOJIS[kind],
            count=int(counts.get(kind.value, 0)),
            pressed=current == kind.value,
        )
        for kind in Reaction.Kind
    ]
    return ReactionBar(article_id=article.pk, buttons=buttons, notice=notice)


def show_reads(article) -> bool:
    """Mostrar "N leituras" na página: total mínimo e nenhum autor ou coautor desligou.

    Usa os créditos já carregados pela página (selectors.article_for_page, com user__profile).
    """
    if (article.reads_count or 0) < MIN_READS_TO_SHOW:
        return False
    for credit in article.contributors.all():
        if credit.role not in ArticleContributor.EDITING_ROLES or credit.user is None:
            continue
        profile = getattr(credit.user, "profile", None)
        if profile is not None and not profile.show_reads:
            return False
    return True
