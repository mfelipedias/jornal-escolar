"""Dados prontos para o template da barra de reações (engagement/partials/reaction_bar.html)."""

from dataclasses import dataclass

from .models import EMOJIS, Reaction


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
