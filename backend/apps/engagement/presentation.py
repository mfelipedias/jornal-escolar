"""Dados prontos para os templates: barra de reações (engagement/partials/reaction_bar.html),
contagem de leituras e bloco de comentários (engagement/partials/comments.html) da página da
publicação."""

from dataclasses import dataclass
from datetime import datetime

from apps.core.site_settings import get_setting
from apps.editorial import permissions
from apps.publications.models import Article, ArticleContributor

from . import services
from .forms import CommentForm
from .models import EMOJIS, Comment, Reaction

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


# --- comentários públicos ---


@dataclass(frozen=True)
class CommentItem:
    pk: int
    author_name: str
    body: str
    created_at: datetime
    reply_body: str
    reply_author: str
    replied_at: datetime | None


@dataclass
class CommentsSection:
    """Bloco "Comentários" da página (engagement/partials/comments.html)."""

    article_id: int
    items: list[CommentItem]
    is_open: bool
    can_reply: bool
    form: CommentForm | None = None
    notice: str = ""
    sent: bool = False

    @property
    def count(self) -> int:
        return len(self.items)


def reply_author(comment: Comment, article: Article) -> str:
    """Quem respondeu, como aparece: "Carla Souza (autoria do texto)" ou "(edição do jornal)".

    Sem gênero no cadastro, o papel vai no substantivo e não em "autora"/"autor". Conta
    apagada ou anonimizada vira "equipe do jornal". Usa os créditos já carregados da página.
    """
    user = comment.replied_by
    if user is None or user.is_anonymized:
        return "equipe do jornal"
    credited = any(
        credit.user_id == user.pk and credit.role in ArticleContributor.EDITING_ROLES
        for credit in article.contributors.all()
    )
    return f"{user.public_name} ({'autoria do texto' if credited else 'edição do jornal'})"


def comment_item(comment: Comment, article: Article) -> CommentItem:
    return CommentItem(
        pk=comment.pk,
        author_name=comment.author_name,
        body=comment.body,
        created_at=comment.created_at,
        reply_body=comment.reply_body,
        reply_author=reply_author(comment, article) if comment.reply_body else "",
        replied_at=comment.replied_at,
    )


def comments_section(
    article: Article,
    user,
    *,
    form: CommentForm | None = None,
    notice: str = "",
    sent: bool = False,
) -> CommentsSection | None:
    """Comentários aprovados e o formulário. None quando o bloco não deve aparecer: comentários
    desligados no site, ou fechados nesta publicação e sem nenhum aprovado."""
    if not get_setting("comments.enabled") or article.status != Article.Status.PUBLISHED:
        return None
    items = [comment_item(c, article) for c in services.approved_comments(article)]
    is_open = permissions.can_comment(user, article)
    if not items and not is_open:
        return None
    if form is None and is_open:
        initial = {"author_name": user.public_name} if user.is_authenticated else {}
        form = CommentForm(initial=initial)
    return CommentsSection(
        article_id=article.pk,
        items=items,
        is_open=is_open,
        can_reply=permissions.can_reply_comment(user, article),
        form=form,
        notice=notice,
        sent=sent,
    )
