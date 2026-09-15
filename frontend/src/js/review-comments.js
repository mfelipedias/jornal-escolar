// Comentários da tela de revisão (docs/17): selecionar um trecho do texto para comentar,
// marcar no texto os trechos comentados e ir do trecho ao comentário (e vice-versa).
//
// As posições valem sobre o "texto da âncora", que precisa sair igual ao do servidor
// (backend/apps/editorial/anchors.py): blocos de texto separados por "\n", <br> vira "\n",
// figuras e linhas horizontais ficam de fora. locate() repete o algoritmo de lá.

const BLOCK_SELECTOR = "p, h2, h3, li, blockquote";
const SKIPPED_SELECTOR = "figure, hr";
const CONTEXT_MAX = 40;
const ANCHOR_MAX = 300;
const SELF_EVIDENT_LENGTH = 30;
const MIN_CONTEXT = 4;
const SELECTION_DELAY_MS = 150;
const HIDE_DELAY_MS = 300;
const EMPTY_SELECTION = { text: "", prefix: "", suffix: "", from: "" };

// Texto da âncora e onde cada nó de texto começa e termina dentro dele.
export function readText(root) {
  const pieces = [];
  let text = "";
  let lastBlock = null;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        if (node.matches(SKIPPED_SELECTOR)) return NodeFilter.FILTER_REJECT;
        return node.tagName === "BR" ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
      return node.data ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
    },
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    let block = element.closest(BLOCK_SELECTOR);
    if (!block || !root.contains(block)) block = root;
    if (lastBlock && block !== lastBlock) text += "\n";
    lastBlock = block;
    if (node.nodeType === Node.TEXT_NODE) {
      pieces.push({ node, start: text.length, end: text.length + node.data.length });
      text += node.data;
    } else {
      text += "\n";
    }
  }
  return { text, pieces };
}

// Posição no texto da âncora de um ponto do DOM (início ou fim de uma seleção).
function pointIndex(read, container, offset) {
  if (container.nodeType === Node.TEXT_NODE) {
    const piece = read.pieces.find((p) => p.node === container);
    if (piece) return piece.start + Math.min(offset, piece.end - piece.start);
  }
  const point = document.createRange();
  point.setStart(container, offset);
  const next = read.pieces.find((p) => point.comparePoint(p.node, 0) >= 0);
  return next ? next.start : read.text.length;
}

function commonSuffix(a, b) {
  let count = 0;
  while (count < a.length && count < b.length && a[a.length - 1 - count] === b[b.length - 1 - count]) {
    count += 1;
  }
  return count;
}

function commonPrefix(a, b) {
  let count = 0;
  while (count < a.length && count < b.length && a[count] === b[count]) count += 1;
  return count;
}

// Mesmo algoritmo de anchors.locate: a ocorrência com mais contexto igual, depois a mais perto.
export function locate(text, quote, prefix = "", suffix = "", hint = null) {
  if (!quote) return null;
  let best = null;
  let bestScore = -1;
  let bestDistance = Infinity;
  for (let start = text.indexOf(quote); start !== -1; start = text.indexOf(quote, start + 1)) {
    const end = start + quote.length;
    const score =
      commonSuffix(text.slice(Math.max(0, start - prefix.length), start), prefix) +
      commonPrefix(text.slice(end, end + suffix.length), suffix);
    const distance = hint === null ? 0 : Math.abs(start - hint);
    if (score > bestScore || (score === bestScore && distance < bestDistance)) {
      best = [start, end];
      bestScore = score;
      bestDistance = distance;
    }
  }
  if (!best) return null;
  const needed = Math.min(MIN_CONTEXT, prefix.length + suffix.length);
  if (bestScore < needed && quote.length < SELF_EVIDENT_LENGTH) return null;
  return best;
}

function clearMarks(root) {
  root.querySelectorAll("mark.review-anchor").forEach((mark) => mark.replaceWith(...mark.childNodes));
  root.normalize();
}

function wrapRange(root, start, end, commentId) {
  const { pieces } = readText(root);
  for (const piece of pieces) {
    const from = Math.max(start, piece.start);
    const to = Math.min(end, piece.end);
    if (from >= to) continue;
    let node = piece.node;
    if (to - piece.start < node.data.length) node.splitText(to - piece.start);
    if (from > piece.start) node = node.splitText(from - piece.start);
    const mark = document.createElement("mark");
    mark.className = "review-anchor";
    mark.dataset.comment = commentId;
    mark.title = "Ver comentário";
    node.parentNode.insertBefore(mark, node);
    mark.appendChild(node);
  }
}

function flash(element, className) {
  element.classList.add(className);
  setTimeout(() => element.classList.remove(className), 2000);
}

export function registerReviewComments(Alpine) {
  Alpine.data("reviewPage", (openCount = 0) => ({
    openCount,
    // Seleção feita no texto, esperando o toque em "Comentar".
    pending: null,
    // Trecho escolhido para o comentário que está sendo escrito.
    selection: { ...EMPTY_SELECTION },
    selectionTimer: null,
    hideTimer: null,

    init() {
      this.textRoot = this.$el.querySelector("[data-review-text]");
      this.onSelectionChange = () => {
        clearTimeout(this.selectionTimer);
        this.selectionTimer = setTimeout(() => this.updatePending(), SELECTION_DELAY_MS);
      };
      document.addEventListener("selectionchange", this.onSelectionChange);
    },

    destroy() {
      document.removeEventListener("selectionchange", this.onSelectionChange);
    },

    get selectionPreview() {
      const text = this.selection.text;
      return `“${text.length > 140 ? `${text.slice(0, 139)}…` : text}”`;
    },

    readSelection() {
      const selection = window.getSelection();
      if (!this.textRoot || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
        return null;
      }
      const range = selection.getRangeAt(0);
      if (!this.textRoot.contains(range.commonAncestorContainer)) return null;
      const read = readText(this.textRoot);
      let start = pointIndex(read, range.startContainer, range.startOffset);
      let end = pointIndex(read, range.endContainer, range.endOffset);
      while (start < end && /\s/.test(read.text[start])) start += 1;
      while (end > start && /\s/.test(read.text[end - 1])) end -= 1;
      if (end <= start) return null;
      return {
        text: read.text.slice(start, end),
        prefix: read.text.slice(Math.max(0, start - CONTEXT_MAX), start),
        suffix: read.text.slice(end, end + CONTEXT_MAX),
        from: start,
        tooLong: end - start > ANCHOR_MAX,
        rect: range.getBoundingClientRect(),
      };
    },

    updatePending() {
      const found = this.readSelection();
      if (!found) {
        // Tocar em "Comentar" pode desfazer a seleção antes do clique: espera um pouco.
        clearTimeout(this.hideTimer);
        this.hideTimer = setTimeout(() => {
          this.pending = null;
        }, HIDE_DELAY_MS);
        return;
      }
      clearTimeout(this.hideTimer);
      this.pending = found;
      this.placeButton(found.rect);
    },

    placeButton(rect) {
      const button = this.$refs.commentButton;
      const box = this.$refs.textBox;
      if (!button || !box) return;
      const bounds = box.getBoundingClientRect();
      const left = Math.max(8, Math.min(rect.left - bounds.left, bounds.width - 160));
      button.style.setProperty("--anchor-x", `${left}px`);
      button.style.setProperty("--anchor-y", `${rect.bottom - bounds.top + 8}px`);
    },

    startComment() {
      const pending = this.pending;
      if (!pending || pending.tooLong) return;
      this.selection = {
        text: pending.text,
        prefix: pending.prefix,
        suffix: pending.suffix,
        from: String(pending.from),
      };
      this.pending = null;
      window.getSelection()?.removeAllRanges();
      const body = document.getElementById("comment-body");
      if (body) {
        body.scrollIntoView({ behavior: "smooth", block: "center" });
        body.focus({ preventScroll: true });
      }
    },

    clearSelection() {
      this.selection = { ...EMPTY_SELECTION };
    },

    // Chamado pelo painel de comentários a cada carga (x-init), inclusive depois do HTMX.
    syncComments(section) {
      this.openCount = Number(section.dataset.openCount || 0);
      if (!section.dataset.error) this.clearSelection();
      if (!this.textRoot) return;
      clearMarks(this.textRoot);
      const { text } = readText(this.textRoot);
      section.querySelectorAll("[data-anchor-text]").forEach((item) => {
        const data = item.dataset;
        let range = [Number(data.anchorStart), Number(data.anchorEnd)];
        if (text.slice(range[0], range[1]) !== data.anchorText) {
          range = locate(text, data.anchorText, data.anchorPrefix, data.anchorSuffix, range[0]);
        }
        if (range) wrapRange(this.textRoot, range[0], range[1], data.comment);
      });
    },

    // Clique num trecho marcado: vai ao comentário.
    openCommentFromText(event) {
      const mark = event.target.closest("mark.review-anchor");
      if (!mark || !window.getSelection()?.isCollapsed) return;
      const item = document.getElementById(`comentario-${mark.dataset.comment}`);
      if (!item) return;
      item.scrollIntoView({ behavior: "smooth", block: "center" });
      item.focus({ preventScroll: true });
      flash(item, "is-active");
    },

    // Clique no trecho citado no comentário: vai ao texto.
    showAnchor(commentId) {
      const marks = this.textRoot?.querySelectorAll(`mark.review-anchor[data-comment="${commentId}"]`);
      if (!marks || !marks.length) return;
      marks[0].scrollIntoView({ behavior: "smooth", block: "center" });
      marks.forEach((mark) => flash(mark, "is-active"));
    },
  }));
}
