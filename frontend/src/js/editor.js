// Editor de publicações (docs/16): TipTap 3 sem framework, autosave e barra de ferramentas.
// Os nós habilitados aqui precisam bater com backend/apps/publications/rendering.py.
import { Editor } from "@tiptap/core";
import Typography from "@tiptap/extension-typography";
import { CharacterCount, Placeholder } from "@tiptap/extensions";
import StarterKit from "@tiptap/starter-kit";

import { Figure } from "./editor-figure.js";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

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
      Figure,
    ],
    content: data.body,
    editorProps: {
      attributes: { "aria-label": "Texto da publicação", role: "textbox", "aria-multiline": "true" },
      handleDrop: (view, event, _slice, moved) => {
        const files = imageFiles(event.dataTransfer?.files);
        if (moved || !files.length) return false;
        event.preventDefault();
        const coords = view.posAtCoords({ left: event.clientX, top: event.clientY });
        files.forEach((file) => insertUploadedImage(file, coords?.pos));
        return true;
      },
      handlePaste: (_view, event) => {
        const files = imageFiles(event.clipboardData?.files);
        if (!files.length) return false;
        event.preventDefault();
        files.forEach((file) => insertUploadedImage(file));
        return true;
      },
      handleDoubleClickOn: (_view, pos, node) => {
        if (node.type.name !== "figure") return false;
        openImageDialog(pos);
        return true;
      },
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
        document.body.dispatchEvent(new CustomEvent("articleSaved")); // atualiza a checklist
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
    image: () => {
      if (editor.isActive("figure")) openImageDialog(editor.state.selection.from);
      else fileInput.click();
    },
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
    image: () => editor.isActive("figure"),
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

  // --- imagens (E16) ---
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = IMAGE_TYPES.join(",");
  fileInput.multiple = true;
  fileInput.hidden = true;
  fileInput.dataset.imageInput = "";
  root.appendChild(fileInput);
  fileInput.addEventListener("change", () => {
    imageFiles(fileInput.files).forEach((file) => insertUploadedImage(file));
    fileInput.value = "";
  });

  function imageFiles(list) {
    return Array.from(list || []).filter((file) => file.type.startsWith("image/"));
  }

  function uploadImage(file, onProgress) {
    return new Promise((resolve, reject) => {
      if (!IMAGE_TYPES.includes(file.type)) {
        reject(new Error("Envie uma imagem JPG, PNG ou WebP."));
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        reject(new Error("A imagem pode ter no máximo 10 MB."));
        return;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("article", String(data.articleId));
      const xhr = new XMLHttpRequest();
      xhr.open("POST", data.mediaUrl);
      xhr.setRequestHeader("X-CSRFToken", csrfToken());
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
      });
      xhr.addEventListener("load", () => {
        let body = {};
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          // resposta sem JSON
        }
        if (xhr.status === 201) resolve(body);
        else reject(new Error(body.error?.message || "Não foi possível enviar a imagem."));
      });
      xhr.addEventListener("error", () => reject(new Error("Falha de conexão ao enviar a imagem.")));
      xhr.send(form);
    });
  }

  async function insertUploadedImage(file, pos) {
    try {
      const asset = await uploadImage(file, (pct) => setStatus(`Enviando imagem… ${pct}%`));
      const node = {
        type: "figure",
        attrs: { assetId: asset.id, src: asset.variants.w960 || asset.url, alt: "", size: "normal" },
      };
      if (pos === undefined) editor.chain().focus().insertContent(node).run();
      else editor.chain().focus().insertContentAt(pos, node).run();
      const figurePos = findFigure(asset.id);
      if (figurePos !== null) openImageDialog(figurePos, true);
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  function findFigure(assetId) {
    let found = null;
    editor.state.doc.descendants((node, position) => {
      if (found === null && node.type.name === "figure" && node.attrs.assetId === assetId) {
        found = position;
      }
    });
    return found;
  }

  const dialog = document.querySelector("[data-image-dialog]");
  const dialogForm = dialog.querySelector("form");
  let dialogPos = null;

  async function openImageDialog(pos, isNew = false) {
    const node = editor.state.doc.nodeAt(pos);
    if (!node || node.type.name !== "figure") return;
    dialogPos = pos;
    const fields = dialogForm.elements;
    fields.alt.value = node.attrs.alt || "";
    fields.caption.value = node.attrs.caption || "";
    fields.credit.value = node.attrs.credit || "";
    fields.size.value = node.attrs.size || "normal";
    fields.is_decorative.checked = false;
    fields.has_people.checked = false;
    fields.consent_ok.checked = false;
    dialog.querySelector("[data-image-preview]").src = node.attrs.src || "";
    dialog.querySelector("[data-image-error]").hidden = true;
    dialog.querySelector("[data-image-new]").hidden = !isNew;
    dialog.showModal();
    try {
      const response = await fetch(`${data.mediaUrl}${node.attrs.assetId}/`, { credentials: "same-origin" });
      if (response.ok) {
        const asset = await response.json();
        fields.is_decorative.checked = asset.is_decorative;
        fields.has_people.checked = asset.has_people;
        fields.consent_ok.checked = asset.consent_ok;
        if (!fields.alt.value) fields.alt.value = asset.alt_text;
        if (!fields.credit.value) fields.credit.value = asset.credit;
      }
    } catch {
      // mantém os valores do nó
    }
    fields.alt.focus();
  }

  dialogForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (event.submitter?.value === "cancel") {
      dialog.close();
      return;
    }
    const fields = dialogForm.elements;
    const node = editor.state.doc.nodeAt(dialogPos);
    const errorEl = dialog.querySelector("[data-image-error]");
    if (!node) {
      dialog.close();
      return;
    }
    if (event.submitter?.value === "remove") {
      editor.chain().focus().setNodeSelection(dialogPos).deleteSelection().run();
      dialog.close();
      return;
    }
    if (!fields.is_decorative.checked && !fields.alt.value.trim()) {
      errorEl.textContent = "Descreva a imagem ou marque como decorativa.";
      errorEl.hidden = false;
      fields.alt.focus();
      return;
    }
    const metadata = {
      alt_text: fields.alt.value.trim(),
      is_decorative: fields.is_decorative.checked,
      credit: fields.credit.value.trim(),
      has_people: fields.has_people.checked,
      consent_ok: fields.consent_ok.checked,
    };
    const response = await fetch(`${data.mediaUrl}${node.attrs.assetId}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
      body: JSON.stringify(metadata),
    }).catch(() => null);
    if (!response?.ok) {
      const body = response ? await response.json().catch(() => ({})) : {};
      errorEl.textContent = body.error?.message || "Não foi possível salvar os dados da imagem.";
      errorEl.hidden = false;
      return;
    }
    editor
      .chain()
      .focus()
      .setNodeSelection(dialogPos)
      .updateAttributes("figure", {
        alt: metadata.is_decorative ? "" : metadata.alt_text,
        caption: fields.caption.value.trim(),
        credit: metadata.credit,
        size: fields.size.value === "wide" ? "wide" : "normal",
      })
      .run();
    dialog.close();
    document.body.dispatchEvent(new CustomEvent("articleSaved")); // autorização muda a checklist
  });

  // O painel lateral (HTMX) também altera a publicação: acompanha o updated_at dele.
  document.body.addEventListener("articleUpdated", (event) => {
    if (event.detail?.updatedAt) updatedAt = event.detail.updatedAt;
  });

  // Antes de publicar, garante que o texto digitado já foi salvo.
  document.body.addEventListener("htmx:confirm", (event) => {
    if (!event.target.closest?.("[data-flush-before]")) return;
    if (!dirty && !saving) return;
    event.preventDefault();
    flush().then((ok) => {
      if (ok) event.detail.issueRequest(true);
      else setStatus("Salve o texto antes de publicar (verifique a conexão).", "error");
    });
  });

  async function flush() {
    clearTimeout(debounceTimer);
    for (let i = 0; i < 50 && saving; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (dirty) await save();
    return !dirty && !blocked;
  }

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

const root = document.querySelector("[data-editor-root]");
if (document.getElementById("editor-data") && root) {
  window.jornalEditor = initEditor(root);
}
