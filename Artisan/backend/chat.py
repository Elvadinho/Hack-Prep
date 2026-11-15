"""AI assistant that EXPLAINS our NASA-based results (it never computes them).

Design: we put our computed facts in a CONTEXT block and tell the model to
use only those facts. This "grounded" approach works with free models that
don't support tool calling, and stops the AI from inventing numbers.
"""
from openai import OpenAI, OpenAIError

from backend import config

SYSTEM_PROMPT = """You are Artisan, an assistant helping communities in Cameroon prevent natural disasters.
Rules:
- Use ONLY the facts in the CONTEXT block (computed from NASA data). Never invent numbers or events.
- Answer in {language}, in short simple sentences a non-scientist understands.
- Always say how confident the trend is, and that this is a trend analysis, not a forecast of a specific disaster.
- Give practical prevention actions and mention the local artisans listed in CONTEXT when useful.
- If the question cannot be answered from CONTEXT, say so and say which data would be needed."""

LANGUAGES = {"fr": "French", "en": "English"}


def build_context(analysis: dict, artisans: list[dict], prevention: list[str]) -> str:
    """Plain-text summary of everything the AI is allowed to use."""
    region, info = analysis["region"], analysis["info"]
    trend, risk = analysis["trend"], analysis["risk"]
    line = analysis["line"]
    lines = [
        f"Region: {region['name_en']} ({region['name_fr']}), capital {region['capital']}",
        f"Hazard: {analysis['hazard']} - indicator: {info['indicator_en']} ({info['definition_en']})",
        f"Data source: {analysis['source']}",
        f"Trend {trend['first_year']}-{trend['last_year']}: {trend['slope_per_decade']:+.3f} {info['unit']} per decade, "
        f"total change {trend['change_over_period']:+.3f} {info['unit']}",
        f"Significance: p-value {trend['p_value']:.4f}, confidence '{trend['confidence']}', "
        f"direction '{trend['direction']}' (danger increases when indicator goes {info['worse']})",
        f"Recent years {risk['recent_years']}: average {risk['recent_anomaly']['value']:.3f} vs 1991-2020 normal "
        f"{risk['recent_anomaly']['baseline_mean']:.3f} (z-score {risk['recent_anomaly']['z_score']:+.2f})",
        f"Risk score: {risk['score']}/100, level '{risk['level']}'",
        f"Trend extrapolation to {line['years'][-1]}: {line['trend'][-1]:.3f} {info['unit']} "
        f"(95% range of a single year {line['lower'][-1]:.3f} to {line['upper'][-1]:.3f})",
        "Prevention actions: " + "; ".join(prevention),
        "Artisans (demo directory): "
        + "; ".join(f"{a['name']} - {a['trade_en']} ({a['region']})" for a in artisans),
    ]
    return "\n".join(lines)


def ask(question: str, lang: str, context: str, max_tokens: int = 700) -> dict:
    """Send the question + context to OpenRouter, trying the fallback model on failure."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is missing in .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.OPENROUTER_API_KEY,
        timeout=60,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(language=LANGUAGES.get(lang, "French"))},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"},
    ]

    last_error: Exception | None = None
    for model in (config.OPENROUTER_MODEL, config.OPENROUTER_FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=0.3
            )
            answer = response.choices[0].message.content
            if answer:
                return {"answer": answer.strip(), "model": model}
        except OpenAIError as error:
            last_error = error
    raise RuntimeError(f"AI service unavailable: {last_error}")