"""Limitador simples por janela fixa, usando o cache do Django (docs/23, "Rate limit").

Uso: if not hit(f"upload:{user.pk}", limit=60, period=3600): responder 429.
"""

import time

from django.core.cache import cache


def hit(key: str, *, limit: int, period: int) -> bool:
    """Registra uma ação. Devolve False quando a ação passou do limite na janela atual."""
    window = int(time.time() // period)
    cache_key = f"ratelimit:{key}:{window}"
    if cache.add(cache_key, 1, timeout=period):
        return True
    try:
        count = cache.incr(cache_key)
    except ValueError:  # a chave expirou entre o add e o incr
        cache.set(cache_key, 1, timeout=period)
        count = 1
    return count <= limit
