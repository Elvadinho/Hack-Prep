// HOME: 3D risk terrain of Cameroon + 3 key numbers + most exposed regions.
App.pages.home = {
  hazard: "heat", rows: null, terrain: null, discoveries: null,

  init() {
    this.terrain = Terrain3D.create($("scene"), $("scene-labels"), {
      onHover: (id, event) => this.onHover(id, event),
      onPick: (id) => { location.hash = `#/synthese?place=${id}`; },
    });
    if (!this.terrain) $("scene").append(el("p", { class: "scene-fallback" }, t("scene_off")));
    $("town-search").addEventListener("submit", (e) => { e.preventDefault(); this.findTown(); });
    $("town-input").addEventListener("input", () => { $("town-error").hidden = true; });
    api("/api/discoveries").then((d) => { this.discoveries = d; this.renderKeys(); }).catch(() => {});
    api("/api/validation").then((v) => { this.validation = v; this.renderStatus(); }).catch(() => {});
  },

  show(params = {}) {
    if (HAZARDS.includes(params.hazard)) this.hazard = params.hazard;
    this.renderControls(); this.load();
  },

  // town search: any place of the app (capitals, towns, neighbouring capitals), with or without accents
  renderSearch() {
    $("town-input").placeholder = t("search_ph");
    $("town-list").replaceChildren(...App.state.places.map((p) => el("option", { value: placeLabel(p) })));
  },
  findTown() {
    const norm = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
    const query = norm($("town-input").value);
    const places = App.state.places;
    const hit = query && (places.find((p) => norm(placeLabel(p)) === query) || places.find((p) => norm(p.name) === query)
      || places.find((p) => norm(p.name).startsWith(query)) || places.find((p) => norm(placeLabel(p)).includes(query)));
    if (!hit) { $("town-error").textContent = t("search_none"); $("town-error").hidden = false; return; }
    location.hash = `#/synthese?place=${hit.id}&view=simple`;
  },
  refresh() { this.renderControls(); this.draw(); this.renderKeys(); this.renderTop(); if (this.rows) this.describe(); },

  renderControls() {
    this.renderSearch();
    seg($("home-hazard"), HAZARDS.map((h) => [h, t(`hazard_${h}`)]), this.hazard, (h) => { this.hazard = h; this.load(); });
    $("home-hazard").setAttribute("aria-label", t("hazard"));
    // vertical scale of the column heights: 100 at the top, 0 at the bottom
    const bands = [["very_high", "75–100"], ["high", "50–74"], ["medium", "25–49"], ["low", "0–24"]];
    $("legend").replaceChildren(el("p", { class: "risk-scale-title" }, t("scale_title")),
      ...bands.map(([level, range]) => {
        const bar = el("i"); bar.style.background = LEVEL_COLORS[level];
        return el("div", { class: "risk-band" }, bar, el("span", {}, t(`level_${level}`)), el("small", {}, range));
      }));
    // the years behind every number on the page, and the forecast horizon in red
    const years = [1981, 1990, 2000, 2010, 2020, 2025];
    $("timeline").replaceChildren(...years.map((y) => el("span", {}, y)), el("span", { class: "future" }, "→ 2030"));
    this.renderStatus();
  },

  renderStatus() {
    const checks = this.validation ? `${this.validation.summary.pass}/${this.validation.checks.length}` : "…";
    $("hero-status").replaceChildren(
      ...[[t("st_source"), "NASA POWER / MERRA-2"], [t("st_points"), "10"], [t("st_days"), "16 436"], [t("st_checks"), checks]]
        .map(([k, v]) => el("span", {}, `${k} `, el("b", {}, v))));
  },

  async load() {
    setLink("", { hazard: this.hazard === "heat" ? "" : this.hazard });
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

  // ---- 3D terrain: heights and colours from the scores of the selected hazard
  draw() {
    if (!this.terrain || !this.rows) return;
    this.terrain.update(Object.fromEntries(this.rows.map((r) => [r.region.id,
      { score: r.risk_score, level: r.risk_level, name: regionName(r.region) }])));
  },

  onHover(id, event) {
    const tip = $("map-tip");
    if (!id || !event) { tip.hidden = true; return; }
    const row = (this.rows || []).find((r) => r.region.id === id), region = regionById(id);
    const rect = $("scene").getBoundingClientRect();
    tip.replaceChildren(`${regionName(region)} · ${t(`hazard_${this.hazard}`)}`, el("b", {}, row ? `${row.risk_score}/100` : "…"));
    tip.style.transform = `translate(${event.clientX - rect.left + 16}px, ${event.clientY - rect.top + 16}px)`;
    tip.hidden = false;
  },
};
