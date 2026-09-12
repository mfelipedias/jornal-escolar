// Ponto de entrada de todas as páginas: estilos, HTMX e Alpine (docs/05, D3).
import "../css/app.css";

import Alpine from "alpinejs";
import htmx from "htmx.org";

window.htmx = htmx;
window.Alpine = Alpine;

// Toast (docs/09): sucesso e informação somem em 4s; erro e aviso ficam até a pessoa fechar.
// Passar o mouse ou o foco por cima pausa a contagem.
const TOAST_MS = 4000;

Alpine.data("toast", () => ({
  open: true,
  timer: null,
  init() {
    this.resume();
  },
  get autoClose() {
    return !["error", "warning"].includes(this.$el.dataset.level);
  },
  pause() {
    clearTimeout(this.timer);
  },
  resume() {
    if (this.autoClose) {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.close(), TOAST_MS);
    }
  },
  close() {
    this.open = false;
    setTimeout(() => this.$el.remove(), 200);
  },
}));

Alpine.start();
