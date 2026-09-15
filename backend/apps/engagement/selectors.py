"""Consultas da moderação de comentários públicos (docs/20, "Moderação no painel"; docs/15).

Quem vê o quê: editor e admin veem os comentários de todas as publicações; o restante da
equipe, só os das publicações em que é autor ou coautor (permissions.can_moderate_comments).
"""

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications.models import Article, ArticleContributor

from .models import Comment

Status = Comment.Status

# Abas da fila: ?aba= → (rótulo, situação).
TABS: dict[str, tuple[str, str]] = {
    "pendentes": ("Pendentes", Status.PENDING),
    "aprovados": ("Aprovados", Status.APPROVED),
    "rejeitados": ("Rejeitados", Status.REJECTED),
}
DEFAULT_TAB = "pendentes"


def sees_all(user: User) -> bool:
    """Editores veem "Todos os pendentes" do jornal."""
    return permissions.is_editor(user)


def moderated_articles(user: User) -> QuerySet[Article]:
    """Publicações cujos comentários a pessoa modera."""
    if sees_all(user):
        return Article.objects.all()
    if not permissions.is_staff_member(user):
        return Article.objects.none()
    ids = ArticleContributor.objects.filter(
        user=user, role__in=ArticleContributor.EDITING_ROLES
    ).values("article_id")
    return Article.objects.filter(pk__in=ids)


def moderation_comments(user: User, article_id: int | None = None) -> QuerySet[Comment]:
    """Todos os comentários que a pessoa modera, opcionalmente de uma publicação só."""
    comments = Comment.objects.filter(article__in=moderated_articles(user).values("pk"))
    if article_id is not None:
        comments = comments.filter(article_id=article_id)
    return comments


def moderation_queue(
    user: User, tab: str = DEFAULT_TAB, article_id: int | None = None
) -> QuerySet[Comment]:
    """Uma aba da fila. Pendentes do mais antigo para o mais recente (quem espera há mais
    tempo primeiro); aprovados e rejeitados do mais recente para o mais antigo."""
    status = TABS.get(tab, TABS[DEFAULT_TAB])[1]
    comments = moderation_comments(user, article_id).filter(status=status)
    if status == Status.PENDING:
        order = ("created_at", "pk")
    else:
        order = ("-moderated_at", "-created_at", "-pk")
    return comments.select_related("article", "replied_by", "moderated_by").order_by(*order)


def tab_counts(user: User, article_id: int | None = None) -> dict[str, int]:
    totals = moderation_comments(user, article_id).aggregate(
        **{key: Count("pk", filter=Q(status=status)) for key, (_, status) in TABS.items()}
    )
    return {key: totals[key] or 0 for key in TABS}


def pending_count(user: User) -> int:
    """Contador do menu e do início do painel."""
    if not permissions.is_staff_member(user):
        return 0
    return moderation_comments(user).filter(status=Status.PENDING).count()


def own_pending_count(user: User) -> int:
    """Pendentes só nas publicações que a pessoa assina (mesmo para editores)."""
    if not permissions.is_staff_member(user):
        return 0
    ids = ArticleContributor.objects.filter(
        user=user, role__in=ArticleContributor.EDITING_ROLES
    ).values("article_id")
    return Comment.objects.filter(article_id__in=ids, status=Status.PENDING).count()


def same_ip_counts(comments: list[Comment]) -> dict[str, int]:
    """Quantos comentários cada ip_hash da lista enviou (a marca "mesmo IP enviou N").

    O hash muda de sal todo mês e é apagado em 30 dias (docs/23), então a conta vale para o
    mês corrente. Comentários sem hash ficam de fora.
    """
    hashes = {comment.ip_hash for comment in comments if comment.ip_hash}
    if not hashes:
        return {}
    rows = (
        Comment.objects.filter(ip_hash__in=hashes)
        .values("ip_hash")
        .annotate(total=Count("pk"))
        .order_by()
    )
    return {row["ip_hash"]: row["total"] for row in rows}
