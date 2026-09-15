"""Índice de busca das publicações (docs/19).

Cada publicação guarda um `search_vector`: as palavras do texto já "normalizadas" pelo
PostgreSQL (sem acento, no radical: "Física" e "fisica" viram "fisic"), com pesos:

    A  título
    B  linha fina e `search_meta` (disciplinas, tópicos e nomes nos créditos)
    C  corpo em texto (`body_text`)

A configuração `pt_unaccent` é criada pela migração 0006: é a `portuguese` com o dicionário
`unaccent` antes do radicalizador. Índice e consulta precisam usar a mesma configuração.

A consulta está em `selectors.py` (search_published e o fallback por trigramas); aqui ficam
também as peças de apoio: `Unaccent`, a limpeza do termo e o trecho destacado (`highlight`).

O vetor é atualizado de propósito pelos services (não por sinal) sempre que muda algo que
entra nele. O comando `reindex_search` refaz tudo e pode rodar quantas vezes quiser.
"""

import re
from collections.abc import Iterable

from django.contrib.postgres.search import SearchVector
from django.db.models import Func, TextField, Value
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

from .models import Article, ArticleContributor

SEARCH_CONFIG = "pt_unaccent"
QUERY_MAX_LENGTH = 100


class Unaccent(Func):
    """f_unaccent(texto): tira os acentos no banco ("Física" → "Fisica"), para trigramas."""

    function = "f_unaccent"
    output_field = TextField()


def clean_query(query: str | None) -> str:
    """Termo digitado numa linha só, sem espaços repetidos e com no máximo 100 caracteres."""
    return " ".join((query or "").split())[:QUERY_MAX_LENGTH].strip()


def plain_words(query: str) -> str:
    """Termo sem a sintaxe de buscador (aspas e -palavra), para comparar por trigramas."""
    words = [w for w in query.replace('"', " ").split() if not w.startswith("-")]
    return " ".join(words)


# Marcas do trecho destacado. O PostgreSQL devolve o texto do corpo com estas marcas em volta
# dos termos encontrados; são caracteres de uso privado do Unicode, que não aparecem em texto
# comum. O HTML só é montado aqui, depois de escapar o texto (docs/19, docs/23).
MARK_START = ""
MARK_STOP = ""
SNIPPET_MAX_CHARS = 200
_MARKS_RE = re.compile(f"({MARK_START}|{MARK_STOP})")


def highlight(raw: str, body_text: str = "", limit: int = SNIPPET_MAX_CHARS) -> SafeString:
    """Trecho do SearchHeadline como HTML seguro: texto escapado e termos em <mark>.

    Corta em até `limit` caracteres visíveis sem partir palavras e põe "…" nas pontas quando
    o trecho não começa no início do corpo ou não chega ao fim dele.
    """
    raw = " ".join((raw or "").split())
    if not raw.replace(MARK_START, "").replace(MARK_STOP, "").strip():
        return mark_safe("")
    pieces: list[str] = []
    used = 0
    marked = False
    cut = False
    for token in _MARKS_RE.split(raw):
        if token in (MARK_START, MARK_STOP):
            marked = token == MARK_START
            continue
        if not token:
            continue
        room = limit - used
        if len(token) > room:
            cut = True
            if marked:  # termo destacado não é partido ao meio
                break
            token = token[:room].rsplit(" ", 1)[0] if " " in token[:room] else ""
            if not token:
                break
        pieces.append(f"<mark>{escape(token)}</mark>" if marked else str(escape(token)))
        used += len(token)
        if cut:
            break
    html = "".join(pieces).rstrip()
    plain = _MARKS_RE.sub("", raw)
    body = " ".join((body_text or "").split())
    if body and not body.startswith(plain[:30]):
        html = "…" + html
    if cut or (body and not body.endswith(plain[-30:])):
        html = html.rstrip(".,;:") + "…"
    return mark_safe(html)  # cada pedaço de texto passou por escape()


def build_meta(article: Article) -> str:
    """Nomes de disciplinas, tópicos e créditos visíveis, numa linha só."""
    names = [
        *article.disciplines.order_by("name").values_list("name", flat=True),
        *article.topics.order_by("name").values_list("name", flat=True),
        *ArticleContributor.objects.filter(article=article, show_in_credits=True)
        .order_by("order", "pk")
        .values_list("display_name", flat=True),
    ]
    return " · ".join(name for name in names if name)


def vector_for(meta: str) -> SearchVector:
    """Expressão SQL do vetor, calculada pelo banco a partir das colunas da publicação."""
    return (
        SearchVector("title", weight="A", config=SEARCH_CONFIG)
        + SearchVector("subtitle", weight="B", config=SEARCH_CONFIG)
        + SearchVector(Value(meta, output_field=TextField()), weight="B", config=SEARCH_CONFIG)
        + SearchVector("body_text", weight="C", config=SEARCH_CONFIG)
    )


def update_search_vector(article: Article | int) -> None:
    """Recalcula o vetor de uma publicação com o que está gravado no banco.

    Usa .update(): não mexe em updated_at (não gera conflito no editor) nem dispara sinais.
    """
    pk = article if isinstance(article, int) else article.pk
    current = Article.objects.filter(pk=pk).first()
    if current is None:
        return
    meta = build_meta(current)
    Article.objects.filter(pk=pk).update(search_meta=meta, search_vector=vector_for(meta))


def update_search_vectors(article_ids: Iterable[int]) -> int:
    ids = sorted(set(article_ids))
    for pk in ids:
        update_search_vector(pk)
    return len(ids)


def reindex_all() -> int:
    """Refaz o índice de todas as publicações (qualquer estado). Devolve quantas."""
    return update_search_vectors(Article.objects.values_list("pk", flat=True))
