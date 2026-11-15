// SYNTHESIS: the climate brief for one place and period, written for non-specialists first.
App.pages.report = {
  place: "centre", start: 1981, end: 2025, data: null, key: "",

  init() {
    $("rep-place").addEventListener("change", (e) => { this.place = e.target.value; this.load(); });
    $("rep-start").addEventListener("change", (e) => { this.start = Number(e.target.value); this.load(); });
    $("rep-end").addEventListener("change", (e) => { this.end = Number(e.target.value); this.load(); });
    $("rep-ai").addEventListener("click", () => this.writeWithAI());
    $("rep-print").addEventListener("click", () => window.print());
  },

  show(params) {
    if (params.place && App.state.places.some((p) => p.id === params.place)) this.place = params.place;
    this.renderControls();
    this.load();
  },
  refresh() { this.key = ""; this.show({}); },

  renderControls() {
    fillPlaces($("rep-place"), this.place);
    fillYears($("rep-start"), this.start);
    fillYears($("rep-end"), this.end);
  },

  async load() {
    if (this.end - this.start < 9) { $("rep-body").replaceChildren(errorEl(new Error(t("years_min")))); return; }
    const key = `${this.place}|${this.start}|${this.end}|${App.state.lang}`;
    if (key === this.key) return;
    this.key = key;
    const place = App.state.places.find((p) => p.id === this.place);
    $("rep-body").replaceChildren(loadingEl(place && !place.capital ? t("rep_downloading", { place: place.name }) : t("loading")));
    $("rep-ai-out").hidden = true;
    try {
      const data = await api(`/api/report?place=${this.place}&start=${this.start}&end=${this.end}&lang=${App.state.lang}`);
      if (key !== this.key) return;
      this.data = data;
      this.render(data);
    } catch (e) { this.key = ""; $("rep-body").replaceChildren(errorEl(e)); }
  },

  // short name of each indicator for plain sentences
  shortLabel(key) {
    const labels = {
      fr: { T2M: "Température moyenne", TXX: "Jour le plus chaud de l'année", TNN: "Nuit la plus froide de l'année", RAIN: "Pluie par an", HOT: "Jours de forte chaleur par an", SOIL: "Humidité du sol" },
      en: { T2M: "Average temperature", TXX: "Hottest day of the year", TNN: "Coldest night of the year", RAIN: "Rain per year", HOT: "Very hot days per year", SOIL: "Soil moisture" },
    };
    return labels[App.state.lang][key];
  },

  render(r) {
    const v0 = r.variables[0];
    const yBefore = `${v0.first_period[0]}–${v0.first_period[1]}`, yNow = `${v0.last_period[0]}–${v0.last_period[1]}`;
    const card = (title, ...content) => el("article", { class: "card" }, title ? el("h2", {}, title) : null, ...content);

    // 1. identity + one-sentence climate
    const intro = card(null,
      el("div", { class: "rep-head" }, el("h2", {}, `${r.place.name} · ${r.place.region_name}`), el("span", { class: "badge" }, t("rep_climate", { type: r.climate_type }))),
      el("p", { class: "rep-meta" }, t("rep_meta", { n: r.n_years, start: r.period[0], end: r.period[1], records: r.n_records, missing: r.missing, lat: fmt(r.place.lat, 3), lon: fmt(r.place.lon, 3) })),
      el("p", { class: "rep-intro" }, r.overview));

    // 2. "In short": one plain line per indicator, with how sure it is
    const brief = card(t("inshort"), el("ul", { class: "brief" }, r.variables.map((v) => {
      const tr = v.trend, rising = tr.slope_per_year > 0;
      const key = !tr.significant ? "short_flat" : rising ? "short_up" : "short_down";
      const icon = !tr.significant ? "=" : rising ? "↑" : "↓";
      const color = !tr.significant ? "#5d6f68" : rising ? "#8d5f22" : "#2f6684";
      return el("li", {},
        el("b", { style: `color:${color}`, "aria-hidden": "true" }, icon),
        el("span", {}, t(key, { label: this.shortLabel(v.key), before: plain(v.first_mean, v.unit), now: plain(v.last_mean, v.unit) })),
        el("span", { class: `tag ${sureClass(tr.confidence, v.robustness.status)}` }, sureText(tr.confidence, v.robustness.status)));
    })));

    // 3. the full statistics table (same layout as a consultant's brief) + details for specialists
    // values with the precision of the unit (soil moisture shown in %)
    const val = (x, u) => (u === "0-1" ? `${fmt(x * 100, 1)}` : fmt(x, digits(u)));
    const delta = (x, u) => (u === "0-1" ? `${signed(x * 100, 1)} pts` : `${signed(x, digits(u))} ${unitLabel(u)}`);
    const perDecade = (v, slope) => (v.unit === "0-1" ? `${signed(slope * 100, 1)} pts` : `${signed(slope, v.unit === "°C" ? 2 : 1)} ${unitLabel(v.unit)}`);
    const simpleRows = r.variables.map((v) => {
      const sure = sureClass(v.trend.confidence, v.robustness.status);
      return el("tr", {},
        el("td", {}, this.shortLabel(v.key)),
        el("td", {}, unitLabel(v.unit)),
        el("td", { class: "num" }, val(v.mean, v.unit)),
        el("td", { class: "num" }, val(v.median, v.unit)),
        el("td", { class: "num" }, `${val(v.min, v.unit)} (${v.min_year})`),
        el("td", { class: "num" }, `${val(v.max, v.unit)} (${v.max_year})`),
        el("td", { class: "num" }, val(v.std, v.unit)),
        el("td", { class: `num ${v.trend.significant ? (v.trend.slope_per_decade > 0 ? "pos" : "neg") : ""}` },
          perDecade(v, v.trend.slope_per_decade)),
        el("td", { class: sure }, sureText(v.trend.confidence, v.robustness.status), el("small", { class: "sub-p" }, fmtP(v.trend.p_value))),
        el("td", { class: "num" }, perDecade(v, v.ols.slope_per_decade),
          el("small", { class: "sub-p" }, `${fmtP(v.ols.p_value)} · R² ${fmt(v.ols.r2, 2)}`)),
        el("td", { class: "num" }, delta(v.change, v.unit),
          el("small", { class: "sub-p" }, `${val(v.first_mean, v.unit)} → ${val(v.last_mean, v.unit)}`)));
    });
    const detailRows = r.variables.map((v) => {
      const d = digits(v.unit), tr = v.trend, o = v.ols;
      return el("tr", {},
        el("td", {}, v.label),
        el("td", { class: "num" }, fmt(v.mean, d)), el("td", { class: "num" }, `${fmt(v.min, d)} (${v.min_year})`),
        el("td", { class: "num" }, `${fmt(v.max, d)} (${v.max_year})`), el("td", { class: "num" }, fmt(v.std, d)),
        el("td", { class: "num" }, signed(o.slope_per_decade, Math.max(d, 2))),
        el("td", { class: "num" }, `${signed(o.ci95_per_decade[0], Math.max(d, 2))} … ${signed(o.ci95_per_decade[1], Math.max(d, 2))}`),
        el("td", { class: "num" }, fmt(o.r2, 3)),
        el("td", {}, fmtP(o.p_value)),
        el("td", { class: "num" }, signed(tr.slope_per_decade, Math.max(d, 2))), el("td", {}, fmtP(tr.p_value)),
        el("td", {}, t(`robust_${v.robustness.status}`)));
    });
    const table = card(t("rep_table"),
      el("div", { class: "table-wrap" }, el("table", { class: "rep-table" },
        el("thead", {}, el("tr", {}, [[t("c_ind")], [t("c_unit")], [t("c_mean"), 1], [t("c_median"), 1], [t("c_min"), 1], [t("c_max"), 1], [t("c_std"), 1],
          [t("c_sen_main"), 1], [t("col_sure")], [t("c_reg_main"), 1], [t("col_evol", { a: yBefore, b: yNow }), 1]]
          .map(([h, num]) => el("th", { class: num ? "num" : null }, h)))),
        el("tbody", {}, simpleRows))),
      el("p", { class: "note-small" }, t("table_help")),
      el("details", { class: "stats" }, el("summary", {}, t("details_stats")),
        el("div", { class: "table-wrap" }, el("table", {},
          el("thead", {}, el("tr", {}, [[t("c_ind")], [t("c_mean"), 1], [t("c_min"), 1], [t("c_max"), 1], [t("c_std"), 1],
            [t("c_ols"), 1], [t("c_ols_ci"), 1], ["R²", 1], [t("c_ols_p")], [t("c_sen"), 1], [t("c_mk_p")], [t("c_rob")]]
            .map(([h, num]) => el("th", { class: num ? "num" : null }, h)))),
          el("tbody", {}, detailRows))),
        el("p", { class: "note-small" }, t("stats_help"))));

    // 4. one bar chart per indicator: the average of each decade
    const charts = card(t("rep_charts"), el("p", { class: "note-small" }, t("bars_help")),
      el("div", { class: "mini-grid big" }, r.variables.map((v, i) => {
        const scale = v.unit === "0-1" ? 100 : 1, per = v.unit === "0-1" ? "pts" : unitLabel(v.unit);
        const stat = (label, value) => el("span", {}, el("small", {}, label), el("b", {}, value));
        return el("div", { class: "mini" },
          el("div", { class: "mini-head" },
            el("h4", {}, this.shortLabel(v.key)),
            el("span", { class: `tag ${sureClass(v.trend.confidence, v.robustness.status)}` }, sureText(v.trend.confidence, v.robustness.status))),
          el("div", { class: "mini-stats" },
            stat(t("c_mean"), plain(v.mean, v.unit)),
            stat("Min", `${plain(v.min, v.unit)} (${v.min_year})`),
            stat("Max", `${plain(v.max, v.unit)} (${v.max_year})`),
            stat(t("c_ols"), `${signed(v.ols.slope_per_decade * scale, v.unit === "°C" ? 2 : 1)} ${per}`),
            stat("R²", fmt(v.ols.r2, 2))),
          el("p", { class: "equation" }, t("rep_equation", {
            a: fmt(v.ols.fitted[0] * scale, v.unit === "mm" || v.unit === "days" ? 1 : 2),
            b: signed(v.ols.slope_per_year * scale, v.unit === "mm" || v.unit === "days" ? 2 : 3),
            y0: v.ols.years[0], p: fmtP(v.ols.p_value),
            lo: signed(v.ols.ci95_per_decade[0] * scale, 2), hi: signed(v.ols.ci95_per_decade[1] * scale, 2) })),
          el("div", { class: "mini-chart", id: `mini-${i}` }));
      })));

    const facts = card(t("rep_facts"), el("ul", { class: "facts-list" }, r.facts.map((f) => {
      const cut = f.indexOf(":");  // "Topic : explanation" -> topic in bold
      return cut > 0 && cut < 40 ? el("li", {}, el("b", {}, f.slice(0, cut).trim()), ` : ${f.slice(cut + 1).trim()}`) : el("li", {}, f);
    })));
    const reco = card(t("rep_reco"), el("div", { class: "axes" }, r.recommendations.map((a) => el("div", { class: "axis" },
      el("h4", {}, `${a.axis}. ${a.title}`),
      el("ul", {}, a.items.map((it) => el("li", {}, it.text))),
      a.artisans?.length ? el("p", { class: "who" }, `${t("rep_artisans")} : ${a.artisans.join(", ")}`) : null))));

    // small summary table: average of every 5-year block, one row per indicator
    const bins = v0.five_year.map((b) => b.label.replace(/^(\d{4})-(\d{2})(\d{2})$/, "$1–$3"));
    const five = card(t("rep_5y"), el("div", { class: "table-wrap" }, el("table", { class: "five-table" },
      el("thead", {}, el("tr", {}, el("th", {}, t("c_ind")), bins.map((b) => el("th", { class: "num" }, b.replace(/^(\d{4})-(\d{4})$/, (m, a, z) => `${a}–${z.slice(2)}`))))),
      el("tbody", {}, r.variables.map((v) => el("tr", {}, el("td", {}, this.shortLabel(v.key)),
        v.five_year.map((b) => el("td", { class: "num" }, plain(b.mean, v.unit).replace(` ${unitLabel(v.unit)}`, "")))))))),
      el("p", { class: "note-small" }, t("rep_5y_help")));

    // what the verdict labels mean (they describe the climate signal, not the quality of the calculation)
    const legendRows = [[`${t("sure_likely")} / ${t("sure_very_likely")}`, "lg_very_likely"], [t("sure_possible"), "lg_possible"],
      [t("sure_chance"), "lg_chance"], [sureText("likely", "not_robust"), "lg_check"]];
    brief.append(el("details", { class: "legend-box" }, el("summary", {}, t("lg_title")), el("p", {}, t("lg_intro")),
      el("dl", { class: "glossary" }, legendRows.flatMap(([label, key]) => [el("dt", {}, label), el("dd", {}, t(key))]))));

    // forecast of each indicator: method chosen and ranges calibrated by replaying the past
    const fcYears = v0.forecast.years, lastK = fcYears.length - 1;
    const reliable = (b) => (b.skill > 0 && b.skill_persistence > 0 ? ["yes", t("rel_good")]
      : b.skill > 0 || b.skill_persistence > 0 ? ["no", t("rel_mid")] : ["warn", t("rel_bad")]);
    const outlook = card(t("rep_fc", { a: fcYears[0], b: fcYears[lastK] }), el("div", { class: "table-wrap" }, el("table", { class: "rep-table" },
      el("thead", {}, el("tr", {}, [[t("c_ind")], [t("c_normal"), 1], [t("c_expected", { y: fcYears[lastK] }), 1], [t("c_range"), 1], [t("c_method")], [t("c_reliable")]]
        .map(([h, num]) => el("th", { class: num ? "num" : null }, h)))),
      el("tbody", {}, r.variables.map((v) => {
        const f = v.forecast, [cls, text] = reliable(v.backtest);
        return el("tr", {},
          el("td", {}, `${this.shortLabel(v.key)} (${unitLabel(v.unit)})`),
          el("td", { class: "num" }, val(v.normal, v.unit)),
          el("td", { class: "num" }, el("b", {}, val(f.mean[lastK], v.unit))),
          el("td", { class: "num" }, `${val(f.lo80[lastK], v.unit)} – ${val(f.hi80[lastK], v.unit)}`),
          el("td", {}, t(`fm_${f.method}`)),
          el("td", { class: cls }, text));
      })))),
      el("p", { class: "note-small" }, t("rep_fc_help")));

    // the last years, value by value (to check recent records yourself)
    const recentYears = r.recent.years;
    const recent = card(t("rep_recent"), el("div", { class: "table-wrap" }, el("table", { class: "five-table" },
      el("thead", {}, el("tr", {}, el("th", {}, t("c_ind")), recentYears.map((y) => el("th", { class: "num" }, y)))),
      el("tbody", {}, r.variables.map((v) => el("tr", {}, el("td", {}, `${this.shortLabel(v.key)} (${unitLabel(v.unit)})`),
        r.recent.rows[v.key].map((x, i) => el("td", { class: `num ${recentYears[i] === v.max_year ? "rec-max" : recentYears[i] === v.min_year ? "rec-min" : ""}` }, val(x, v.unit)))))))),
      el("p", { class: "note-small" }, t("rep_recent_help")));

    // how to read: every word of the table explained for non-specialists
    const glossary = card(t("rep_read"), el("dl", { class: "glossary" },
      ["mean", "median", "minmax", "std", "trend", "sure", "evol", "outlier"].flatMap((k) => [el("dt", {}, t(`g_${k}`)), el("dd", {}, t(`g_${k}_text`))])));

    // method, for reviewers
    const method = el("details", { class: "card method" }, el("summary", {}, t("rep_method")),
      el("ul", {}, ["data", "indic", "trend", "sig", "robust", "ols", "limits"].map((k) => el("li", {}, t(`m_${k}`, { lat: fmt(r.place.lat, 3), lon: fmt(r.place.lon, 3), n: r.n_years, start: r.period[0], end: r.period[1] })))));

    const num = (n, card_) => { card_.querySelector("h2")?.prepend(`${n}. `); return card_; };
    $("rep-body").replaceChildren(intro, brief, num(1, table), num(2, facts), num(3, five), num(4, recent), num(5, charts), num(6, outlook), num(7, reco),
      glossary, method, el("p", { class: "note-small" }, r.source));
    r.variables.forEach((v, i) => this.drawDecades(`mini-${i}`, v));
  },

  // one chart per indicator: every year (line) + 5-year averages (bands) + exceptional years (◆) + linear regression
  drawDecades(id, v) {
    const scale = v.unit === "0-1" ? 100 : 1;
    const color = v.trend.significant ? (v.trend.slope_per_year > 0 ? "#bc7f32" : "#2f6684") : "#5d6f68";
    const stepX = [], stepY = [];
    v.five_year.forEach((b) => {
      const [a, z] = b.label.split("-").map(Number);
      stepX.push(a - 0.5, z + 0.5, null); stepY.push(b.mean * scale, b.mean * scale, null);
    });
    const out = v.outliers || [];
    const f = v.forecast, lastYear = v.series.years.at(-1), lastValue = v.series.values.at(-1);
    describeChart(id, `${this.shortLabel(v.key)}: ${plain(v.first_mean, v.unit)} → ${plain(v.last_mean, v.unit)}; `
      + `${t("c_trend_reg")} ${signed(v.ols.slope_per_decade * scale, 2)}/10 (R² ${fmt(v.ols.r2, 2)})`);
    Plotly.react(id, [
      { x: stepX, y: stepY, mode: "lines", line: { color: "rgba(36,94,77,0.25)", width: 8 }, hoverinfo: "skip", name: t("rep_5y") },
      { x: v.series.years, y: v.series.values.map((x) => x * scale), mode: "lines+markers", line: { color: "#245e4d", width: 1.6 },
        marker: { size: 3 }, hovertemplate: "%{x} : %{y:.2f}<extra></extra>", name: t("leg_year") },
      { x: v.ols.years, y: v.ols.fitted.map((x) => x * scale), mode: "lines", line: { color, width: 2.4, dash: "dash" },
        hoverinfo: "skip", name: t("leg_regression") },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.hi80].map((x) => x * scale), mode: "lines", line: { width: 0 }, hoverinfo: "skip" },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.lo80].map((x) => x * scale), mode: "lines", line: { width: 0 }, fill: "tonexty",
        fillcolor: "rgba(188,127,50,0.20)", hoverinfo: "skip" },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.mean].map((x) => x * scale), mode: "lines", line: { color: "#bc7f32", width: 2, dash: "dot" },
        hovertemplate: `%{x} : %{y:.2f} (${t("fc_forecast")})<extra></extra>` },
      { x: out.map((o) => o.year), y: out.map((o) => o.value * scale), mode: "markers", marker: { symbol: "diamond", size: 8, color: "#b5452f" },
        hovertemplate: "%{x} : %{y:.2f} (> 2σ)<extra></extra>", name: "> 2σ" },
    ], plotLayout({
      showlegend: false, hovermode: "closest", margin: { l: 48, r: 8, t: 6, b: 26 },
      font: { family: "Inter", size: 11, color: "#1d3030" },
      xaxis: { fixedrange: true, tickformat: "d", dtick: 5, gridcolor: "#eef3ef" },
      yaxis: { fixedrange: true, gridcolor: "#e3eae5", title: { text: unitLabel(v.unit), font: { size: 11 } } },
    }), PLOT_CONFIG);
  },

  async writeWithAI() {
    const btn = $("rep-ai"), out = $("rep-ai-out");
    btn.disabled = true; out.hidden = false; out.replaceChildren(loadingEl(t("ai_thinking")));
    try {
      const r = await api(`/api/report/ai?place=${this.place}&start=${this.start}&end=${this.end}&lang=${App.state.lang}`);
      out.innerHTML = renderMarkdown(r.answer);
      out.append(el("p", { class: "model" }, `AI: ${r.model}`));
      out.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth" });
    } catch (e) { out.replaceChildren(errorEl(e)); }
    finally { btn.disabled = false; }
  },
};
