"""Classificação das notícias por tópico e disciplina (E47; docs/21, "Classificação").

Dois métodos automáticos, sem IA:

- Padrão da fonte (`source_default`): os tópicos e as disciplinas padrão da fonte, com 0,4.
- Palavra-chave (`keyword`): as `keywords` de cada tópico ativo, procuradas sem acento e sem
  diferença de maiúsculas, como palavra inteira ("arte" não acha "partes"). Cada palavra-chave
  encontrada no título vale 2 pontos e no resumo, 1 (nos dois, 3). O score é
  0,1 + 0,2 * pontos, entre 0,3 e 0,9: uma palavra só no resumo dá 0,3; no título, 0,5; duas
  no título, 0,9.
  Siglas curtas escritas em maiúsculas no admin (IA, SUS, COP, OBA) só contam em maiúsculas
  no texto, porque "ia", "sus" e "oba" também são palavras comuns.

As disciplinas vêm dos tópicos encontrados (`Topic.disciplines`, com o score do tópico) e das
disciplinas padrão da fonte. A tela de sugestões (E48) mostra os de score 0,5 ou mais.

Classificar de novo apaga só as linhas automáticas da notícia; os ajustes manuais ficam.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.db import transaction

from apps.taxonomy.models import Topic

from .models import NewsItem, NewsItemClassification, NewsSource
from .normalize import fold

Method = NewsItemClassification.Method

SOURCE_DEFAULT_SCORE = 0.4
KEYWORD_MIN_SCORE = 0.3
KEYWORD_MAX_SCORE = 0.9
TITLE_POINTS = 2
SUMMARY_POINTS = 1
# A tela de sugestões mostra tópicos e disciplinas a partir deste score.
VISIBLE_SCORE = 0.5
# Siglas até este tamanho, escritas em maiúsculas, só casam em maiúsculas.
ACRONYM_MAX_LENGTH = 4


def keyword_score(points: int) -> float:
    if points <= 0:
        return 0.0
    return round(min(KEYWORD_MAX_SCORE, 0.1 + 0.2 * points), 2)


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _is_acronym(term: str) -> bool:
    letters = term.replace("-", "")
    return letters.isalpha() and letters.isupper() and len(letters) <= ACRONYM_MAX_LENGTH


@dataclass(frozen=True)
class _Keyword:
    term: str
    pattern: re.Pattern[str]
    case_sensitive: bool

    @classmethod
    def build(cls, term: str) -> "_Keyword | None":
        term = " ".join(term.split())
        if not term:
            return None
        case_sensitive = _is_acronym(term)
        folded = _strip_accents(term) if case_sensitive else fold(term)
        words = [re.escape(word) for word in folded.split()]
        pattern = re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)")
        return cls(term=term, pattern=pattern, case_sensitive=case_sensitive)


@dataclass
class _Text:
    """O mesmo texto em duas formas: sem acento, e sem acento e em minúsculas."""

    plain: str
    folded: str

    @classmethod
    def build(cls, value: str) -> "_Text":
        return cls(plain=_strip_accents(value), folded=fold(value))

    def contains(self, keyword: _Keyword) -> bool:
        haystack = self.plain if keyword.case_sensitive else self.folded
        return keyword.pattern.search(haystack) is not None


@dataclass
class _TopicRule:
    topic_id: int
    keywords: list[_Keyword]
    discipline_ids: list[int]


@dataclass
class Match:
    """Resultado para um alvo (tópico ou disciplina) antes de gravar."""

    score: float
    method: str
    matched: list[str] = field(default_factory=list)


@dataclass
class Classification:
    topics: dict[int, Match] = field(default_factory=dict)
    disciplines: dict[int, Match] = field(default_factory=dict)

    def add_topic(self, topic_id: int, match: Match) -> None:
        _keep_best(self.topics, topic_id, match)

    def add_discipline(self, discipline_id: int, match: Match) -> None:
        _keep_best(self.disciplines, discipline_id, match)


def _keep_best(target: dict[int, Match], key: int, match: Match) -> None:
    current = target.get(key)
    if current is None or match.score > current.score:
        target[key] = match


class Classifier:
    """Carrega tópicos, palavras-chave e padrões das fontes uma vez e classifica muitas
    notícias em seguida (uma coleta, um comando de reclassificação)."""

    def __init__(self) -> None:
        self.rules: list[_TopicRule] = []
        topics = Topic.objects.filter(is_active=True).prefetch_related("disciplines")
        for topic in topics:
            keywords = [kw for kw in map(_Keyword.build, topic.keywords or []) if kw]
            if not keywords:
                continue
            discipline_ids = [d.pk for d in topic.disciplines.all() if d.is_active]
            self.rules.append(_TopicRule(topic.pk, keywords, discipline_ids))
        self._source_defaults: dict[int, tuple[list[int], list[int]]] = {}

    def _defaults(self, source: NewsSource) -> tuple[list[int], list[int]]:
        if source.pk not in self._source_defaults:
            topic_ids = list(
                source.default_topics.filter(is_active=True).values_list("pk", flat=True)
            )
            discipline_ids = list(
                source.default_disciplines.filter(is_active=True).values_list("pk", flat=True)
            )
            self._source_defaults[source.pk] = (topic_ids, discipline_ids)
        return self._source_defaults[source.pk]

    def classify(self, item: NewsItem) -> Classification:
        result = Classification()
        topic_ids, discipline_ids = self._defaults(item.source)
        for topic_id in topic_ids:
            result.add_topic(topic_id, Match(SOURCE_DEFAULT_SCORE, Method.SOURCE_DEFAULT))
        for discipline_id in discipline_ids:
            result.add_discipline(discipline_id, Match(SOURCE_DEFAULT_SCORE, Method.SOURCE_DEFAULT))

        title = _Text.build(item.title)
        summary = _Text.build(item.summary)
        for rule in self.rules:
            points = 0
            matched: list[str] = []
            for keyword in rule.keywords:
                hits = TITLE_POINTS * title.contains(keyword)
                hits += SUMMARY_POINTS * summary.contains(keyword)
                if hits:
                    points += hits
                    matched.append(keyword.term)
            if not points:
                continue
            match = Match(keyword_score(points), Method.KEYWORD, matched)
            result.add_topic(rule.topic_id, match)
            for discipline_id in rule.discipline_ids:
                result.add_discipline(discipline_id, Match(match.score, Method.KEYWORD, matched))
        return result

    def save(self, item: NewsItem) -> Classification:
        """Classifica e grava, trocando só as linhas automáticas da notícia."""
        result = self.classify(item)
        rows = [_row(item, match, topic_id=pk) for pk, match in result.topics.items()]
        rows += [_row(item, match, discipline_id=pk) for pk, match in result.disciplines.items()]
        with transaction.atomic():
            item.classifications.exclude(method=Method.MANUAL).delete()
            NewsItemClassification.objects.bulk_create(rows)
        return result


def _row(item: NewsItem, match: Match, **target: int) -> NewsItemClassification:
    return NewsItemClassification(
        item=item,
        score=match.score,
        method=match.method,
        matched=", ".join(match.matched)[:300],
        **target,
    )


def classify_items(items: Iterable[NewsItem], classifier: Classifier | None = None) -> int:
    """Classifica (de novo) as notícias dadas. Devolve quantas receberam ao menos um tópico ou
    disciplina."""
    classifier = classifier or Classifier()
    classified = 0
    for item in items:
        result = classifier.save(item)
        classified += bool(result.topics or result.disciplines)
    return classified
