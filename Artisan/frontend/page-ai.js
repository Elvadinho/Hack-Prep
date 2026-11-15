// AI ASSISTANT: national summary + questions about one region and hazard.
App.pages.ai = {
  region: "centre", hazard: "heat",

  init() {
    $("ai-region").addEventListener("change", (e) => { this.region = e.target.value; });
    $("ai-hazard").addEventListener("change", (e) => { this.hazard = e.target.value; });
    $("ai-summary").addEventListener("click", () => this.summary());
    $("ai-form").addEventListener("submit", (e) => { e.preventDefault(); this.ask(); });
  },
  show() {
    fillRegions($("ai-region"), this.region);
    $("ai-hazard").replaceChildren(...HAZARDS.map((h) => el("option", { value: h }, t(`hazard_${h}`))));
    $("ai-hazard").value = this.hazard;
    $("ai-input").placeholder = t("ai_placeholder");
    $("ai-suggest").replaceChildren(...t("ai_suggest").map((q) => el("button", { type: "button", onclick: () => this.ask(q) }, q)));
  },
  refresh() { this.show(); },

  async summary() {
    const btn = $("ai-summary"), out = $("ai-summary-out");
    btn.disabled = true; out.replaceChildren(loadingEl(t("ai_thinking")));
    try {
      const r = await api(`/api/summary?lang=${App.state.lang}`);
      out.innerHTML = renderMarkdown(r.answer);
      out.append(el("p", { class: "model" }, `AI: ${r.model}`));
    } catch (e) { out.replaceChildren(errorEl(e)); }
    finally { btn.disabled = false; }
  },

  async ask(text) {
    const input = $("ai-input"), question = (text ?? input.value).trim();
    if (!question) return;
    const log = $("ai-log");
    log.append(el("div", { class: "msg user" }, question));
    const pending = el("div", { class: "msg bot loading" }, t("ai_thinking"));
    log.append(pending); input.value = "";
    try {
      const r = await api("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region: this.region, hazard: this.hazard, lang: App.state.lang, horizon: 3, question }),
      });
      pending.className = "msg bot"; pending.innerHTML = renderMarkdown(r.answer);
    } catch (e) { pending.className = "msg bot"; pending.replaceChildren(errorEl(e)); }
    pending.scrollIntoView({ block: "nearest" });
  },
};
