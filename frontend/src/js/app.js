// Ponto de entrada de todas as páginas: estilos, HTMX e Alpine (docs/05, D3).
import "../css/app.css";

import Alpine from "alpinejs";
import htmx from "htmx.org";

window.htmx = htmx;
window.Alpine = Alpine;

// O HTMX injetaria um <style> para os indicadores de carregamento, bloqueado pela
// Content-Security-Policy (docs/23). O projeto não usa a classe htmx-indicator.
htmx.config.includeIndicatorStyles = false;

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

// Foto de perfil (docs/14): recorte quadrado central no navegador antes de enviar.
// O servidor recorta de novo se a imagem chegar sem recorte (JavaScript desligado).
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
const AVATAR_SIDE = 1024;

Alpine.data("avatarPicker", (initialUrl = "") => ({
  preview: initialUrl,
  error: "",
  async pick(event) {
    const input = event.target;
    const file = input.files?.[0];
    this.error = "";
    if (!file) return;
    if (file.size > AVATAR_MAX_BYTES) {
      this.error = "A foto pode ter no máximo 5 MB.";
      input.value = "";
      return;
    }
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      const side = Math.min(bitmap.width, bitmap.height);
      const out = Math.min(side, AVATAR_SIDE);
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = out;
      canvas
        .getContext("2d")
        .drawImage(
          bitmap,
          (bitmap.width - side) / 2,
          (bitmap.height - side) / 2,
          side,
          side,
          0,
          0,
          out,
          out,
        );
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) throw new Error("sem blob");
      const cropped = new File([blob], "foto.jpg", { type: "image/jpeg" });
      const transfer = new DataTransfer();
      transfer.items.add(cropped);
      input.files = transfer.files;
      this.preview = URL.createObjectURL(cropped);
    } catch {
      // Navegador sem suporte: envia o arquivo original e o servidor recorta.
      this.preview = URL.createObjectURL(file);
    }
  },
}));

// Filtro de chips por texto (tópicos no perfil e no assistente).
Alpine.data("chipFilter", () => ({
  query: "",
  matches(name) {
    const plain = (text) =>
      text
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase();
    return !this.query || plain(name).includes(plain(this.query.trim()));
  },
}));

// Compartilhar (docs/11): copiar link, WhatsApp (link comum) e o menu nativo do celular.
// Sem scripts de redes sociais. A cópia tem plano B para navegadores sem Clipboard API
// (ou fora de HTTPS): seleciona o campo com o link para a pessoa copiar.
Alpine.data("share", () => ({
  copied: false,
  canShare: false,
  init() {
    this.canShare = typeof navigator.share === "function";
  },
  get url() {
    return this.$el.dataset.url;
  },
  done() {
    this.copied = true;
    setTimeout(() => (this.copied = false), 2500);
  },
  fallback() {
    const field = this.$refs.link;
    field.hidden = false;
    field.focus();
    field.select();
    try {
      if (document.execCommand("copy")) this.done();
    } catch {
      // Sem cópia automática: o link fica selecionado no campo.
    }
  },
  copy() {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(this.url).then(
        () => this.done(),
        () => this.fallback(),
      );
    } else {
      this.fallback();
    }
  },
  native() {
    navigator.share({ title: this.$el.dataset.title, url: this.url }).catch(() => {});
  },
}));

Alpine.start();
