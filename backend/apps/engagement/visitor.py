"""Cookie anônimo do visitante (docs/20, docs/23).

O cookie "jv" guarda um UUID v4 aleatório por 1 ano, com SameSite=Lax, HttpOnly e Secure em
produção. Não identifica a pessoa: serve para lembrar a reação dela e, na E39, não contar a
mesma leitura duas vezes. É emitido pela página da publicação; os endpoints ignoram quem
chega sem ele (robôs que só disparam POST).
"""

import uuid

from django.conf import settings
from django.http import HttpRequest, HttpResponse

COOKIE_NAME = "jv"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def anon_key(request: HttpRequest) -> uuid.UUID | None:
    """Código do cookie, se existir e for um UUID válido."""
    value = request.COOKIES.get(COOKIE_NAME, "")
    try:
        key = uuid.UUID(value) if value else None
    except ValueError:
        return None
    return key if key is not None and key.version == 4 else None


def ensure_cookie(request: HttpRequest, response: HttpResponse) -> uuid.UUID:
    """Emite o cookie quando falta (ou é inválido). Devolve o código em vigor."""
    key = anon_key(request)
    if key is not None:
        return key
    key = uuid.uuid4()
    response.set_cookie(
        COOKIE_NAME,
        str(key),
        max_age=COOKIE_MAX_AGE,
        samesite="Lax",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return key
