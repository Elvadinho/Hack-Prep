// COMPARE: same NASA indicator for 2-3 places (towns or neighbouring countries), animated year by year.
App.pages.compare = {
  places: ["centre", "country_chad", "country_nigeria"],
  variable: "T2M", start: 1981, end: 2025, data: null, playing: false, frames: [],

  init() {
    $("cmp-start").addEventListener("change", (e) => { this.start = Number(e.target.value); this.load(); });
    $("cmp-end").addEventListener("change", (e) => { this.end = Number(e.target.value); this.load(); });
    $("cmp-play").addEventListener("click", () => (this.playing ? this.pause() : this.play()));
  },

  show() { this.renderControls(); this.load(); },
  refresh() { this.show(); },

  renderControls() {
    const picks = this.places.map((id, i) => {
      const select = el("select", { "aria-label": t("cmp_place", { n: i + 1 }) });
      fillPlaces(select, id, { withCountries: true });
      select.addEventListener("change", (e) => { this.places[i] = e.target.value; this.load(); });
      const dot = el("i"); dot.style.background = COLORS[i];
      const remove = this.places.length > 2
        ? el("button", { type: "button", class: "icon-btn", title: t("cmp_remove"), "aria-label": t("cmp_remove"),
            onclick: () => { this.places.splice(i, 1); this.renderControls(); this.load(); } }, "×")
        : null;
      return el("label", { class: "place-pick" }, t("cmp_place", { n: i + 1 }), el("span", { class: "row" }, dot, select, remove));
    });
    if (this.places.length < 3) {
      picks.push(el("button", { type: "button", class: "btn btn-ghost", onclick: () => {
        const next = App.state.places.find((p) => !this.places.includes(p.id) && p.foreign) || App.state.places[0];
        this.places.push(next.id); this.renderControls(); this.load();
      } }, t("cmp_add")));
    }
    $("cmp-places").replaceChildren(...picks);
    fillYears($("cmp-start"), this.start);
    fillYears($("cmp-end"), this.end);
    const variables = ["T2M", "TXX", "TNN", "RAIN", "HOT", "SOIL"];
    seg($("cmp-variable"), variables.map((v) => [v, t(`v_${v}`)]), this.variable, (v) => { this.variable = v; this.load(); });
    $("cmp-variable").setAttribute("aria-label", t("indicator"));
  },

  async load() {
    if (this.end - this.start < 9) { $("cmp-cards").replaceChildren(errorEl(new Error(t("years_min")))); return; }
    $("cmp-cards").replaceChildren(loadingEl());
    try {
      const q = `places=${this.places.join(",")}&variable=${this.variable}&start=${this.start}&end=${this.end}&lang=${App.state.lang}`;
      this.data = await api(`/api/compare?${q}`);
      this.drawChart();
      this.renderCards();
    } catch (e) { $("cmp-cards").replaceChildren(errorEl(e)); }
  },

  async drawChart() {
    const d = this.data, unit = d.unit, n = d.places.length;
    $("cmp-chart-title").textContent = `${d.label}${unit === "0-1" ? "" : ` (${unitLabel(unit)})`} · ${this.start}–${this.end}`;
    const years = d.places[0].series.years;
    const all = d.places.flatMap((p) => p.series.values);
    const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * 0.08 || 1;

    // easy reading: faint dots = each year; thick line = 5-year average (shows the direction without the noise)
    const smooth = (values) => values.map((_, i) => mean(values.slice(Math.max(0, i - 2), Math.min(values.length, i + 3))));
    const smoothed = d.places.map((p) => smooth(p.series.values));
    const observed = (k) => d.places.map((p, i) => ({
      x: p.series.years.slice(0, k + 1), y: p.series.values.slice(0, k + 1),
      mode: "markers", marker: { size: 5, color: COLORS[i], opacity: 0.35 }, showlegend: false,
      hovertemplate: `${p.place.name}: %{y:.1f}<extra></extra>`,
    }));
    const trends = (k) => d.places.map((p, i) => ({
      x: p.series.years.slice(0, k + 1), y: smoothed[i].slice(0, k + 1),
      mode: "lines", name: p.place.label, line: { color: COLORS[i], width: 4, shape: "spline" }, hoverinfo: "skip",
    }));
    const yearLabel = (yr) => [{ xref: "paper", yref: "paper", x: 0.01, y: 0.98, xanchor: "left", yanchor: "top", showarrow: false,
      text: `<b>${yr}</b>`, font: { size: 28, color: "rgba(21,60,55,0.22)" } }];

    const last = years.length - 1;
    const layout = plotLayout({
      xaxis: { tickformat: "d", fixedrange: true, gridcolor: "#eef3ef", range: [years[0] - 0.5, years[last] + 0.5] },
      yaxis: { fixedrange: true, gridcolor: "#e3eae5", range: [lo - pad, hi + pad], title: { text: unit === "0-1" ? "" : unitLabel(unit) } },
      annotations: yearLabel(REDUCED_MOTION ? `${years[0]}–${years[last]}` : years[0]),
    });
    describeChart("cmp-chart", `${d.label}, ${years[0]}–${years[last]}: ` + d.places.map((p) =>
      `${p.place.label} ${withUnit(p.first_mean, unit)} → ${withUnit(p.last_mean, unit)}, ${signed(p.trend.slope_per_decade, 2)}/10 (${fmtP(p.trend.p_value)})`).join("; "));
    const startK = REDUCED_MOTION ? last : 0;
    await Plotly.newPlot("cmp-chart", [...observed(startK), ...trends(startK)], layout, PLOT_CONFIG);

    this.frames = years.map((yr, k) => ({
      name: String(yr),
      data: [...observed(k), ...trends(k)],
      traces: [...Array(2 * n).keys()],
      layout: { annotations: yearLabel(k === last ? `${years[0]}–${yr}` : yr) },
    }));
    await Plotly.addFrames("cmp-chart", this.frames);
    if (!REDUCED_MOTION) this.play(); else this.setButton(false);
  },

  play() {
    this.setButton(true);
    Plotly.animate("cmp-chart", this.frames.map((f) => f.name), {
      frame: { duration: 70, redraw: false }, transition: { duration: 50, easing: "linear" }, mode: "immediate",
    }).then(() => this.setButton(false));
  },
  pause() {
    Plotly.animate("cmp-chart", [null], { mode: "immediate", frame: { duration: 0, redraw: false }, transition: { duration: 0 } });
    this.setButton(false);
  },
  setButton(playing) {
    this.playing = playing;
    $("cmp-play").textContent = playing ? t("cmp_pause") : t("cmp_play");
  },

  renderCards() {
    const d = this.data, u = d.unit;
    $("cmp-cards").replaceChildren(...d.places.map((p, i) => {
      const tr = p.trend;
      const card = el("article", { class: "cmp-card" },
        el("h3", {}, p.place.label),
        el("div", { class: "big-change" }, plain(p.first_mean, u), el("span", { class: "arrow", "aria-hidden": "true" }, "→"), plain(p.last_mean, u)),
        el("p", { class: "note-small" }, `${p.first_period[0]}–${p.first_period[1]} → ${p.last_period[0]}–${p.last_period[1]}`),
        el("dl", {},
          el("dt", {}, t("cmp_change")), el("dd", { class: tr.significant ? (p.change > 0 ? "pos" : "neg") : "" }, plainChange(p.change, u)),
          el("dt", {}, t("col_sure")), el("dd", { class: sureClass(tr.confidence, p.robustness.status) }, sureText(tr.confidence, p.robustness.status)),
          el("dt", {}, t("cmp_record")), el("dd", {}, `${plain(p.max, u)} (${p.max_year})`)));
      card.style.borderTopColor = COLORS[i];
      return card;
    }));
  },
};
