"""Versão do conteúdo público, para invalidar caches quando algo publicado muda.

Blocos em cache usam a versão na chave: ao publicar, editar ou arquivar, a versão sobe e as
chaves antigas deixam de ser lidas (expiram sozinhas). Os sinais ficam em signals.py.
"""

from django.core.cache import cache
from django.db import transaction

VERSION_KEY = "public-content:version"


def public_version() -> int:
    return cache.get_or_set(VERSION_KEY, 1, timeout=None)


def bump_public_version() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # chave ainda não existe
        cache.set(VERSION_KEY, 2, timeout=None)


def invalidate_public_content() -> None:
    """Sobe a versão agora e de novo depois do commit: quem remontar o cache no meio da
    transação não deixa guardada a versão antiga."""
    bump_public_version()
    transaction.on_commit(bump_public_version)
