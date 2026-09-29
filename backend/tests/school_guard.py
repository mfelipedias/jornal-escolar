"""O nome da escola nunca aparece no site, nas configurações nem nos dados (CLAUDE.md).

O teste precisa saber qual é o nome sem escrevê-lo, porque o repositório é público: guardamos
só o SHA-256 do sobrenome da escola, em minúsculas e sem acento, e comparamos com cada palavra
do texto.
"""

import hashlib
import re
import unicodedata

FORBIDDEN_WORD_SHA256 = frozenset(
    {"074b0c24ddf7423f3a37628cef04305f59958f2682a70dc146c96842e7ef0ee8"}
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def mentions_school(text: str) -> bool:
    words = set(re.findall(r"\w+", _fold(text)))
    return any(hashlib.sha256(word.encode()).hexdigest() in FORBIDDEN_WORD_SHA256 for word in words)
