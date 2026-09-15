"""Índice de busca das publicações (docs/19).

Cada publicação guarda um `search_vector`: as palavras do texto já "normalizadas" pelo
PostgreSQL (sem acento, no radical: "Física" e "fisica" viram "fisic"), com pesos:

    A  título
    B  linha fina e `search_meta` (disciplinas, tópicos e nomes nos créditos)
    C  corpo em texto (`body_text`)

A configuração `pt_unaccent` é criada pela migração 0006: é a `portuguese` com o dicionário
`unaccent` antes do radicalizador. Índice e consulta precisam usar a mesma configuração.

O vetor é atualizado de propósito pelos services (não por sinal) sempre que muda algo que
entra nele. O comando `reindex_search` refaz tudo e pode rodar quantas vezes quiser.
"""

from collections.abc import Iterable

from django.contrib.postgres.search import SearchVector
from django.db.models import TextField, Value

from .models import Article, ArticleContributor

SEARCH_CONFIG = "pt_unaccent"


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
