// Editor de publicações (docs/16): TipTap 3 sem framework, autosave e barra de ferramentas.
// Os nós habilitados aqui precisam bater com backend/apps/publications/rendering.py.
import { Editor } from "@tiptap/core";
import Typography from "@tiptap/extension-typography";
import { CharacterCount, Placeholder } from "@tiptap/extensions";
import StarterKit from "@tiptap/starter-kit";

const DEBOUNCE_MS = 2000;
const MAX_WAIT_MS = 30000;
const RETRY_MAX_MS = 60000;

function csrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function autosize(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

function safeUrl(value) {
  const url = value.trim();
  if (!url) return null;
  if (/^(https?:\/\/|mailto:|\/(?!\/)|#)/i.test(url)) return url;
  if (/^[\w.-]+\.[a-z]{2,}(\/|$)/i.test(url)) return `https://${url}`; // "gov.br/inep"
  return null;
}

export function initEditor(root) {
  const data = JSON.parse(document.getElementById("editor-data").textContent);
  const titleEl = root.querySelector("[data-editor-title]");
  const subtitleEl = root.querySelector("[data-editor-subtitle]");
  const statusEl = document.querySelector("[data-save-status]");
  const countEl = root.querySelector("[data-editor-count]");
  const toolbar = root.querySelector("[data-editor-toolbar]");
  const linkForm = root.querySelector("[data-link-form]");
  const backupKey = `jornal:editor:${data.articleId}`;

  let updatedAt = data.updatedAt;
  let dirty = false;
  let saving = false;
  let blocked = false; // conflito: não tenta mais salvar
  let debounceTimer = null;
  let firstChangeAt = null;
  let retryDelay = 2000;

  titleEl.value = data.title;
  subtitleEl.value = data.subtitle;
  [titleEl, subtitleEl].forEach(autosize);

  const editor = new Editor({
    element: root.querySelector("[data-editor-body]"),
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        code: false,
        codeBlock: false,
        strike: false,
        underline: false,
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Placeholder.configure({ placeholder: "Comece a escrever…" }),
      CharacterCount,
      Typography,
    ],
    content: data.body,
    editorProps: {
      attributes: { "aria-label": "Texto da publicação", role: "textbox", "aria-multiline": "true" },
    },
    onUpdate: () => markDirty(),
    onSelectionUpdate: () => refreshToolbar(),
    onTransaction: () => refreshToolbar(),
  });

  // Recupera texto que não chegou ao servidor (queda de conexão, aba fechada).
  try {
    const backup = JSON.parse(localStorage.getItem(backupKey) || "null");
    if (backup && backup.baseUpdatedAt === data.updatedAt) {
      titleEl.value = backup.title;
      subtitleEl.value = backup.subtitle;
      editor.commands.setContent(backup.body_json, { emitUpdate: false });
      [titleEl, subtitleEl].forEach(autosize);
      markDirty();
      setStatus("Texto recuperado deste aparelho; salvando…");
    } else if (backup) {
      localStorage.removeItem(backupKey);
    }
  } catch {
    // localStorage indisponível: segue sem cópia local
  }

  function setStatus(text, tone = "neutral") {
    statusEl.textContent = text;
    statusEl.classList.toggle("text-danger", tone === "error");
    statusEl.classList.toggle("text-ink-3", tone !== "error");
  }

  function snapshot() {
    return { title: titleEl.value, subtitle: subtitleEl.value, body_json: editor.getJSON() };
  }

  function updateCount() {
    const words = editor.storage.characterCount.words();
    const minutes = Math.max(1, Math.ceil(words / 200));
    countEl.textContent = `${words} ${words === 1 ? "palavra" : "palavras"} · ${minutes} min de leitura`;
  }

  function markDirty() {
    if (blocked) return;
    dirty = true;
    updateCount();
    setStatus("Alterações não salvas");
    firstChangeAt ??= Date.now();
    clearTimeout(debounceTimer);
    const waited = Date.now() - firstChangeAt;
    debounceTimer = setTimeout(save, waited >= MAX_WAIT_MS ? 0 : DEBOUNCE_MS);
  }

  async function save() {
    if (!dirty || saving || blocked) return;
    saving = true;
    dirty = false;
    firstChangeAt = null;
    const body = snapshot();
    let retrying = false;
    setStatus("Salvando…");
    try {
      localStorage.setItem(backupKey, JSON.stringify({ ...body, baseUpdatedAt: updatedAt }));
    } catch {
      // sem cópia local
    }
    try {
      const response = await fetch(data.saveUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        credentials: "same-origin",
        body: JSON.stringify({ ...body, updated_at: updatedAt }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.ok) {
        updatedAt = result.updated_at;
        retryDelay = 2000;
        try {
          localStorage.removeItem(backupKey);
        } catch {
          // ignora
        }
        setStatus(dirty ? "Alterações não salvas" : `Salvo às ${result.saved_at}`);
      } else if (response.status === 409 || response.status === 403 || response.status === 413) {
        blocked = response.status !== 413;
        setStatus(result.error?.message || "Não foi possível salvar.", "error");
      } else if (response.status === 401) {
        blocked = true;
        setStatus("Sua sessão expirou. Entre de novo em outra aba; o texto está guardado neste aparelho.", "error");
      } else {
        throw new Error(result.error?.message || `HTTP ${response.status}`);
      }
    } catch {
      dirty = true;
      retrying = true;
      setStatus(`Falha ao salvar. Tentando de novo em ${Math.round(retryDelay / 1000)} s…`, "error");
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(save, retryDelay);
      retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
    } finally {
      saving = false;
      // Alguém digitou enquanto salvava: agenda o próximo salvamento.
      if (dirty && !blocked && !retrying) markDirty();
    }
  }

  // --- título e linha fina ---
  titleEl.addEventListener("input", () => {
    autosize(titleEl);
    markDirty();
  });
  subtitleEl.addEventListener("input", () => {
    autosize(subtitleEl);
    markDirty();
  });
  titleEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      subtitleEl.focus();
    }
  });
  subtitleEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      editor.commands.focus("start");
    }
  });

  // --- barra de ferramentas ---
  const commands = {
    paragraph: () => editor.chain().focus().setParagraph().run(),
    h2: () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
    h3: () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
    bold: () => editor.chain().focus().toggleBold().run(),
    italic: () => editor.chain().focus().toggleItalic().run(),
    bulletList: () => editor.chain().focus().toggleBulletList().run(),
    orderedList: () => editor.chain().focus().toggleOrderedList().run(),
    blockquote: () => editor.chain().focus().toggleBlockquote().run(),
    horizontalRule: () => editor.chain().focus().setHorizontalRule().run(),
    undo: () => editor.chain().focus().undo().run(),
    redo: () => editor.chain().focus().redo().run(),
    link: () => openLinkForm(),
  };
  const isActive = {
    paragraph: () => editor.isActive("paragraph"),
    h2: () => editor.isActive("heading", { level: 2 }),
    h3: () => editor.isActive("heading", { level: 3 }),
    bold: () => editor.isActive("bold"),
    italic: () => editor.isActive("italic"),
    link: () => editor.isActive("link"),
    bulletList: () => editor.isActive("bulletList"),
    orderedList: () => editor.isActive("orderedList"),
    blockquote: () => editor.isActive("blockquote"),
  };

  toolbar.addEventListener("click", (event) => {
    const button = event.target.closest("[data-cmd]");
    if (button) commands[button.dataset.cmd]?.();
  });

  function refreshToolbar() {
    toolbar.querySelectorAll("[data-cmd]").forEach((button) => {
      const check = isActive[button.dataset.cmd];
      if (check) button.setAttribute("aria-pressed", String(check()));
    });
    toolbar.querySelector('[data-cmd="undo"]').disabled = !editor.can().undo();
    toolbar.querySelector('[data-cmd="redo"]').disabled = !editor.can().redo();
  }

  // --- links ---
  const linkInput = linkForm.querySelector("input");
  function openLinkForm() {
    linkInput.value = editor.getAttributes("link").href || "";
    linkForm.hidden = false;
    linkInput.focus();
  }
  function closeLinkForm() {
    linkForm.hidden = true;
    editor.commands.focus();
  }
  linkForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const href = safeUrl(linkInput.value);
    if (!href) {
      linkInput.setCustomValidity("Use um endereço que comece com https:// ou mailto:");
      linkInput.reportValidity();
      return;
    }
    linkInput.setCustomValidity("");
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    closeLinkForm();
  });
  linkForm.querySelector("[data-link-remove]").addEventListener("click", () => {
    editor.chain().focus().extendMarkRange("link").unsetLink().run();
    closeLinkForm();
  });
  linkInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeLinkForm();
  });
  root.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openLinkForm();
    }
  });

  // Salva ao sair da aba e avisa se ainda há algo pendente.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") save();
  });
  window.addEventListener("beforeunload", (event) => {
    if (dirty || saving) event.preventDefault();
  });

  updateCount();
  refreshToolbar();
  if (!data.title) titleEl.focus();
  return editor;
}

const root = document.querySelector("main");
if (document.getElementById("editor-data") && root) {
  window.jornalEditor = initEditor(root);
}
