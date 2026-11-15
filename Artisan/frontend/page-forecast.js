// FORECASTS + ADVICE: next 1-10 years for one region and hazard, how reliable, and what to do.
App.pages.forecast = {
  region: "centre", hazard: "heat", horizon: 3,

  init() {
    $("fc-region").addEventListener("change", (e) => { this.region = e.target.value; this.load(); });
  },
  show(params) {
    if (params.region && regionById(params.region)) this.region = params.region;
    this.renderControls(); this.load();
  },
  refresh() { this.show({}); },

  renderControls() {
    fillRegions($("fc-region"), this.region);
    seg($("fc-hazard"), HAZARDS.map((h) => [h, t(`hazard_${h}`)]), this.hazard, (h) => { this.hazard = h; this.load(); });
    seg($("fc-horizon"), [1, 2, 3, 5, 10].map((h) => [h, h === 1 ? t("year_1") : t("years_n", { n: h })]), this.horizon, (h) => { this.horizon = h; this.load(); });
  },

  async load() {
    $("fc-numbers").replaceChildren(loadingEl());
    try {
      const q = `region=${this.region}&metric=${this.hazard}&horizon=${this.horizon}`;
      const [a, advice] = await Promise.all([
        api(`/api/explore?${q}`),
        api(`/api/advice?region=${this.region}&hazard=${this.hazard}&horizon=${this.horizon}&lang=${App.state.lang}`),
      ]);
      this.drawChart(a); this.renderNumbers(a); this.renderAdvice(advice);
    } catch (e) { $("fc-numbers").replaceChildren(errorEl(e)); }
  },

  drawChart(a) {
    const fc = a.forecast, last = a.range[1], lastVal = a.series.values.at(-1);
    const fx = [last, ...fc.years];
    const traces = [
      { x: fx, y: [lastVal, ...fc.hi80], mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
      { x: fx, y: [lastVal, ...fc.lo80], mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(188,127,50,0.18)", name: t("fc_band"), hoverinfo: "skip" },
      { x: a.series.years, y: a.series.values, mode: "lines+markers", name: t("fc_observed"), line: { color: "#245e4d", width: 2 }, marker: { size: 4 } },
      { x: a.line.years, y: a.line.trend.map((v) => Math.max(0, v)), mode: "lines", name: t("fc_trend"), line: { color: "#245e4d", width: 1.5, dash: "dot" } },
      { x: fx, y: [lastVal, ...fc.mean], mode: "lines+markers", name: t("fc_forecast"), line: { color: "#bc7f32", width: 2.6, dash: "dash" }, marker: { size: 7, symbol: "diamond" } },
    ];
    const thr = a.extreme.threshold, k = fc.years.length - 1;
    describeChart("fc-chart", `${t(`hazard_${this.hazard}`)}, ${regionName(regionById(this.region))}: ${a.range[0]}–${a.range[1]} ` +
      `${signed(a.trend.slope_per_decade, 2)}/10 (${fmtP(a.trend.p_value)}); ${t("fc_expected", { y: fc.years[k] })} ${withUnit(fc.mean[k], a.unit)}.`);
    Plotly.react("fc-chart", traces, plotLayout({
      yaxis: { fixedrange: true, gridcolor: "#e3eae5", rangemode: "tozero", title: { text: unitLabel(a.unit) } },
      shapes: [
        { type: "line", xref: "paper", x0: 0, x1: 1, y0: thr, y1: thr, line: { color: "#b5452f", width: 1, dash: "dot" } },
      ],
      annotations: [
        { xref: "paper", x: 0, y: thr, xanchor: "left", yanchor: "bottom", text: t("fc_threshold"), showarrow: false, font: { size: 10, color: "#b5452f" } },
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

  renderAdvice(a) {
    $("fc-priority").textContent = a.priority_label;
    $("fc-priority").className = `priority ${a.priority}`;
    $("fc-timing").textContent = a.timing;
    $("fc-actions").replaceChildren(...a.actions.map((x) => el("li", {}, x.text, x.artisans.length ? el("span", { class: "who" }, `→ ${x.artisans.join(", ")}`) : null)));
    $("fc-facts").replaceChildren(...a.facts.map((f) => el("li", {}, f)));
    $("fc-artisans").replaceChildren(...a.artisans.map((x) => {
      const where = regionById(x.region);
      return el("div", { class: "artisan" },
        el("b", {}, App.state.lang === "fr" ? x.trade_fr : x.trade_en), x.name,
        el("br"), el("small", {}, `${x.local ? t("local") : t("other")} · ${where ? regionName(where) : x.region}`));
    }));
  },
};
