// Movimento e carregamento (docs/09, "Movimento"): barra de progresso no topo, cabeçalho que
// encolhe ao rolar e o pulinho das reações (a entrada dos cards é só CSS, em app.css). Só classes e
// variáveis CSS pelo CSSOM (a Content-Security-Policy bloqueia style inline). Com
// prefers-reduced-motion o CSS desliga as animações e aqui nada é escondido.

const root = document.documentElement;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// --- Barra de progresso ---------------------------------------------------------------------

const HTMX_DELAY_MS = 150; // respostas rápidas do HTMX não piscam a barra
const SAFETY_MS = 10000; // navegação cancelada (ex.: aviso do editor) não prende a barra
const USER_EVENTS = new Set(["click", "submit", "change", "input", "keyup", "search"]);
const HTMX_SELECTOR =
  "[hx-get], [hx-post], [hx-put], [hx-patch], [hx-delete], [hx-boost], " +
  "[data-hx-get], [data-hx-post]";

let showTimer = 0;
let safetyTimer = 0;
let doneTimer = 0;
let htmxPending = 0;

function progressBar() {
  return document.querySelector(".page-progress");
}

function startProgress(delay = 0) {
  if (!progressBar()) return;
  clearTimeout(showTimer);
  clearTimeout(doneTimer);
  showTimer = setTimeout(() => {
    root.classList.remove("is-loaded");
    root.classList.add("is-loading");
  }, delay);
  clearTimeout(safetyTimer);
  safetyTimer = setTimeout(finishProgress, SAFETY_MS);
}

function finishProgress() {
  clearTimeout(showTimer);
  clearTimeout(safetyTimer);
  const bar = progressBar();
  if (!bar || !root.classList.contains("is-loading")) return;
  // Completa a partir de onde a barra está, não do começo.
  try {
    const scale = new DOMMatrixReadOnly(getComputedStyle(bar).transform).a;
    bar.style.setProperty("--progress-from", String(Math.min(Math.max(scale, 0), 1)));
  } catch {
    // Navegador sem DOMMatrix: o CSS usa o valor padrão.
  }
  root.classList.remove("is-loading");
  root.classList.add("is-loaded");
  doneTimer = setTimeout(() => root.classList.remove("is-loaded"), 400);
}

function resetProgress() {
  clearTimeout(showTimer);
  clearTimeout(safetyTimer);
  clearTimeout(doneTimer);
  htmxPending = 0;
  root.classList.remove("is-loading", "is-loaded");
}

function leavesPage(link, event) {
  if (event.defaultPrevented || event.button !== 0) return false;
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return false;
  if (link.hasAttribute("download") || link.closest("[data-no-progress]")) return false;
  if (link.target && link.target !== "_self") return false;
  if (link.closest(HTMX_SELECTOR)) return false;
  const href = link.getAttribute("href");
  if (!href || href.startsWith("#")) return false;
  const url = new URL(link.href, window.location.href);
  if (!["http:", "https:"].includes(url.protocol)) return false;
  if (url.origin !== window.location.origin) return false;
  // Só a âncora mudou: a página não troca.
  const samePage =
    url.pathname === window.location.pathname && url.search === window.location.search;
  return !(samePage && url.hash);
}

function watchProgress() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (link && leavesPage(link, event)) startProgress();
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (event.defaultPrevented || !(form instanceof HTMLFormElement)) return;
    if (form.closest("[data-no-progress]") || form.closest(HTMX_SELECTOR)) return;
    if (form.method === "dialog" || (form.target && form.target !== "_self")) return;
    startProgress();
  });

  document.addEventListener("htmx:beforeRequest", (event) => {
    const { elt, requestConfig } = event.detail;
    if (elt.closest?.("[data-no-progress]")) return;
    // Atualizações de fundo (ex.: conferência do editor depois de salvar) não mostram a barra.
    const trigger = requestConfig?.triggeringEvent?.type;
    if (trigger && !USER_EVENTS.has(trigger)) return;
    htmxPending += 1;
    startProgress(HTMX_DELAY_MS);
  });

  const htmxDone = () => {
    if (htmxPending === 0) return;
    htmxPending -= 1;
    if (htmxPending === 0) finishProgress();
  };
  for (const name of ["htmx:afterRequest", "htmx:sendError", "htmx:timeout", "htmx:sendAbort"]) {
    document.addEventListener(name, htmxDone);
  }

  // Voltar pelo histórico pode restaurar a página com a barra ainda ligada (bfcache).
  window.addEventListener("pageshow", resetProgress);
}

// --- Cabeçalho que encolhe ao rolar ---------------------------------------------------------

function watchMasthead() {
  const masthead = document.querySelector(".masthead");
  if (!masthead) return;
  let ticking = false;
  const update = () => {
    ticking = false;
    const y = window.scrollY;
    // Folga entre ligar (24px) e desligar (4px) para não ficar piscando no limite.
    if (y > 24) masthead.classList.add("is-scrolled");
    else if (y < 4) masthead.classList.remove("is-scrolled");
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    },
    { passive: true },
  );
  update();
}

// --- Reações: pulinho no botão escolhido ----------------------------------------------------

function popReactions() {
  document.addEventListener("htmx:afterSwap", (event) => {
    if (reducedMotion.matches) return;
    const submitter = event.detail.requestConfig?.triggeringEvent?.submitter;
    if (!submitter?.classList?.contains("reaction-btn")) return;
    const button = document.getElementById(submitter.id);
    if (!button || button.getAttribute("aria-pressed") !== "true") return;
    button.classList.add("is-popping");
    button.addEventListener("animationend", () => button.classList.remove("is-popping"), {
      once: true,
    });
  });
}

// --- Ligações -------------------------------------------------------------------------------

export function configureHtmxTransitions(htmx) {
  htmx.config.globalViewTransitions = true;
  // No painel e no editor a troca é imediata: um fade por cima de quem está digitando atrapalha.
  document.addEventListener("htmx:beforeTransition", (event) => {
    if (!document.querySelector(".masthead") || reducedMotion.matches) event.preventDefault();
  });
}

export function startMotion() {
  watchProgress();
  watchMasthead();
  popReactions();
}
