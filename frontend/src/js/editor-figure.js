// Nó "figure" do editor: imagem enviada ao servidor (MediaAsset) com legenda e crédito.
// Atributos iguais aos aceitos por backend/apps/publications/rendering.py.
import { Node } from "@tiptap/core";

export const Figure = Node.create({
  name: "figure",
  group: "block",
  atom: true,
  draggable: true,
  selectable: true,

  addAttributes() {
    const plain = (fallback = "") => ({ default: fallback, rendered: false });
    return {
      assetId: plain(null),
      src: plain(null),
      alt: plain(),
      caption: plain(),
      credit: plain(),
      size: plain("normal"),
    };
  },

  // Só figuras do próprio jornal (com data-asset-id); imagens coladas de outros sites são descartadas.
  parseHTML() {
    return [
      {
        tag: "figure[data-asset-id]",
        getAttrs: (el) => ({
          assetId: Number(el.getAttribute("data-asset-id")) || null,
          src: el.querySelector("img")?.getAttribute("src") || null,
          alt: el.querySelector("img")?.getAttribute("alt") || "",
          caption: el.querySelector("[data-caption]")?.textContent || "",
          credit: el.querySelector(".figure-credit")?.textContent || "",
          size: el.getAttribute("data-size") === "wide" ? "wide" : "normal",
        }),
      },
    ];
  },

  renderHTML({ node }) {
    const { assetId, src, alt, caption, credit, size } = node.attrs;
    return [
      "figure",
      {
        class: `figure figure--${size} editor-figure`,
        "data-asset-id": String(assetId ?? ""),
        "data-size": size,
      },
      ["img", { src: src || "", alt: alt || "", draggable: "false" }],
      [
        "figcaption",
        {},
        ["span", { "data-caption": "" }, caption || ""],
        ["span", { class: "figure-credit" }, credit || ""],
      ],
    ];
  },
});
