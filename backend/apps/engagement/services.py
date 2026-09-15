"""Regras das reações (docs/20).

toggle_reaction: mesmo tipo remove, tipo diferente troca, sem reação cria. O total por tipo em
Article.reactions_count é recalculado na mesma transação, com a publicação travada.

A gravação do total usa QuerySet.update, que não dispara o post_save da publicação: reagir
não invalida o cache público da home e das listas (publications/cache.py).
"""

import uuid

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count

from apps.accounts.models import User
from apps.editorial import permissions
from apps.publications.models import Article

from .models import Reaction


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
