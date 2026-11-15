// Start-up and page router: #/ , #/synthese , #/comparer , #/previsions , #/decouvertes , #/fiabilite , #/assistant
const ROUTES = { "": "home", synthese: "report", comparer: "compare", previsions: "forecast", decouvertes: "discover", fiabilite: "validation", assistant: "ai" };

function applyStaticText() {
  document.documentElement.lang = App.state.lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  $("lang-toggle").textContent = App.state.lang === "fr" ? "EN" : "FR";
}

function route() {
  const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
  const name = ROUTES[path] ?? "home";
  const params = Object.fromEntries(new URLSearchParams(query || ""));
  document.querySelectorAll(".page").forEach((s) => { s.hidden = s.dataset.page !== name; });
  document.querySelector("main").classList.toggle("is-home", name === "home");
  document.querySelectorAll("[data-page-link]").forEach((a) => {
    if (a.dataset.pageLink === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  const page = App.pages[name];
  if (!page) return;
  if (!page.ready) { page.init(); page.ready = true; }
  App.current = name;
  page.show(params);
  window.scrollTo({ top: 0 });
  // tell keyboard and screen-reader users that the page changed
  const heading = document.querySelector(`.page[data-page="${name}"] h1`);
  if (heading) {
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
    document.title = `${heading.textContent} · ArtisanConnect`;
  }
}

async function start() {
  applyStaticText();
  const [regions, places] = await Promise.all([api("/api/regions"), api("/api/places")]);
  App.state.regions = regions;
  App.state.places = places;
  $("lang-toggle").addEventListener("click", () => {
    App.state.lang = App.state.lang === "fr" ? "en" : "fr";
    try { localStorage.setItem("artisan-lang", App.state.lang); } catch { /* private mode */ }
    applyStaticText();
    Object.values(App.pages).forEach((p) => { p.stale = true; });
    App.pages[App.current]?.refresh?.();
  });
  window.addEventListener("hashchange", route);
  route();
}

start().catch((e) => document.querySelector("main").prepend(errorEl(e)));
