// Contador de leituras (docs/20). Uma leitura é enviada ao servidor quando a pessoa ficou
// ao menos `reads.min_seconds` com a aba visível E rolou 25% do corpo (ou o corpo cabe na
// tela). O servidor conta no máximo uma por pessoa, por publicação, por dia.
//
// Marcação (publications/detail.html):
//   <div data-read-beacon data-url="/x/articles/1/read/" data-min-seconds="15" hidden>
//     <input name="csrfmiddlewaretoken" ...>
//   </div>
//   <div data-article-body>...</div>

const SCROLL_FRACTION = 0.25;

function bodyScrolledEnough(body) {
  const rect = body.getBoundingClientRect();
  const viewport = window.innerHeight || document.documentElement.clientHeight;
  if (rect.height <= viewport) return true; // o corpo inteiro cabe na tela
  const seen = viewport - rect.top; // quanto do corpo já passou pela parte de baixo da tela
  return seen / rect.height >= SCROLL_FRACTION;
}

function send(url, token) {
  const data = new FormData();
  data.append("csrfmiddlewaretoken", token);
  // sendBeacon não aceita cabeçalhos: o token do CSRF vai no corpo.
  if (typeof navigator.sendBeacon === "function" && navigator.sendBeacon(url, data)) return;
  fetch(url, { method: "POST", body: data, credentials: "same-origin", keepalive: true }).catch(
    () => {},
  );
}

export function startReadBeacon() {
  const beacon = document.querySelector("[data-read-beacon]");
  const body = document.querySelector("[data-article-body]");
  if (!beacon || !body) return;

  const url = beacon.dataset.url;
  const token = beacon.querySelector("input[name=csrfmiddlewaretoken]")?.value || "";
  const minMs = Math.max(Number(beacon.dataset.minSeconds) || 15, 1) * 1000;

  let visibleMs = 0; // tempo com a aba visível já somado
  let visibleSince = document.visibilityState === "visible" ? performance.now() : null;
  let scrolled = false;
  let done = false;
  let timer = null;
  let frame = null;

  const elapsed = () => visibleMs + (visibleSince === null ? 0 : performance.now() - visibleSince);

  function stop() {
    done = true;
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", onScroll);
  }

  function check() {
    if (done) return;
    scrolled = scrolled || bodyScrolledEnough(body);
    if (!scrolled || elapsed() < minMs) return;
    stop();
    send(url, token);
  }

  function schedule() {
    clearTimeout(timer);
    if (visibleSince === null) return;
    timer = setTimeout(check, Math.max(minMs - elapsed(), 0) + 50);
  }

  function onVisibility() {
    if (document.visibilityState === "visible") {
      if (visibleSince === null) visibleSince = performance.now();
      schedule();
    } else if (visibleSince !== null) {
      visibleMs += performance.now() - visibleSince;
      visibleSince = null;
      clearTimeout(timer);
    }
  }

  function onScroll() {
    if (scrolled || frame !== null) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      scrolled = bodyScrolledEnough(body);
      if (scrolled) check();
    });
  }

  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  scrolled = bodyScrolledEnough(body);
  schedule();
}
