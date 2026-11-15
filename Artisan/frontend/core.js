// Shared state and helpers used by every page.
const App = {
  state: { lang: readLang(), regions: [], places: [], years: [1981, 2025] },
  pages: {},        // filled by page-*.js: { init(), show(params), refresh() }
  current: null,
};
const $ = (id) => document.getElementById(id);
// one palette for charts, map and 3D scene (dark "observatory" theme)
// one palette for charts, map and 3D scene: white line work + one red accent on black
const THEME = {
  data: "#ededed", warm: "#e5432f", cool: "#8fb8cc", alert: "#e5432f", muted: "#6b6b6b", ink: "#a8a8a8",
  grid: "#1c1c1c", band: "rgba(237,237,237,0.07)", warmBand: "rgba(229,67,47,0.20)",
  watermark: "rgba(237,237,237,0.08)", font: "'IBM Plex Mono', ui-monospace, monospace",
};
const COLORS = ["#ededed", "#e5432f", "#8fb8cc", "#c9a96e"];
// risk ramp: neutral grey -> red, so danger is what stands out
const LEVEL_COLORS = { low: "#5c6266", medium: "#a39a8c", high: "#e07a5f", very_high: "#e5432f" };
const HAZARDS = ["heat", "flood", "drought", "landslide"];
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function readLang() { try { return localStorage.getItem("artisan-lang") || "fr"; } catch { return "fr"; } }
function t(key, vars = {}) {
  const text = I18N[App.state.lang]?.[key] ?? key;
  return typeof text === "string" ? text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`) : text;
}
function fmt(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat(App.state.lang === "fr" ? "fr-FR" : "en-GB", { maximumFractionDigits: d }).format(v);
}
const signed = (v, d = 2) => (v > 0 ? "+" : "") + fmt(v, d);
const pct = (p) => (App.state.lang === "fr" ? `${fmt(p * 100, 0)} %` : `${fmt(p * 100, 0)}%`);
const fmtP = (p) => (p < 0.001 ? `p < ${fmt(0.001, 3)}` : `p = ${fmt(p, 3)}`);
// soil moisture (0-1 index) is shown as a percentage: 0.62 -> "62 %"
const unitLabel = (u) => (u === "days" ? t("u_days") : u === "0-1" ? "%" : u);
// full unit name for chart axes ("°C", "jours par an", "mm", "%")
const unitName = (u) => (u === "days" ? t("u_days_year") : u === "0-1" ? "%" : u);
// a 0-1 analysis (soil moisture) scaled to % for charts
function asPercent(a) {
  if (a.unit !== "0-1") return a;
  const k = (list) => list.map((v) => v * 100);
  const fc = a.forecast;
  return { ...a, series: { ...a.series, values: k(a.series.values) }, line: { ...a.line, trend: k(a.line.trend) },
    forecast: { ...fc, mean: k(fc.mean), lo80: k(fc.lo80), hi80: k(fc.hi80), lo95: k(fc.lo95), hi95: k(fc.hi95) },
    extreme: { ...a.extreme, threshold: a.extreme.threshold * 100 } };
}
const digits = (u) => (u === "0-1" ? 3 : u === "mm" || u === "days" ? 0 : 2);
const withUnit = (v, u) => (u === "0-1" ? `${fmt(v * 100, 0)} %` : `${fmt(v, digits(u))} ${unitLabel(u)}`);
// plain value with 1 decimal for temperatures, 0 for counts/rain: easy to read
const plain = (v, u) => (u === "0-1" ? `${fmt(v * 100, 0)} %` : `${fmt(v, u === "°C" || u === "C" ? 1 : 0)} ${unitLabel(u)}`);
const plainChange = (v, u) => (u === "0-1" ? `${signed(v * 100, 0)} pts` : `${signed(v, u === "°C" ? 1 : 0)} ${unitLabel(u)}`);
// "how sure is it?" in plain words, from the confidence label + the since-2000 check
function sureText(confidence, robustness) {
  // a trend that disappears after 2000 is not called "sure": it may come from the 1998 data jump
  if (robustness === "not_robust" && (confidence === "likely" || confidence === "very_likely")) {
    const check = t("sure_check");
    return check.charAt(0).toUpperCase() + check.slice(1);
  }
  return t(`sure_${confidence}`);
}
const sureClass = (confidence, robustness) =>
  robustness === "not_robust" ? "warn" : confidence === "very_likely" || confidence === "likely" ? "yes" : "no";
const mean = (list) => list.reduce((s, v) => s + v, 0) / list.length;
const regionById = (id) => App.state.regions.find((r) => r.id === id);
const regionName = (r) => (App.state.lang === "fr" ? r.name_fr : r.name_en);

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") n.className = v; else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return n;
}
function svgEl(tag, attrs) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}
async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
  }
  return res.json();
}
const loadingEl = (text = t("loading")) => el("p", { class: "loading", role: "status" }, text);
const errorEl = (e) => el("p", { class: "error", role: "alert" }, `${t("error")}: ${e.message}`);

// segmented control: options = [[value, label], ...]
function seg(container, options, current, onPick) {
  const buttons = options.map(([value, label]) => {
    const button = el("button", { type: "button", "aria-pressed": String(value === current) }, label);
    button.addEventListener("click", () => {
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      onPick(value);
    });
    return button;
  });
  container.replaceChildren(...buttons);
  container.setAttribute("role", "group");  // the label comes from the field caption or data-label
  const caption = container.previousElementSibling;
  if (caption && caption.tagName === "SPAN") container.setAttribute("aria-label", caption.textContent);
}

// text alternative for a chart (screen readers cannot read Plotly drawings)
function describeChart(id, text) {
  const node = $(id);
  node.setAttribute("role", "img");
  node.setAttribute("aria-label", text);
}

function fillYears(select, value) {
  select.setAttribute("aria-label", t(select.id.endsWith("start") ? "from" : "to"));
  const years = [];
  for (let y = App.state.years[0]; y <= App.state.years[1]; y++) years.push(y);
  select.replaceChildren(...years.map((y) => el("option", { value: y }, y)));
  select.value = value;
}

function fillRegions(select, value) {
  select.replaceChildren(...App.state.regions.map((r) => el("option", { value: r.id }, `${regionName(r)} · ${r.capital}`)));
  select.value = value;
}

function placeLabel(p) {
  if (p.foreign) return `${p.name} — ${App.state.lang === "fr" ? p.country_fr : p.country_en}`;
  return `${p.name} (${regionName(regionById(p.region))})`;
}
function fillPlaces(select, value, { withCountries = false } = {}) {
  const groups = [[t("capitals"), App.state.places.filter((p) => p.capital)],
    [t("towns"), App.state.places.filter((p) => !p.capital && !p.foreign).sort((a, b) => a.name.localeCompare(b.name))]];
  if (withCountries) groups.push([t("countries"), App.state.places.filter((p) => p.foreign)]);
  select.replaceChildren(...groups.map(([label, list]) => el("optgroup", { label }, list.map((p) => el("option", { value: p.id }, placeLabel(p))))));
  select.value = value;
}

const PLOT_CONFIG = { displayModeBar: false, responsive: true };
function plotLayout(extra = {}) {
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: THEME.font, size: 11, color: THEME.ink },
    hoverlabel: { bgcolor: "#000", bordercolor: "#3a3a3a", font: { family: THEME.font, color: "#ededed", size: 11 } },
    margin: { l: 52, r: 14, t: 16, b: 40 }, hovermode: "x unified",
    xaxis: { tickformat: "d", fixedrange: true, gridcolor: THEME.grid, zeroline: false, linecolor: THEME.grid },
    yaxis: { fixedrange: true, gridcolor: THEME.grid, zeroline: false },
    legend: { orientation: "h", y: -0.18 },
    ...extra,
  };
}

// small, safe markdown (headings, bold, lists, | tables |) — everything is escaped first
function renderMarkdown(text) {
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const blocks = [];
  for (const line of text.split(/\r?\n/)) {
    const isTable = line.trim().startsWith("|");
    const last = blocks.at(-1);
    if (last && last.isTable === isTable) last.lines.push(line); else blocks.push({ isTable, lines: [line] });
  }
  return blocks.map(({ isTable, lines }) => {
    if (isTable && lines.length >= 2) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const [head, , ...body] = lines;
      return `<div class="table-wrap"><table><thead><tr>${cells(head).map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${body.map((l) => `<tr>${cells(l).map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    let html = "", list = false;
    for (const raw of lines) {
      const item = raw.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (item) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(item[1])}</li>`; continue; }
      if (list) { html += "</ul>"; list = false; }
      const h = raw.match(/^#{1,4}\s+(.*)$/);
      if (h) html += `<h3>${inline(h[1])}</h3>`; else if (raw.trim() && raw.trim() !== "---") html += `<p>${inline(raw)}</p>`;
    }
    return html + (list ? "</ul>" : "");
  }).join("");
}

function sparkline(ev) {
  const w = 300, h = 50, pad = 4, v = ev.values, y = ev.years;
  const lo = Math.min(...v), hi = Math.max(...v);
  const X = (yr) => pad + ((yr - y[0]) / (y.at(-1) - y[0])) * (w - 2 * pad);
  const Y = (val) => h - pad - ((val - lo) / (hi - lo || 1)) * (h - 2 * pad);
  const svg = svgEl("svg", { class: "spark", viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: "none", "aria-hidden": "true" });
  svg.append(svgEl("polyline", { points: v.map((val, i) => `${X(y[i])},${Y(val)}`).join(" ") }));
  svg.append(svgEl("polyline", { class: "trend", points: ev.line.years.map((yr, i) => `${X(yr)},${Y(ev.line.trend[i])}`).join(" ") }));
  if (ev.change_year) svg.append(svgEl("line", { class: "mark", x1: X(ev.change_year), x2: X(ev.change_year), y1: 0, y2: h }));
  return svg;
}

// small screens show each table row as a block: every cell needs the name of its column
function labelCells(root) {
  root.querySelectorAll("table").forEach((table) => {
    const heads = [...table.querySelectorAll("thead th")].map((th) => th.textContent.trim());
    table.querySelectorAll("tbody tr").forEach((tr) => {
      [...tr.children].forEach((td, i) => { if (heads[i]) td.dataset.label = heads[i]; });
    });
  });
}

// Plotly measures its box when it draws; if the grid settles afterwards the chart can stay too wide.
// Re-measure once the layout is final (and on every window resize, through Plotly's responsive flag).
function fitCharts(root) {
  requestAnimationFrame(() => root.querySelectorAll(".js-plotly-plot").forEach((plot) => Plotly.Plots.resize(plot)));
}

// ---- links that keep the page state: #/synthese?place=...&start=... (no reload, no extra Back step)
function setLink(path, params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
  const hash = `#/${path}${query ? `?${query}` : ""}`;
  if (location.hash !== hash) history.replaceState(null, "", hash);
}
const yearParam = (value, fallback) => {
  const y = Number(value);
  return Number.isInteger(y) && y >= App.state.years[0] && y <= App.state.years[1] ? y : fallback;
};

// ---- the data behind a view, as a CSV file built in the browser (opens in Excel, LibreOffice, Python)
function downloadCSV(filename, rows) {
  const cell = (v) => {
    if (v === null || v === undefined || Number.isNaN(v)) return "";
    const text = typeof v === "number" ? String(Math.round(v * 10000) / 10000) : String(v);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = "\ufeff" + rows.map((row) => row.map(cell).join(",")).join("\r\n");  // BOM: accents survive in Excel
  const link = el("a", { href: URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })), download: filename });
  document.body.append(link);
  link.click();
  setTimeout(() => { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
}
const fileSlug = (text) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// unit written in CSV headers: soil moisture stays a 0-1 index (the raw NASA value), days follow the language
const csvUnit = (u) => (u === "0-1" ? "0-1" : unitName(u));

// ---- "copy link" with visible confirmation
async function copyLink(button) {
  const label = button.textContent;
  try { await navigator.clipboard.writeText(location.href); button.textContent = t("link_copied"); }
  catch { window.prompt(t("copy_link"), location.href); }
  setTimeout(() => { button.textContent = label; }, 1800);
}
