// Ponto de entrada de todas as páginas: estilos, HTMX e Alpine (docs/05, D3).
import "../css/app.css";

import Alpine from "alpinejs";
import htmx from "htmx.org";

window.htmx = htmx;
window.Alpine = Alpine;

Alpine.start();
