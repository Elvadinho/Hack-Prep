// AI ASSISTANT: a console. Left: the context the AI receives (region, hazard, the NASA figures).
// Right: one conversation thread; the national summary is posted into the same thread.
// The AI only rewords numbers computed by the app (see backend/chat.py): it never computes them.
App.pages.ai = {
  region: "centre", hazard: "heat", busy: false,

  init() {
    $("ai-region").addEventListener("change", (e) => { this.region = e.target.value; this.loadContext(); });
    $("ai-summary").addEventListener("click", () => this.summary());
    $("ai-form").addEventListener("submit", (e) => { e.preventDefault(); this.ask(); });
    $("ai-input").addEventListener("keydown", (e) => {  // Enter sends, Shift+Enter adds a line
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.ask(); }
    });
  },

  show() {
    fillRegions($("ai-region"), this.region);
    seg($("ai-hazard"), HAZARDS.map((h) => [h, t(`hazard_${h}`)]), this.hazard, (h) => { this.hazard = h; this.loadContext(); });
    $("ai-input").placeholder = t("ai_placeholder");
    this.renderEmpty();
    this.loadContext();
  },
  refresh() { this.show(); },

  // the exact figures sent to the AI for this region and hazard
  async loadContext() {
    const box = $("ai-facts");
    box.replaceChildren(loadingEl());
    $("ai-scope").textContent = `${regionName(regionById(this.region))} · ${t(`hazard_${this.hazard}`)}`;
    try {
      const a = await api(`/api/analysis?region=${this.region}&hazard=${this.hazard}`);
      const tr = a.trend, risk = a.risk, unit = a.info.unit, pct = unit === "0-1";
      const facts = [
        [t("ai_f_score"), `${risk.score}/100`, t(`level_${risk.level}`)],
        [t("ai_f_trend"), `${signed(tr.slope_per_decade * (pct ? 100 : 1), pct ? 1 : 2)} ${pct ? "pts" : unitLabel(unit)} / 10 ${t("ai_years")}`, sureText(tr.confidence, a.robustness.status)],
        [t("ai_f_recent"), plain(risk.recent_anomaly.value, unit), t("ai_f_normal", { n: plain(risk.recent_anomaly.baseline_mean, unit) })],
      ];
      box.replaceChildren(...facts.map(([k, v, note]) => el("div", {}, el("dt", {}, k), el("dd", {}, v, el("small", {}, note)))));
    } catch (e) { box.replaceChildren(errorEl(e)); }
  },

  renderEmpty() {
    if ($("ai-log").querySelector(".msg")) return;  // a conversation is already running
    $("ai-log").replaceChildren(el("div", { class: "ai-empty" },
      el("p", { class: "eyebrow" }, t("ai_title")),
      el("h2", {}, t("ai_empty_title")),
      el("div", { class: "ai-suggest" }, t("ai_suggest").map((q, i) =>
        el("button", { type: "button", onclick: () => this.ask(q) }, el("span", {}, String(i + 1).padStart(2, "0")), q)))));
  },

  // one message in the thread: who speaks, about what, and the text
  message(kind, label, body) {
    $("ai-log").querySelector(".ai-empty")?.remove();
    const node = el("article", { class: `msg ${kind}` }, el("header", {}, label), body);
    $("ai-log").append(node);
    node.scrollIntoView({ block: "end", behavior: REDUCED_MOTION ? "auto" : "smooth" });
    return node;
  },

  async respond(label, request) {
    this.busy = true;
    $("ai-send").disabled = true; $("ai-summary").disabled = true;
    const body = el("div", { class: "ai-output" }, loadingEl(t("ai_thinking")));
    const node = this.message("bot", label, body);
    try {
      const r = await request();
      body.innerHTML = renderMarkdown(r.answer || t("ai_empty_answer"));
      labelCells(body);
      if (r.steps?.length) {  // which prewritten tools the agent ran on the NASA data, in order
        node.append(el("details", { class: "ai-steps" },
          el("summary", {}, t("ai_tools_used", { n: r.steps.length })),
          el("ol", {}, r.steps.map((s) => el("li", { class: s.ok ? "" : "warn" },
            el("code", {}, `${s.tool}(${Object.entries(s.args).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("|") : v}`).join(", ")})`),
            el("small", {}, s.summary))))));
      }
      node.append(el("footer", {}, `${t("ai_model")} · ${r.model}`));
    } catch (e) { body.replaceChildren(errorEl(e)); }
    finally {
      this.busy = false;
      $("ai-send").disabled = false; $("ai-summary").disabled = false;
      node.scrollIntoView({ block: "nearest" });
    }
  },

  summary() {
    if (this.busy) return;
    this.message("user", t("ai_you"), el("p", {}, t("ai_summary_ask")));
    this.respond(t("ai_summary"), () => api(`/api/summary?lang=${App.state.lang}`));
  },

  ask(text) {
    if (this.busy) return;
    const input = $("ai-input"), question = (text ?? input.value).trim();
    if (!question) return;
    input.value = "";
    const scope = `${regionName(regionById(this.region))} · ${t(`hazard_${this.hazard}`)}`;
    this.message("user", `${t("ai_you")} · ${scope}`, el("p", {}, question));
    // the agent: the model picks prewritten tools (statistics, comparisons, forecasts) and explains their results
    this.respond(`ArtisanConnect IA · ${scope}`, () => api("/api/agent", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ region: this.region, hazard: this.hazard, lang: App.state.lang, question }),
    }));
  },
};
