// HOME: risk map of Cameroon + 3 key numbers + most exposed regions.
App.pages.home = {
  hazard: "heat", rows: null, raster: null, hover: null, discoveries: null,

  init() {
    this.raster = CMR.raster(0.04);
    const canvas = $("map");
    canvas.addEventListener("mousemove", (e) => this.onHover(e));
    canvas.addEventListener("mouseleave", () => { this.hover = null; $("map-tip").hidden = true; this.draw(); });
    canvas.addEventListener("click", (e) => { const id = this.regionAt(e); if (id) location.hash = `#/synthese?place=${id}`; });
    window.addEventListener("resize", () => { if (App.current === "home") this.draw(); });
    api("/api/discoveries").then((d) => { this.discoveries = d; this.renderKeys(); }).catch(() => {});
  },

  show() { this.renderControls(); this.load(); },
  refresh() { this.renderControls(); this.draw(); this.renderKeys(); this.renderTop(); },

  renderControls() {
    seg($("home-hazard"), HAZARDS.map((h) => [h, t(`hazard_${h}`)]), this.hazard, (h) => { this.hazard = h; this.load(); });
    $("home-hazard").setAttribute("aria-label", t("hazard"));
    $("legend").replaceChildren(...Object.entries(LEVEL_COLORS).map(([level, color]) => {
      const swatch = el("i"); swatch.style.background = color;
      return el("span", {}, swatch, t(`level_${level}`));
    }));
  },

  async load() {
    $("home-keys").replaceChildren(loadingEl());
    try {
      this.rows = await api(`/api/table?metric=${this.hazard}&horizon=3`);
      this.draw(); this.renderKeys(); this.renderTop(); this.describe();
    } catch (e) { $("home-keys").replaceChildren(errorEl(e)); }
  },

  renderKeys() {
    if (!this.rows) return;
    const atRisk = this.rows.filter((r) => ["high", "very_high"].includes(r.risk_level)).length;
    const worsening = this.rows.filter((r) => r.significant && r.robustness !== "not_robust").length;
    const keys = [
      [`${atRisk}/10`, t("home_k1")],
      [`${worsening}/10`, t("home_k3")],
      [this.discoveries ? this.discoveries.significant_after_fdr : "…", t("home_k2")],
    ];
    $("home-keys").replaceChildren(...keys.map(([n, label]) => el("div", { class: "key" }, el("strong", {}, n), el("span", {}, label))));
  },

  // the map is a picture: give screen readers every region's score as text
  describe() {
    const list = [...this.rows].sort((a, b) => b.risk_score - a.risk_score)
      .map((r) => `${regionName(r.region)} ${r.risk_score}/100 (${t(`level_${r.risk_level}`)})`).join(", ");
    $("map-desc").textContent = t("map_alt", { hazard: t(`hazard_${this.hazard}`), list });
  },

  renderTop() {
    if (!this.rows) return;
    const top = [...this.rows].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5);
    $("home-top").replaceChildren(...top.map((r) => {
      const bar = el("i"); bar.style.width = `${r.risk_score}%`; bar.style.background = LEVEL_COLORS[r.risk_level];
      const level = el("span", { class: `level ${r.risk_level}` }, t(`level_${r.risk_level}`));
      level.style.background = LEVEL_COLORS[r.risk_level];
      // the evidence in plain words: average of the first 5 years -> last 5 years
      const line = t("rank_line", { indicator: this.indicatorLabel(), before: `${plain(r.before.mean, r.unit)} (${r.before.years[0]}-${String(r.before.years[1]).slice(2)})`,
        now: `${plain(r.now.mean, r.unit)} (${r.now.years[0]}-${String(r.now.years[1]).slice(2)})` });
      const parts = r.risk_parts;
      return el("li", {}, el("a", { href: `#/synthese?place=${r.region.id}` },
        el("strong", {}, `${regionName(r.region)} · ${r.region.capital}`), level,
        el("span", { class: "line" }, line),
        el("span", { class: "bar", title: `${r.risk_score}/100` }, bar),
        parts ? el("span", { class: "parts" }, t("score_parts", { score: r.risk_score, a: fmt(parts.trend_points, 0), b: fmt(parts.recent_points, 0) })) : null));
    }));
    this.renderHow(top[0]);
  },

  // "How is this score calculated?": the 2 questions, a worked example with real numbers, the exact formula
  renderHow(r) {
    const body = $("home-how-body");
    if (!r?.risk_parts) { body.replaceChildren(); return; }
    const p = r.risk_parts, e = p.explain, u = r.unit;
    const years = `${p.recent_years[0]}–${p.recent_years.at(-1)}`;
    const why = e.evidence_weight === 0 ? t("how_ex_noproof")
      : t("how_ex_weights", { ev: fmt(e.evidence_weight, 2), chk: fmt(e.check_weight, 2), rob: t(`how_rob_${e.robustness}`) });
    body.replaceChildren(
      el("p", {}, t("how_intro")),
      el("ol", { class: "how-steps" },
        el("li", {}, el("b", {}, t("how_a_title")), " ", t("how_a_text")),
        el("li", {}, el("b", {}, t("how_b_title")), " ", t("how_b_text"))),
      el("div", { class: "how-example" },
        el("b", {}, t("how_ex_title", { region: regionName(r.region), hazard: t(`hazard_${this.hazard}`) })),
        el("p", {}, "A. ", t("how_ex_a", { change: plainChange(e.change, u), swing: plain(e.normal_swing, u), n: fmt(e.change_in_swings, 1), p: fmtP(e.p_value) }), " ", why,
          " → ", el("b", {}, `${fmt(p.trend_points, 1)} / 50`)),
        el("p", {}, "B. ", t("how_ex_b", { years, now: plain(p.recent_anomaly.value, u), normal: plain(p.recent_anomaly.baseline_mean, u), n: fmt(e.recent_in_swings, 1) }),
          " → ", el("b", {}, `${fmt(p.recent_points, 1)} / 50`)),
        el("p", {}, el("b", {}, t("how_ex_total", { a: fmt(p.trend_points, 1), b: fmt(p.recent_points, 1), score: r.risk_score, level: t(`level_${r.risk_level}`) })))),
      el("details", { class: "stats" }, el("summary", {}, t("how_tech_title")),
        el("p", { class: "formula" }, t("how_tech_a")),
        el("p", { class: "formula" }, t("how_tech_b")),
        el("p", {}, t("how_tech_levels")),
        el("p", {}, t("how_tech_limits"))));
  },

  indicatorLabel() {
    const labels = {
      fr: { heat: "Jours de forte chaleur par an", flood: "Jours de pluie très forte par an", drought: "Humidité du sol", landslide: "Pluie max. sur 3 jours" },
      en: { heat: "Very hot days per year", flood: "Very heavy rain days per year", drought: "Soil moisture", landslide: "Max 3-day rainfall" },
    };
    return labels[App.state.lang][this.hazard];
  },

  // ---- canvas map
  draw() {
    const R = this.raster;
    if (!R || App.current !== "home") return;
    const canvas = $("map"), box = canvas.parentElement;
    const { lonMin, lonMax, latMin, latMax } = CMR.bounds;
    // fit the map in the screen: limit its height, keep the real proportions
    const ratio = (latMax - latMin) / (lonMax - lonMin);
    const maxH = Math.max(360, Math.min(600, window.innerHeight - 260));
    const W = Math.min(box.clientWidth, maxH / ratio), H = W * ratio;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.height = `${H}px`; canvas.style.width = `${W}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const sx = W / (lonMax - lonMin), sy = H / (latMax - latMin);
    const X = (lon) => (lon - lonMin) * sx, Y = (lat) => (latMax - lat) * sy;
    const cw = R.step * sx, ch = R.step * sy;
    const rows = Object.fromEntries((this.rows || []).map((r) => [r.region.id, r]));
    const colors = R.ids.map((id) => (rows[id] ? LEVEL_COLORS[rows[id].risk_level] : "#dfe7e2"));
    const hoverK = R.ids.indexOf(this.hover);

    ctx.fillStyle = "#f8fbf8"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#5d6f68"; ctx.textAlign = "center";
    for (const n of CMR.neighbours) {
      ctx.font = `${n.italic ? "italic " : ""}600 ${Math.max(9, W / 64)}px Inter, sans-serif`;
      ctx.fillText(n[App.state.lang], X(n.lon), Y(n.lat));
    }
    for (let r = 0; r < R.rows; r++) for (let c = 0; c < R.cols; c++) {
      const k = R.grid[r * R.cols + c];
      if (k < 0) continue;
      ctx.fillStyle = k === hoverK ? shade(colors[k]) : colors[k];
      ctx.fillRect(c * cw, r * ch, cw + 0.7, ch + 0.7);
    }
    ctx.beginPath();  // white borders between regions
    for (let r = 0; r < R.rows; r++) for (let c = 0; c < R.cols; c++) {
      const k = R.grid[r * R.cols + c];
      if (k < 0) continue;
      const right = c + 1 < R.cols ? R.grid[r * R.cols + c + 1] : -1;
      const down = r + 1 < R.rows ? R.grid[(r + 1) * R.cols + c] : -1;
      if (right >= 0 && right !== k) { ctx.moveTo((c + 1) * cw, r * ch); ctx.lineTo((c + 1) * cw, (r + 1) * ch); }
      if (down >= 0 && down !== k) { ctx.moveTo(c * cw, (r + 1) * ch); ctx.lineTo((c + 1) * cw, (r + 1) * ch); }
    }
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath();
    CMR.outline.forEach(([lon, lat], i) => (i ? ctx.lineTo(X(lon), Y(lat)) : ctx.moveTo(X(lon), Y(lat))));
    ctx.closePath(); ctx.strokeStyle = "#153c37"; ctx.lineWidth = 1.5; ctx.stroke();

    const size = Math.max(10, W / 50);
    for (const id of R.ids) {
      const [lat, lon] = CMR.seeds[id][0];
      ctx.beginPath(); ctx.arc(X(lon), Y(lat), 3, 0, Math.PI * 2);
      ctx.fillStyle = "#fff"; ctx.fill(); ctx.strokeStyle = "#153c37"; ctx.lineWidth = 1.4; ctx.stroke();
      const p = R.labels[id], region = regionById(id);
      ctx.textAlign = "center"; ctx.lineJoin = "round"; ctx.lineWidth = 3.5; ctx.strokeStyle = "rgba(255,255,255,.92)"; ctx.fillStyle = "#153c37";
      ctx.font = `700 ${size}px Inter, sans-serif`;
      const name = region ? regionName(region) : id;
      ctx.strokeText(name, X(p.lon), Y(p.lat)); ctx.fillText(name, X(p.lon), Y(p.lat));
      if (rows[id]) {
        ctx.font = `600 ${size * 0.9}px Inter, sans-serif`;
        const score = String(rows[id].risk_score);
        ctx.strokeText(score, X(p.lon), Y(p.lat) + size * 1.1); ctx.fillText(score, X(p.lon), Y(p.lat) + size * 1.1);
      }
    }
  },

  regionAt(event) {
    const R = this.raster, rect = $("map").getBoundingClientRect();
    const { lonMin, lonMax, latMin, latMax } = CMR.bounds;
    const lon = lonMin + ((event.clientX - rect.left) / rect.width) * (lonMax - lonMin);
    const lat = latMax - ((event.clientY - rect.top) / rect.height) * (latMax - latMin);
    const c = Math.floor((lon - lonMin) / R.step), r = Math.floor((latMax - lat) / R.step);
    if (c < 0 || r < 0 || c >= R.cols || r >= R.rows) return null;
    const k = R.grid[r * R.cols + c];
    return k >= 0 ? R.ids[k] : null;
  },

  onHover(e) {
    const id = this.regionAt(e), tip = $("map-tip");
    if (id !== this.hover) { this.hover = id; this.draw(); }
    if (!id) { tip.hidden = true; return; }
    const row = (this.rows || []).find((r) => r.region.id === id), region = regionById(id);
    const rect = $("map").getBoundingClientRect();
    tip.replaceChildren(`${regionName(region)} · ${t(`hazard_${this.hazard}`)}`, el("b", {}, row ? `${row.risk_score}/100` : "…"));
    tip.style.left = `${e.clientX - rect.left}px`; tip.style.top = `${e.clientY - rect.top}px`; tip.hidden = false;
  },
};

function shade(hex) {  // lighten a colour for hover
  const [r, g, b] = hex.match(/\w\w/g).map((h) => parseInt(h, 16));
  return `rgb(${Math.round(r + (255 - r) * 0.3)},${Math.round(g + (255 - g) * 0.3)},${Math.round(b + (255 - b) * 0.3)})`;
}
