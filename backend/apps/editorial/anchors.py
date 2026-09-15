"""Âncoras dos comentários editoriais (docs/17, "Comentários editoriais").

Estratégia: trecho citado com contexto. O comentário guarda o trecho selecionado, até
CONTEXT_MAX caracteres antes e depois dele e as posições em que estava. Para reencontrar,
procuramos todas as ocorrências do trecho no texto atual e ficamos com a que tem mais
contexto igual ao guardado (empate: a mais próxima da posição antiga). Assim, editar outro
parágrafo muda as posições, mas não a âncora. Se o trecho sumiu (ou só sobrou uma ocorrência
curta num contexto diferente), o comentário vira "trecho alterado".

As posições valem sobre o "texto da âncora" do documento, que o navegador reconstrói igual a
partir do HTML renderizado (frontend/src/js/review-comments.js, função readText):
- cada bloco de texto (parágrafo, título, item de lista com texto direto, citação da
  blockquote) vira uma linha, e blocos seguidos são separados por um "\\n";
- quebra de linha (hardBreak) vira "\\n";
- figuras (legenda e crédito) e linhas horizontais ficam de fora.
"""

from typing import Any

from apps.publications import rendering

SEPARATOR = "\n"
CONTEXT_MAX = 40
# Trechos longos são específicos o bastante para valer mesmo sem contexto igual.
SELF_EVIDENT_LENGTH = 30
# Trechos curtos precisam de ao menos este tanto de contexto igual (um espaço não basta).
MIN_CONTEXT = 4

SKIPPED_NODES = {"figure", "horizontalRule"}


def document_text(document: Any) -> str:
    """Texto da âncora do documento do editor (JSON ProseMirror)."""
    blocks: list[str] = []
    _collect(rendering.normalize(document), blocks)
    return SEPARATOR.join(block for block in blocks if block)


def _collect(node: dict, blocks: list[str]) -> None:
    kind = node.get("type")
    if kind in SKIPPED_NODES:
        return
    buffer: list[str] = []
    for child in node.get("content", []):
        if child["type"] == "text":
            buffer.append(child["text"])
        elif child["type"] == "hardBreak":
            buffer.append("\n")
        else:
            if buffer:
                blocks.append("".join(buffer))
                buffer = []
            _collect(child, blocks)
    if buffer:
        blocks.append("".join(buffer))
    if kind == "blockquote":
        cite = (node.get("attrs") or {}).get("cite")
        if cite:
            blocks.append(cite)


def context(text: str, start: int, end: int) -> tuple[str, str]:
    """O que vem antes e depois de um trecho, para guardar junto com a âncora."""
    return text[max(0, start - CONTEXT_MAX) : start], text[end : end + CONTEXT_MAX]


def _common_suffix(a: str, b: str) -> int:
    count = 0
    for x, y in zip(reversed(a), reversed(b), strict=False):
        if x != y:
            break
        count += 1
    return count


def _common_prefix(a: str, b: str) -> int:
    count = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        count += 1
    return count


def locate(
    text: str, quote: str, prefix: str = "", suffix: str = "", hint: int | None = None
) -> tuple[int, int] | None:
    """Onde o trecho está agora: (início, fim) no texto, ou None se não foi reencontrado."""
    if not quote:
        return None
    best: tuple[int, int] | None = None
    best_key: tuple[int, int] | None = None
    start = text.find(quote)
    while start != -1:
        end = start + len(quote)
        score = _common_suffix(text[max(0, start - len(prefix)) : start], prefix)
        score += _common_prefix(text[end : end + len(suffix)], suffix)
        key = (-score, abs(start - hint) if hint is not None else 0)
        if best_key is None or key < best_key:
            best, best_key = (start, end), key
        start = text.find(quote, start + 1)
    if best is None or best_key is None:
        return None
    needed = min(MIN_CONTEXT, len(prefix) + len(suffix))
    if -best_key[0] < needed and len(quote) < SELF_EVIDENT_LENGTH:
        return None  # trecho curto que só aparece em outro lugar: não é o comentado
    return best
