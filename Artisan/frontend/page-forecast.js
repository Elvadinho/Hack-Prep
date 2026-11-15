// FORECASTS + ADVICE: next 1-10 years for one region and hazard, how reliable, and what to do.
// What can be forecast for each hazard: the physical quantity first (°C, mm, %), then the hazard count.
const FC_MEASURES = {
  heat: ["T2M_MAX", "heat"],       // average daily maximum temperature (°C) | days above the hot-day threshold
  flood: ["PRECTOTCORR", "flood"], // annual rainfall (mm) | very heavy rain days
  drought: ["drought"],            // root-zone soil moisture (%)
  landslide: ["landslide"],        // largest 3-day rainfall of the year (mm)
};

App.pages.forecast = {
  region: "centre", hazard: "heat", measure: "T2M_MAX", horizon: 3,

  init() {
    $("fc-region").addEventListener("change", (e) => { this.region = e.target.value; this.load(); });
    $("fc-csv").addEventListener("click", () => this.downloadData());
    $("fc-link").addEventListener("click", (e) => copyLink(e.currentTarget));
  },
  show(params) {
    if (params.region && regionById(params.region)) this.region = params.region;
    if (HAZARDS.includes(params.hazard)) { this.hazard = params.hazard; this.measure = FC_MEASURES[this.hazard][0]; }
    if (params.measure && FC_MEASURES[this.hazard].includes(params.measure)) this.measure = params.measure;
    if ([1, 2, 3, 5, 10].includes(Number(params.horizon))) this.horizon = Number(params.horizon);
    this.renderControls(); this.load();
  },
  refresh() { this.show({}); },

  renderControls() {
    fillRegions($("fc-region"), this.region);
    seg($("fc-hazard"), HAZARDS.map((h) => [h, t(`hazard_${h}`)]), this.hazard, (h) => {
      this.hazard = h; this.measure = FC_MEASURES[h][0]; this.renderMeasures(); this.load();
    });
    this.renderMeasures();
    seg($("fc-horizon"), [1, 2, 3, 5, 10].map((h) => [h, h === 1 ? t("year_1") : t("years_n", { n: h })]), this.horizon, (h) => { this.horizon = h; this.load(); });
  },

  renderMeasures() {
    const options = FC_MEASURES[this.hazard];
    $("fc-measure-field").hidden = options.length < 2;
    seg($("fc-measure"), options.map((m) => [m, t(`ms_${m}`)]), this.measure, (m) => { this.measure = m; this.load(); });
  },

  async load() {
    setLink("previsions", { region: this.region, hazard: this.hazard, measure: this.measure, horizon: this.horizon });
    $("fc-numbers").replaceChildren(loadingEl());
    try {
      const q = `region=${this.region}&metric=${this.measure}&horizon=${this.horizon}`;
      const [a, advice] = await Promise.all([
        api(`/api/explore?${q}`),
        api(`/api/advice?region=${this.region}&hazard=${this.hazard}&horizon=${this.horizon}&lang=${App.state.lang}`),
      ]);
      this.last = a;
      this.drawChart(a); this.renderNumbers(a); this.renderAdvice(advice);
      fitCharts(document.querySelector('[data-page="forecast"]'));
    } catch (e) { $("fc-numbers").replaceChildren(errorEl(e)); }
  },

  drawChart(raw) {
    const a = asPercent(raw);  // soil moisture is a 0-1 index on the server: shown in % like everywhere else
    const fc = a.forecast, last = a.range[1], lastVal = a.series.values.at(-1);
    const counts = ["days", "mm", "0-1"].includes(raw.unit);  // only these start at zero; temperatures do not
    const fx = [last, ...fc.years];
    const traces = [
      { x: fx, y: [lastVal, ...fc.hi80], mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
      { x: fx, y: [lastVal, ...fc.lo80], mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: THEME.warmBand, name: t("fc_band"), hoverinfo: "skip" },
      { x: a.series.years, y: a.series.values, mode: "lines+markers", name: t("fc_observed"), line: { color: THEME.data, width: 2 }, marker: { size: 4 } },
      { x: a.line.years, y: a.line.trend.map((v) => (counts ? Math.max(0, v) : v)), mode: "lines", name: t("fc_trend"), line: { color: THEME.data, width: 1.5, dash: "dot" } },
      { x: fx, y: [lastVal, ...fc.mean], mode: "lines+markers", name: t("fc_forecast"), line: { color: THEME.warm, width: 2.6, dash: "dash" }, marker: { size: 7, symbol: "diamond" } },
    ];
    const thr = a.extreme.threshold, k = fc.years.length - 1;
    $("fc-chart-title").textContent = `${t(`ms_${this.measure}`)} · ${unitName(raw.unit)}`;
    describeChart("fc-chart", `${t(`hazard_${this.hazard}`)}, ${regionName(regionById(this.region))}: ${a.range[0]}–${a.range[1]} ` +
      `${signed(a.trend.slope_per_decade, 2)}/10 (${fmtP(a.trend.p_value)}); ${t("fc_expected", { y: fc.years[k] })} ${withUnit(fc.mean[k], a.unit)}.`);
    Plotly.react("fc-chart", traces, plotLayout({
      yaxis: { fixedrange: true, gridcolor: THEME.grid, rangemode: counts ? "tozero" : "normal", title: { text: unitName(raw.unit) } },
      shapes: [
        { type: "line", xref: "paper", x0: 0, x1: 1, y0: thr, y1: thr, line: { color: THEME.alert, width: 1, dash: "dot" } },
      ],
      annotations: [
        { xref: "paper", x: 0, y: thr, xanchor: "left", yanchor: "bottom", text: t("fc_threshold"), showarrow: false, font: { size: 10, color: THEME.alert } },
      ],
    }), PLOT_CONFIG);
  },

  renderNumbers(a) {
    const fc = a.forecast, ex = a.extreme, bt = a.backtest, u = a.unit, k = fc.years.length - 1;
    const good = bt.skill !== null && bt.skill > 0 && bt.skill_persistence > 0;
    const change = fc.mean[k] - a.baseline_mean;
    $("fc-method").textContent = t("fc_method", { m: t(`fm_${fc.method}`),
      list: Object.entries(a.method_errors).map(([m, e]) => `${t(`fm_${m}`)} ${fmt(e, 2)}`).join(" · ") });
    const numbers = [
      [t("fc_expected", { y: fc.years[k] }), withUnit(fc.mean[k], u), t("fc_range", { lo: withUnit(fc.lo80[k], u), hi: withUnit(fc.hi80[k], u) }), ""],
      [t("fc_vs_normal", { y: fc.years[k] }), plainChange(change, u), ex.beyond_normal ? t("fc_beyond") : t("fc_vs_sub", { n: withUnit(a.baseline_mean, u) }), ex.beyond_normal ? "warn" : ""],
      [t("fc_skill"), bt.mae_model === null ? "—" : `± ${withUnit(bt.mae_model, u)}`,
        t("fc_rel", { c: withUnit(bt.mae_climatology, u), p: withUnit(bt.mae_persistence, u), n: bt.n_forecasts }), good ? "yes" : "warn"],
    ];
    $("fc-numbers").replaceChildren(...numbers.map(([label, value, sub, cls]) =>
      el("div", { class: "number" }, el("span", {}, label), el("strong", { class: cls }, value), el("small", {}, sub))));
  },

  // observed values, trend line and forecast with its likely ranges, year by year
  downloadData() {
    const a = this.last;
    if (!a) return;
    const fc = a.forecast, trend = Object.fromEntries(a.line.years.map((y, i) => [y, a.line.trend[i]]));
    const observed = Object.fromEntries(a.series.years.map((y, i) => [y, a.series.values[i]]));
    const future = Object.fromEntries(fc.years.map((y, i) => [y, i]));
    const years = [...a.series.years, ...fc.years];
    const rows = [
      ["# ArtisanConnect", a.source], ["# " + t("dl_measure"), `${t(`ms_${this.measure}`)} (${csvUnit(a.unit)})`], ["# " + t("c_method"), t(`fm_${fc.method}`)], [],
      [t("c_year"), t("fc_observed"), t("fc_trend"), t("fc_forecast"), t("dl_low80"), t("dl_high80"), t("dl_low95"), t("dl_high95")],
      ...years.map((y) => {
        const k = future[y], f = (list) => (k === undefined ? null : list[k]);
        return [y, observed[y], trend[y], f(fc.mean), f(fc.lo80), f(fc.hi80), f(fc.lo95), f(fc.hi95)];
      }),
    ];
    downloadCSV(`artisanconnect_${this.region}_${this.measure.toLowerCase()}_${fc.years.at(-1)}.csv`, rows);
  },

  renderAdvice(a) {
    $("fc-priority").textContent = a.priority_label;
    $("fc-priority").className = `priority ${a.priority}`;
    $("fc-timing").textContent = a.timing;
    $("fc-actions").replaceChildren(...a.actions.map((text) => el("li", {}, text)));
    $("fc-facts").replaceChildren(...a.facts.map((f) => el("li", {}, f)));
  },
};
