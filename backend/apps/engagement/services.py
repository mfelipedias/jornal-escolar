"""Regras das reações e das leituras (docs/20).

toggle_reaction: mesmo tipo remove, tipo diferente troca, sem reação cria. O total por tipo em
Article.reactions_count é recalculado na mesma transação, com a publicação travada.

A gravação do total usa QuerySet.update, que não dispara o post_save da publicação: reagir
não invalida o cache público da home e das listas (publications/cache.py).

record_read: conta uma leitura por pessoa, por publicação, por dia (INSERT ... ON CONFLICT DO
NOTHING); só quando a linha entra, Article.reads_count sobe, também por update().
"""

import hashlib
import hmac
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Count, F, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications.models import Article

from .models import ArticleRead, Reaction


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
