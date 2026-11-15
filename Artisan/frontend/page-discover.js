// DISCOVERIES: what the automatic scan of 200 NASA series found — in plain words, "before -> now".
App.pages.discover = {
  data: null,
  init() {},
  async show() {
    if (!this.data) {
      $("dc-grid").replaceChildren(loadingEl());
      try { this.data = await api("/api/discoveries"); } catch (e) { $("dc-grid").replaceChildren(errorEl(e)); return; }
    }
    this.render();
  },
  refresh() { this.show(); },

  // "Littoral · Température moyenne" ; season added only when it is not the whole year
  what(ev) {
    const variable = ev.variable_label[App.state.lang];
    const label = variable.charAt(0).toUpperCase() + variable.slice(1);
    return ev.period === "year" ? label : `${label} ${ev.period_label[App.state.lang]}`;
  },

  beforeNow(ev) {
    const v = ev.values;
    const before = mean(v.slice(0, 5)), now = mean(v.slice(-5));
    return el("div", { class: "big-change" },
      plain(before, ev.unit), el("span", { class: "arrow", "aria-hidden": "true" }, "→"), plain(now, ev.unit),
      el("div", { class: "note-small" }, `${ev.years[0]}–${ev.years[4]} → ${ev.years.at(-5)}–${ev.years.at(-1)}`));
  },

  card(ev, body, extraClass = "") {
    return el("article", { class: `disc ${extraClass}` },
      el("span", { class: "disc-type" }, regionName(regionById(ev.region.id) || ev.region)),
      el("strong", {}, this.what(ev)),
      ...body,
      el("a", { href: `#/synthese?place=${ev.region.id}` }, t("dc_open")));
  },

  render() {
    const f = this.data.findings;
    $("dc-sub").textContent = t("dc_sub");
    $("dc-filter").replaceChildren();  // no filter tabs: 4 short sections instead
    const sections = [];
    const section = (title, cards) => cards.length && sections.push(el("section", { class: "dc-section" }, el("h2", {}, title), el("div", { class: "disc-grid" }, cards)));

    const alert = (f.data_alert || [])[0];
    if (alert) {
      section(t("dc_alert_title"), [el("article", { class: "disc alert" },
        el("p", {}, t("dc_alert_text", { year: alert.year, n: alert.regions.length })),
        sparkline(alert.evidence[0]))]);
    }
    section(t("dc_change_title"), (f.strong_trend || []).slice(0, 4).map((item) => {
      const ev = item.evidence[0];
      return this.card(ev, [this.beforeNow(ev),
        el("span", { class: `tag ${sureClass(ev.trend.confidence, ev.robustness.status)}` }, sureText(ev.trend.confidence, ev.robustness.status))]);
    }));
    section(t("dc_season_title"), (f.seasonal_shift || []).slice(0, 3).map((item) => {
      const ev = item.evidence[0];
      const key = ev.trend.slope_per_year > 0 ? "dc_season_text_up" : "dc_season_text";
      return this.card(ev, [this.beforeNow(ev), el("p", {}, t(key, { what: this.what(ev) }))]);
    }));
    section(t("dc_record_title"), (f.record || []).slice(0, 3).map((item) => {
      const ev = item.evidence[0], value = ev.values.at(-1), year = ev.years.at(-1);
      const isMax = value >= Math.max(...ev.values);
      return this.card(ev, [el("div", { class: "big-change" }, plain(value, ev.unit)),
        el("p", {}, t(isMax ? "dc_record_text" : "dc_record_text_low", { value: plain(value, ev.unit), year }))]);
    }));
    $("dc-grid").replaceChildren(...sections);
    $("dc-grid").className = "";  // sections hold their own grids
  },
};
