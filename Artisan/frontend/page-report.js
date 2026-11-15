// SYNTHESIS: the climate brief for one place and period, written for non-specialists first.
App.pages.report = {
  place: "centre", start: 1981, end: 2025, data: null, key: "", simple: false,

  init() {
    $("rep-place").addEventListener("change", (e) => { this.place = e.target.value; this.load(); });
    $("rep-start").addEventListener("change", (e) => { this.start = Number(e.target.value); this.load(); });
    $("rep-end").addEventListener("change", (e) => { this.end = Number(e.target.value); this.load(); });
    $("rep-ai").addEventListener("click", () => this.writeWithAI());
    $("rep-print").addEventListener("click", () => window.print());
    $("rep-csv").addEventListener("click", () => this.downloadData());
    $("rep-link").addEventListener("click", (e) => copyLink(e.currentTarget));
  },

  show(params) {
    if (params.place && App.state.places.some((p) => p.id === params.place)) this.place = params.place;
    this.start = yearParam(params.start, this.start);
    this.end = yearParam(params.end, this.end);
    if ("view" in params || params.place) {  // a new link always re-renders in the requested view
      this.simple = params.view === "simple";
      this.key = "";
    }
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
    setLink("synthese", { place: this.place, start: this.start, end: this.end, view: this.simple ? "simple" : "" });
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

    // the 3 messages to remember (also the head of the printed, dated bulletin)
    const locale = App.state.lang === "fr" ? "fr-FR" : "en-GB";
    const month = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(new Date());
    const today = new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(new Date());
    const keyCard = el("article", { class: "card key-card" },
      el("div", { class: "bulletin-head" },
        el("p", { class: "bulletin-title" }, t("bulletin_title", { month })),
        el("p", { class: "bulletin-meta" }, `${r.place.name} · ${r.place.region_name} · ${r.period[0]}–${r.period[1]} · ${t("bulletin_issued", { date: today })}`)),
      el("h2", {}, t("key_title")),
      el("ol", { class: "key-list" }, this.keyMessages(r).map((k) => el("li", {}, el("b", {}, k.head), el("span", {}, k.text)))));

    // 2. "In short": one plain line per indicator, with how sure it is
    const brief = card(t("inshort"), el("ul", { class: "brief" }, r.variables.map((v) => {
      const tr = v.trend, rising = tr.slope_per_year > 0;
      const key = !tr.significant ? "short_flat" : rising ? "short_up" : "short_down";
      const icon = !tr.significant ? "=" : rising ? "↑" : "↓";
      const color = !tr.significant ? THEME.muted : rising ? THEME.warm : THEME.cool;
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
        el("td", {}, this.shortLabel(v.key), el("small", { class: "sub-p" }, unitName(v.unit))),
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
        el("thead", {}, el("tr", {}, [[t("c_ind")], [t("c_mean"), 1], [t("c_median"), 1], [t("c_min"), 1], [t("c_max"), 1], [t("c_std"), 1],
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
      el("ul", {}, a.items.map((text) => el("li", {}, text)))))));

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

    // section index in the "technical document" style: 01, 02 ...
    const num = (n, card_) => { card_.querySelector("h2")?.prepend(el("span", { class: "idx" }, String(n).padStart(2, "0"))); return card_; };
    $("rep-body").replaceChildren(intro, keyCard, brief, num(1, table), num(2, facts), num(3, five), num(4, recent), num(5, charts), num(6, outlook), num(7, reco),
      glossary, method, el("p", { class: "note-small" }, r.source));
    if (this.simple) {  // arrived from the home search: the short version first, everything one click away
      const more = el("button", { type: "button", class: "btn", onclick: () => {
        this.simple = false;
        setLink("synthese", { place: this.place, start: this.start, end: this.end });
        this.render(r);
        window.scrollTo({ top: 0 });
      } }, t("rep_more"));
      outlook.querySelector(".idx")?.remove();  // section numbers belong to the full report only
      $("rep-body").replaceChildren(intro, keyCard, brief, outlook, el("div", { class: "more-row" }, more), el("p", { class: "note-small" }, r.source));
      labelCells($("rep-body"));
      return;
    }
    labelCells($("rep-body"));
    r.variables.forEach((v, i) => this.drawDecades(`mini-${i}`, v));
    fitCharts($("rep-body"));
  },

  // one chart per indicator: every year (line) + 5-year averages (bands) + exceptional years (◆) + linear regression
  drawDecades(id, v) {
    const scale = v.unit === "0-1" ? 100 : 1;
    const color = v.trend.significant ? (v.trend.slope_per_year > 0 ? THEME.warm : THEME.cool) : THEME.muted;
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
      { x: stepX, y: stepY, mode: "lines", line: { color: THEME.band, width: 8 }, hoverinfo: "skip", name: t("rep_5y") },
      { x: v.series.years, y: v.series.values.map((x) => x * scale), mode: "lines+markers", line: { color: THEME.data, width: 1.6 },
        marker: { size: 3 }, hovertemplate: "%{x} : %{y:.2f}<extra></extra>", name: t("leg_year") },
      { x: v.ols.years, y: v.ols.fitted.map((x) => x * scale), mode: "lines", line: { color, width: 2.4, dash: "dash" },
        hoverinfo: "skip", name: t("leg_regression") },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.hi80].map((x) => x * scale), mode: "lines", line: { width: 0 }, hoverinfo: "skip" },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.lo80].map((x) => x * scale), mode: "lines", line: { width: 0 }, fill: "tonexty",
        fillcolor: THEME.warmBand, hoverinfo: "skip" },
      { x: [lastYear, ...f.years], y: [lastValue, ...f.mean].map((x) => x * scale), mode: "lines", line: { color: THEME.warm, width: 2, dash: "dot" },
        hovertemplate: `%{x} : %{y:.2f} (${t("fc_forecast")})<extra></extra>` },
      { x: out.map((o) => o.year), y: out.map((o) => o.value * scale), mode: "markers", marker: { symbol: "diamond", size: 8, color: THEME.alert },
        hovertemplate: "%{x} : %{y:.2f} (> 2σ)<extra></extra>", name: "> 2σ" },
    ], plotLayout({
      showlegend: false, hovermode: "closest", margin: { l: 48, r: 8, t: 6, b: 26 },
      font: { family: THEME.font, size: 11, color: THEME.ink },
      xaxis: { fixedrange: true, tickformat: "d", dtick: 5, gridcolor: THEME.grid },
      yaxis: { fixedrange: true, gridcolor: THEME.grid, title: { text: unitLabel(v.unit), font: { size: 11 } } },
    }), PLOT_CONFIG);
  },

  // 1. the clearest proven change, 2. what to expect in the last forecast year, 3. the first action
  keyMessages(r) {
    const byKey = Object.fromEntries(r.variables.map((v) => [v.key, v]));
    const proven = r.variables.filter((v) => v.trend.significant && v.robustness.status !== "not_robust");
    const strength = (v) => Math.abs(v.change) / (v.std || 1);
    const main = [...proven].sort((a, b) => strength(b) - strength(a))[0];
    const out = [];
    if (main) {
      out.push({ head: t("key_change", { label: this.shortLabel(main.key) }),
        text: t("key_change_text", { before: plain(main.first_mean, main.unit), now: plain(main.last_mean, main.unit),
          a: `${main.first_period[0]}–${main.first_period[1]}`, b: `${main.last_period[0]}–${main.last_period[1]}`,
          sure: sureText(main.trend.confidence, main.robustness.status).toLowerCase() }) });
    } else {
      out.push({ head: t("key_nochange"), text: t("key_nochange_text") });
    }
    const target = main || byKey.T2M, f = target.forecast, k = f.years.length - 1;
    out.push({ head: t("key_forecast", { year: f.years[k], label: this.shortLabel(target.key) }),
      text: t("key_forecast_text", { value: plain(f.mean[k], target.unit), lo: plain(f.lo80[k], target.unit),
        hi: plain(f.hi80[k], target.unit), normal: plain(target.normal, target.unit) }) });
    const axis = main && ["RAIN", "SOIL"].includes(main.key) ? r.recommendations[0]
      : r.recommendations.find((x) => x.axis === "B") || r.recommendations[0];
    if (axis?.items.length) out.push({ head: t("key_action", { axis: axis.title }), text: axis.items[0] });
    return out;
  },

  // every yearly value behind the page, then the forecasts
  downloadData() {
    const r = this.data;
    if (!r) return;
    const head = r.variables.map((v) => `${this.shortLabel(v.key)} (${csvUnit(v.unit)})`);
    const years = r.variables[0].series.years;
    const rows = [
      ["# ArtisanConnect", r.source], ["# " + t("place"), r.place.name, r.place.lat, r.place.lon], ["# " + t("dl_period"), `${r.period[0]}-${r.period[1]}`], [],
      [t("c_year"), ...head],
      ...years.map((y, i) => [y, ...r.variables.map((v) => v.series.values[i])]),
      [],
      [t("c_year"), t("c_ind"), t("dl_expected"), t("dl_low80"), t("dl_high80"), t("c_method")],
      ...r.variables.flatMap((v, k) => v.forecast.years.map((y, i) => [y, head[k], v.forecast.mean[i], v.forecast.lo80[i], v.forecast.hi80[i], t(`fm_${v.forecast.method}`)])),
    ];
    downloadCSV(`artisanconnect_${fileSlug(r.place.name)}_${r.period[0]}-${r.period[1]}.csv`, rows);
  },

  async writeWithAI() {
    const btn = $("rep-ai"), out = $("rep-ai-out");
    btn.disabled = true; out.hidden = false; out.replaceChildren(loadingEl(t("ai_thinking")));
    try {
      const r = await api(`/api/report/ai?place=${this.place}&start=${this.start}&end=${this.end}&lang=${App.state.lang}`);
      out.innerHTML = renderMarkdown(r.answer);
      labelCells(out);
      out.append(el("p", { class: "model" }, `AI: ${r.model}`));
      out.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth" });
    } catch (e) { out.replaceChildren(errorEl(e)); }
    finally { btn.disabled = false; }
  },
};
