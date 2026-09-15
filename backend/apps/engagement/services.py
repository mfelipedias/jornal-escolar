"""Regras das reações, das leituras e dos comentários públicos (docs/20).

toggle_reaction: mesmo tipo remove, tipo diferente troca, sem reação cria. O total por tipo em
Article.reactions_count é recalculado na mesma transação, com a publicação travada.

A gravação do total usa QuerySet.update, que não dispara o post_save da publicação: reagir
não invalida o cache público da home e das listas (publications/cache.py).

record_read: conta uma leitura por pessoa, por publicação, por dia (INSERT ... ON CONFLICT DO
NOTHING); só quando a linha entra, Article.reads_count sobe, também por update().

submit_comment: comentário público pendente, com links removidos e limite de pendentes por
pessoa. reply_to_comment: resposta da equipe. Article.comments_count (só aprovados) é
recalculado por recount_comments, também por update().
"""

import hashlib
import hmac
import re
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.core.audit import hash_ip
from apps.editorial import permissions
from apps.publications.models import Article

from .models import ArticleRead, Comment, Reaction


def counts_for(article_id: int) -> dict[str, int]:
    """Total por tipo, só com os tipos que têm alguma reação (zero não aparece)."""
    rows = (
        Reaction.objects.filter(article_id=article_id)
        .values("kind")
        .annotate(total=Count("pk"))
        .order_by()
    )
    return {row["kind"]: row["total"] for row in rows if row["total"]}


def recount(article_id: int) -> dict[str, int]:
    counts = counts_for(article_id)
    Article.objects.filter(pk=article_id).update(reactions_count=counts)
    return counts


@transaction.atomic
def toggle_reaction(
    article: Article,
    kind: str,
    *,
    user: User | None = None,
    anon_key: uuid.UUID | None = None,
) -> str | None:
    """Aplica a reação de quem entrou (user) ou do visitante (anon_key).

    Devolve o tipo que ficou valendo, ou None se a reação foi removida. Atualiza
    article.reactions_count em memória para a view montar a barra.
    """
    if kind not in Reaction.Kind.values:
        raise ValidationError("Tipo de reação inválido.")
    if user is not None and not user.is_authenticated:
        user = None
    if not permissions.can_react(user or AnonymousUser(), article):
        raise PermissionDenied
    if user is None and anon_key is None:
        raise ValidationError("Visitante sem código anônimo.")

    # Trava a publicação: duas reações simultâneas da mesma pessoa não furam a unicidade e
    # o total não perde contagem.
    Article.objects.select_for_update().filter(pk=article.pk).values_list("pk").get()
    owner = {"user": user} if user is not None else {"anon_key": anon_key}
    current = Reaction.objects.filter(article=article, **owner).first()
    if current is None:
        Reaction.objects.create(article=article, kind=kind, **owner)
        result: str | None = kind
    elif current.kind == kind:
        current.delete()
        result = None
    else:
        current.kind = kind
        current.save(update_fields=["kind"])
        result = kind
    article.reactions_count = recount(article.pk)
    return result


def current_kind(article: Article, *, user: User | None, anon_key: uuid.UUID | None) -> str | None:
    """Reação que esta pessoa deixou na publicação, para marcar o botão."""
    if user is not None and user.is_authenticated:
        owner = {"user": user}
    elif anon_key is not None:
        owner = {"anon_key": anon_key}
    else:
        return None
    return Reaction.objects.filter(article=article, **owner).values_list("kind", flat=True).first()


# --- leituras ---


def viewer_key(day: date, *, user: User | None = None, anon_key: uuid.UUID | None = None) -> str:
    """Chave do leitor no dia: HMAC-SHA256 de "u:<id>" ou "a:<uuid>" com a SECRET_KEY.

    Sem a chave secreta não dá para saber quem leu; com o dia na conta, a mesma pessoa tem
    chaves diferentes em dias diferentes (docs/23: sem histórico de leitura identificável).
    """
    if user is not None:
        who = f"u:{user.pk}"
    elif anon_key is not None:
        who = f"a:{anon_key}"
    else:
        raise ValidationError("Leitor sem conta e sem código anônimo.")
    message = f"{day.isoformat()}|{who}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def record_read(
    article: Article,
    *,
    user: User | None = None,
    anon_key: uuid.UUID | None = None,
    day: date | None = None,
) -> bool:
    """Registra a leitura. Devolve True só quando ela contou (primeira da pessoa no dia).

    Não conta: publicação fora do ar, visitante sem código e quem aparece nos créditos da
    publicação (o autor revisando o próprio texto não infla o contador).
    """
    if article.status != Article.Status.PUBLISHED:
        return False
    if user is not None and not user.is_authenticated:
        user = None
    if user is not None and article.contributors.filter(user=user).exists():
        return False
    if user is None and anon_key is None:
        return False
    day = day or timezone.localdate()
    key = viewer_key(day, user=user, anon_key=anon_key)
    table = ArticleRead._meta.db_table
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {table} (article_id, viewer_key, day, created_at) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
                [article.pk, key, day, timezone.now()],
            )
            inserted = cursor.fetchone() is not None
        if inserted:
            Article.objects.filter(pk=article.pk).update(reads_count=F("reads_count") + 1)
    return inserted


def reads_since(articles: QuerySet[Article], days: int = 30) -> int:
    """Leituras dos últimos `days` dias (hoje incluído) nas publicações dadas."""
    start = timezone.localdate() - timedelta(days=days - 1)
    return ArticleRead.objects.filter(article__in=articles, day__gte=start).count()


def purge_old_reads(days: int | None = None) -> int:
    """Apaga registros diários antigos (padrão 90 dias). O total já está em reads_count."""
    days = days or settings.READS_RETENTION_DAYS
    limit = timezone.localdate() - timedelta(days=days)
    deleted, _ = ArticleRead.objects.filter(day__lt=limit).delete()
    return deleted


# --- comentários públicos ---

# Endereços com protocolo ou "www.", e-mails e domínios soltos com os finais mais comuns
# ("bit.ly/x", "site.com.br"). Palavras coladas por ponto ("sensores.Adorei") não casam.
LINK_RE = re.compile(
    r"""
    (?:https?|ftp)://\S+
    | \bwww\.\S+
    | [\w.+-]+@[\w-]+(?:\.[\w-]+)+
    | \b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*
      \.(?:com|net|org|info|biz|io|me|app|dev|xyz|site|online|store|link|ly|gl|gg|tv|co|br)
      (?:\.br)?\b(?:/\S*)?
    """,
    re.IGNORECASE | re.VERBOSE,
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class CommentLimitError(Exception):
    """A pessoa já tem o máximo de comentários aguardando aprovação nesta publicação."""


def strip_links(text: str) -> tuple[str, bool]:
    """Remove links e e-mails do texto. Devolve (texto limpo, se havia algum)."""
    cleaned, count = LINK_RE.subn("", text)
    return cleaned, count > 0


def clean_text(text: str) -> str:
    """Sem caracteres de controle, espaços repetidos ou mais de uma linha em branco seguida."""
    text = CONTROL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def pending_count(article: Article, anon_key: uuid.UUID) -> int:
    return Comment.objects.filter(
        article=article, anon_key=anon_key, status=Comment.Status.PENDING
    ).count()


def submit_comment(
    article: Article,
    *,
    author_name: str,
    body: str,
    anon_key: uuid.UUID | None = None,
    ip: str = "",
    user: User | None = None,
) -> Comment:
    """Grava um comentário pendente (docs/20). Nada aparece em público até a aprovação.

    Links e e-mails saem do corpo (marca had_links); nome com link é recusado. Visitante tem no
    máximo COMMENTS_PENDING_PER_KEY pendentes por publicação (CommentLimitError). Quem entrou
    no sistema (equipe) comenta sem o cookie e fica só com o limite por IP, aplicado na view.
    """
    if user is not None and not user.is_authenticated:
        user = None
    if not permissions.can_comment(user or AnonymousUser(), article):
        raise PermissionDenied
    if user is None and anon_key is None:
        raise ValidationError("Visitante sem código anônimo.")

    errors: dict[str, str] = {}
    name = re.sub(r"\s+", " ", CONTROL_RE.sub("", author_name)).strip()
    if strip_links(name)[1]:
        errors["author_name"] = "Use só o seu nome, sem links ou e-mail."
    elif not Comment.NAME_MIN <= len(name) <= Comment.NAME_MAX:
        errors["author_name"] = (
            f"O nome precisa ter de {Comment.NAME_MIN} a {Comment.NAME_MAX} caracteres."
        )
    text, had_links = strip_links(body)
    text = clean_text(text)
    if len(text) < Comment.BODY_MIN:
        errors["body"] = (
            "Links e e-mails não são aceitos. Escreva o comentário sem eles."
            if had_links
            else f"O comentário precisa de pelo menos {Comment.BODY_MIN} caracteres."
        )
    elif len(text) > Comment.BODY_MAX:
        errors["body"] = f"O comentário pode ter no máximo {Comment.BODY_MAX} caracteres."
    if errors:
        raise ValidationError(errors)

    limit = settings.COMMENTS_PENDING_PER_KEY
    if anon_key is not None and pending_count(article, anon_key) >= limit:
        raise CommentLimitError
    return Comment.objects.create(
        article=article,
        author_name=name,
        body=text,
        anon_key=anon_key,
        ip_hash=hash_ip(ip),
        had_links=had_links,
    )


def approved_comments(article: Article) -> QuerySet[Comment]:
    """Comentários visíveis na página: só os aprovados, do mais recente para o mais antigo."""
    return (
        Comment.objects.filter(article=article, status=Comment.Status.APPROVED)
        .select_related("replied_by")
        .order_by("-created_at", "-pk")
    )


def recount_comments(article_id: int) -> int:
    """Recalcula Article.comments_count (só aprovados), sem invalidar o cache público."""
    total = Comment.objects.filter(article_id=article_id, status=Comment.Status.APPROVED).count()
    Article.objects.filter(pk=article_id).update(comments_count=total)
    return total


@transaction.atomic
def reply_to_comment(user: User, comment: Comment, body: str) -> Comment:
    """Resposta da equipe a um comentário (docs/20): autores, coautores, editor e admin.

    Uma resposta por comentário; responder de novo substitui, e texto vazio apaga a resposta.
    Não muda a situação do comentário ("Responder e aprovar" é da moderação, E41).
    """
    if not permissions.can_reply_comment(user, comment.article):
        raise PermissionDenied
    text = clean_text(body or "")
    if len(text) > Comment.REPLY_MAX:
        raise ValidationError(
            {"reply_body": f"A resposta pode ter no máximo {Comment.REPLY_MAX} caracteres."}
        )
    if text:
        comment.reply_body = text
        comment.replied_by = user
        comment.replied_at = timezone.now()
    else:
        comment.reply_body = ""
        comment.replied_by = None
        comment.replied_at = None
    comment.save(update_fields=["reply_body", "replied_by", "replied_at"])
    return comment


def purge_old_comments(days: int | None = None) -> tuple[int, int]:
    """Prazo dos comentários (docs/20, docs/23), padrão 30 dias.

    Apaga os rejeitados há mais tempo que isso e limpa os dados técnicos (ip_hash e código
    anônimo) dos demais. Devolve (rejeitados apagados, comentários limpos).
    """
    days = days or settings.COMMENTS_RETENTION_DAYS
    limit = timezone.now() - timedelta(days=days)
    rejected = Comment.objects.filter(status=Comment.Status.REJECTED).filter(
        Q(moderated_at__lt=limit) | Q(moderated_at__isnull=True, created_at__lt=limit)
    )
    deleted, _ = rejected.delete()
    cleared = (
        Comment.objects.filter(created_at__lt=limit)
        .filter(~Q(ip_hash="") | Q(anon_key__isnull=False))
        .update(ip_hash="", anon_key=None)
    )
    return deleted, cleared
