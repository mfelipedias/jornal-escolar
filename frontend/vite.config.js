import { resolve } from "node:path";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// O Django serve os arquivos gerados em /static/dist/ (ver DJANGO_VITE em config/settings/base.py).
export default defineConfig({
  base: "/static/dist/",
  plugins: [tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // URLs absolutas para fontes e imagens quando a página vem do Django (porta 8000).
    origin: "http://localhost:5173",
    // Ligado pelo compose.yaml da raiz: dentro do container, observar arquivos por polling.
    watch: { usePolling: process.env.VITE_USE_POLLING === "true", interval: 300 },
  },
  build: {
    outDir: resolve(import.meta.dirname, "../backend/static/dist"),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: {
        app: resolve(import.meta.dirname, "src/js/app.js"),
        editor: resolve(import.meta.dirname, "src/js/editor.js"),
      },
    },
  },
});
