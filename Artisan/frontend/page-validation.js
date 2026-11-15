// RELIABILITY: the proof that the analysis is right, recomputed by the server from the code and the NASA data.
App.pages.validation = {
  data: null,
  init() {},
  async show() {
    if (!this.data) {
      $("va-body").replaceChildren(loadingEl(t("va_loading")));
      try { this.data = await api("/api/validation"); } catch (e) { $("va-body").replaceChildren(errorEl(e)); return; }
    }
    this.render();
  },
  refresh() { this.show(); },

  // numbers of each check, ready to drop into its sentence
  vars(check) {
    const v = check.values, out = {};
    for (const [key, value] of Object.entries(v)) {
      if (typeof value !== "number") out[key] = value;
      else if (Number.isInteger(value)) out[key] = fmt(value, 0);
      else if (["diff", "median"].includes(key) || key.startsWith("mae_") || key.startsWith("brier_")) out[key] = fmt(value, key === "diff" ? 3 : 2);
      else if (["sen", "ols", "mk"].includes(key)) out[key] = value < 1e-9 ? "0" : fmt(value, 3);
      else out[key] = pct(value);  // everything else is a share of cases
    }
    if (v.best) { out.best = t(`fm_${v.best}`); out.mae_best = fmt(v[`mae_${v.best}`], 2); }
    return out;
  },

  render() {
    const d = this.data;
    const mark = { pass: "✓", warn: "!", fail: "✕" };
    const item = (check) => el("li", { class: `va-item ${check.status}` },
      el("span", { class: "va-mark", "aria-hidden": "true" }, mark[check.status]),
      el("div", {},
        el("h3", {}, t(`va_${check.id}_title`), el("span", { class: "sr-only" }, ` — ${t(`va_status_${check.status}`)}`)),
        el("p", {}, t(`va_${check.id}_text`, this.vars(check))),
        check.id === "forecast" ? el("p", { class: "note-small" }, t("va_forecast_removed", this.vars(check))) : null));
    const block = (title, intro, checks) => el("article", { class: "card" }, el("h2", {}, title), el("p", { class: "va-intro" }, intro),
      el("ul", { class: "va-list" }, checks.map(item)));

    const summary = el("div", { class: "keys va-keys" },
      [["pass", d.summary.pass], ["warn", d.summary.warn], ["fail", d.summary.fail]].map(([status, n]) =>
        el("div", { class: `key ${status}` }, el("strong", {}, n), el("span", {}, t(`va_count_${status}`)))));
    const limits = el("article", { class: "card" }, el("h2", {}, t("va_limits_title")), el("p", { class: "va-intro" }, t("va_limits_intro")),
      el("ul", { class: "facts-list" }, [1, 2, 3, 4, 5].map((i) => el("li", {}, t(`va_limit_${i}`)))));

    $("va-body").replaceChildren(
      el("article", { class: "card" }, el("p", { class: "rep-intro" }, t("va_lead", { n: d.checks.length, years: d.n_years })), summary),
      block(t("va_calc_title"), t("va_calc_intro"), d.checks.filter((c) => c.block === "calc")),
      block(t("va_method_title"), t("va_method_intro"), d.checks.filter((c) => c.block === "method")),
      limits,
      el("p", { class: "note-small" }, t("va_footer", { version: d.version })));
  },
};
