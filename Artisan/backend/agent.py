"""AI agent with tools: the model asks, our prewritten functions compute, the model explains.

Like a small MCP server: each tool is a plain Python function with a name, a description and its
arguments. The language model never computes a number itself. At each step it replies with ONE
JSON object, either
    {"tool": "<name>", "args": {...}}   -> we run the tool on NASA POWER data and send back the result
    {"answer": "<markdown>"}            -> final answer for the user
This text protocol works with any chat model (no native function-calling support needed).
"""
import json
import re
import unicodedata
from functools import lru_cache

import httpx
import numpy as np
import pandas as pd
from scipy import stats as sps

from backend import config
from backend.chat import complete
from backend.explore import METRICS, analyze_metric
from backend.nasa_power import load_daily
from backend.regions import REGIONS, REGIONS_BY_ID
from backend.risk import HAZARDS, analyze
from backend.stats import MIN_YEARS, trend_test
from backend.towns import PLACES, place_as_region

MAX_STEPS = 6
EXTRA_PARAMETERS = ["RH2M", "WS2M"]  # humidity and wind: downloaded on demand, cached apart from the main data

# name -> (NASA POWER column, how one value per year is built, unit, description)
VARIABLES = {
    "temperature": ("T2M", "mean", "°C", "average air temperature at 2 m"),
    "max_temperature": ("T2M_MAX", "mean", "°C", "average of the daily maximum temperature"),
    "min_temperature": ("T2M_MIN", "mean", "°C", "average of the daily minimum temperature"),
    "hottest_day": ("T2M_MAX", "max", "°C", "temperature of the hottest day of the year"),
    "hot_days": ("T2M_MAX", "hot", "days", "days hotter than the 1991-2020 90th percentile of daily maxima"),
    "rain": ("PRECTOTCORR", "sum", "mm", "total rainfall of the year"),
    "heavy_rain_day": ("PRECTOTCORR", "max", "mm", "rain of the wettest day of the year"),
    "soil_moisture": ("GWETROOT", "mean", "0-1", "root-zone soil wetness (0 dry, 1 saturated)"),
    "humidity": ("RH2M", "mean", "%", "relative humidity at 2 m"),
    "wind": ("WS2M", "mean", "m/s", "wind speed at 2 m"),
}


# ------------------------------------------------------------------ data access
def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def resolve_place(place: str) -> str:
    """Accept an id ("town_kousseri"), a town ("Kousséri"), a region ("Extrême-Nord") or a country capital."""
    if place in PLACES:
        return place
    query = _norm(place)
    for region in REGIONS:
        if query in (_norm(region.name_fr), _norm(region.name_en), region.id):
            return region.id
    exact = [p for p in PLACES.values() if _norm(p["name"]) == query or _norm(p.get("country_en", "")) == query
             or _norm(p.get("country_fr", "")) == query]
    partial = [p for p in PLACES.values() if query and query in _norm(p["name"])]
    match = (exact or partial or [None])[0]
    if not match:
        raise ValueError(f"Unknown place '{place}'. Use find_place to search.")
    return match["id"]


@lru_cache(maxsize=64)
def _extra_daily(place_id: str) -> pd.DataFrame:
    """Humidity and wind for one place (NASA POWER daily point API, cached on disk)."""
    p = PLACES[place_id]
    path = config.CACHE_DIR / f"extra_{place_id}_{config.START_YEAR}_{config.END_YEAR}_{'-'.join(EXTRA_PARAMETERS)}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        response = httpx.get(config.POWER_URL, timeout=120, params={
            "parameters": ",".join(EXTRA_PARAMETERS), "community": "AG", "latitude": p["lat"], "longitude": p["lon"],
            "start": f"{config.START_YEAR}0101", "end": f"{config.END_YEAR}1231", "format": "JSON"})
        response.raise_for_status()
        payload = response.json()
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    frame = pd.DataFrame(payload["properties"]["parameter"])
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    return frame.replace(-999.0, np.nan)


def _daily(place_id: str, column: str) -> pd.Series:
    if column in EXTRA_PARAMETERS:
        return _extra_daily(place_id)[column]
    return load_daily(place_as_region(place_id))[column]


def yearly_series(place_id: str, variable: str) -> pd.Series:
    if variable not in VARIABLES:
        raise ValueError(f"Unknown variable '{variable}'. Valid: {list(VARIABLES)}")
    column, how, _, _ = VARIABLES[variable]
    daily = _daily(place_id, column)
    year = daily.index.year
    if how == "hot":
        threshold = daily.loc[f"{config.BASELINE_START}":f"{config.BASELINE_END}"].quantile(0.90)
        series = (daily > threshold).groupby(year).sum().astype(float)
    else:
        series = getattr(daily.groupby(year), how)()
    series.index.name = "year"
    return series


def _years(start, end) -> tuple[int, int]:
    start, end = int(start), int(end)
    if not (config.START_YEAR <= start <= end <= config.END_YEAR):
        raise ValueError(f"Years must be between {config.START_YEAR} and {config.END_YEAR}, start <= end.")
    return start, end


def _r(value, digits=3):
    if value is None:
        return None
    value = float(value)
    return None if np.isnan(value) else round(value, digits)


# ------------------------------------------------------------------ the tools
def find_place(name: str) -> dict:
    """Search the places the app knows (10 regional capitals, ~45 towns, 6 neighbouring capitals)."""
    query = _norm(name)
    hits = [p for p in PLACES.values() if query in _norm(p["name"]) or query in _norm(p.get("region", ""))][:8]
    return {"places": [{"id": p["id"], "name": p["name"], "region": p["region"], "lat": p["lat"], "lon": p["lon"]} for p in hits]}


def period_statistics(place: str, start: int, end: int, variables: list[str]) -> dict:
    """Over [start, end] per variable: mean, min/max years, trend (10+ years), and how unusual vs the 1991-2020 normal."""
    place_id = resolve_place(place)
    start, end = _years(start, end)
    if isinstance(variables, str):
        variables = [variables]
    out = {"place": PLACES[place_id]["name"], "period": [start, end], "variables": {}}
    for variable in variables[:6]:
        series = yearly_series(place_id, variable)
        part = series.loc[start:end].dropna()
        normal = series.loc[config.BASELINE_START:config.BASELINE_END]
        item = {
            "description": VARIABLES[variable][3], "unit": VARIABLES[variable][2], "n_years": int(len(part)),
            "mean": _r(part.mean()), "min": _r(part.min()), "min_year": int(part.idxmin()),
            "max": _r(part.max()), "max_year": int(part.idxmax()),
            "first_year_value": _r(part.iloc[0]), "last_year_value": _r(part.iloc[-1]),
            "normal_1991_2020": _r(normal.mean()),
            "difference_from_normal": _r(part.mean() - normal.mean()),
            "difference_in_normal_swings": _r((part.mean() - normal.mean()) / normal.std(ddof=1), 2),
        }
        if len(part) >= MIN_YEARS:
            trend = trend_test(part)
            item.update({"trend_per_decade": _r(trend["slope_per_decade"]), "trend_p_value": _r(trend["p_value"], 4),
                         "trend_verdict": trend["confidence"]})
        else:
            item["trend_note"] = (f"Only {len(part)} years: too short for a reliable trend test (needs {MIN_YEARS}). "
                                  "Use the year-by-year values and the comparison with the normal.")
            item["values"] = {int(y): _r(v) for y, v in part.items()}
        out["variables"][variable] = item
    return out


def compare_periods(place: str, variable: str, a_start: int, a_end: int, b_start: int, b_end: int) -> dict:
    """Average of one variable in two periods, the difference, and whether it beats chance (Welch t-test)."""
    place_id = resolve_place(place)
    series = yearly_series(place_id, variable)
    a = series.loc[slice(*_years(a_start, a_end))].dropna()
    b = series.loc[slice(*_years(b_start, b_end))].dropna()
    p = float(sps.ttest_ind(b, a, equal_var=False).pvalue) if len(a) > 2 and len(b) > 2 else None
    return {"place": PLACES[place_id]["name"], "variable": variable, "unit": VARIABLES[variable][2],
            "period_a": [int(a_start), int(a_end)], "mean_a": _r(a.mean()),
            "period_b": [int(b_start), int(b_end)], "mean_b": _r(b.mean()),
            "difference_b_minus_a": _r(b.mean() - a.mean()), "p_value_welch": _r(p, 4),
            "significant_at_5pct": None if p is None else p < 0.05}


def seasonal_cycle(place: str, variable: str, start: int, end: int) -> dict:
    """Month-by-month average over [start, end] next to the 1991-2020 normal (which season changed)."""
    place_id = resolve_place(place)
    if variable not in VARIABLES or VARIABLES[variable][1] in ("hot", "max"):
        raise ValueError("seasonal_cycle works with temperature, max_temperature, min_temperature, rain, soil_moisture, humidity, wind")
    column, how, unit, _ = VARIABLES[variable]
    daily = _daily(place_id, column)
    start, end = _years(start, end)
    agg = "sum" if how == "sum" else "mean"

    def monthly(frame: pd.Series) -> pd.Series:
        values = getattr(frame.groupby([frame.index.year, frame.index.month]), agg)()
        return values.groupby(level=1).mean()

    period = monthly(daily.loc[f"{start}":f"{end}"])
    normal = monthly(daily.loc[f"{config.BASELINE_START}":f"{config.BASELINE_END}"])
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return {"place": PLACES[place_id]["name"], "variable": variable, "unit": unit + (" per month" if agg == "sum" else ""),
            "months": {months[m - 1]: {"period": _r(period[m], 2), "normal": _r(normal[m], 2), "difference": _r(period[m] - normal[m], 2)}
                       for m in period.index}}


def yearly_values(place: str, variable: str, start: int, end: int) -> dict:
    """The value of every year in [start, end] (to cite a specific year)."""
    place_id = resolve_place(place)
    start, end = _years(start, end)
    series = yearly_series(place_id, variable).loc[start:end]
    return {"place": PLACES[place_id]["name"], "variable": variable, "unit": VARIABLES[variable][2],
            "values": {int(y): _r(v) for y, v in series.items()}}


def risk_ranking(hazard: str) -> dict:
    """Risk score (0-100) of the 10 regions for one hazard, highest first."""
    if hazard not in HAZARDS:
        raise ValueError(f"hazard must be one of {list(HAZARDS)}")
    rows = []
    for r in REGIONS:
        risk = analyze(r.id, hazard)["risk"]
        rows.append({"region": r.name_en, "capital": r.capital, "score": risk["score"], "level": risk["level"]})
    return {"hazard": hazard, "indicator": HAZARDS[hazard]["indicator_en"], "regions": sorted(rows, key=lambda x: -x["score"])}


def forecast(region: str, metric: str, horizon: int = 5) -> dict:
    """Expected value for the next years with the 80% range, for a Cameroon region and a metric."""
    region_id = resolve_place(region)
    if region_id not in REGIONS_BY_ID:
        region_id = PLACES[region_id]["region"]
    if region_id not in REGIONS_BY_ID:
        raise ValueError("forecast works for the 10 Cameroon regions")
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {list(METRICS)}")
    a = analyze_metric(region_id, metric, "year", config.START_YEAR, config.END_YEAR, max(1, min(int(horizon), 10)), 0.05)
    fc = a["forecast"]
    return {"region": REGIONS_BY_ID[region_id].name_en, "metric": metric, "unit": a["unit"], "method": fc["method"],
            "normal_1991_2020": _r(a["baseline_mean"]),
            "years": {y: {"expected": _r(m), "low_80": _r(lo), "high_80": _r(hi)}
                      for y, m, lo, hi in zip(fc["years"], fc["mean"], fc["lo80"], fc["hi80"])},
            "past_average_error": _r(a["backtest"]["mae_model"])}


TOOLS = {
    "find_place": (find_place, {"name": "town, region or country"}),
    "period_statistics": (period_statistics, {"place": "place id or name", "start": "first year", "end": "last year",
                                              "variables": f"list, any of {list(VARIABLES)}"}),
    "compare_periods": (compare_periods, {"place": "place", "variable": "one variable",
                                          "a_start": "year", "a_end": "year", "b_start": "year", "b_end": "year"}),
    "seasonal_cycle": (seasonal_cycle, {"place": "place", "variable": "one variable", "start": "year", "end": "year"}),
    "yearly_values": (yearly_values, {"place": "place", "variable": "one variable", "start": "year", "end": "year"}),
    "risk_ranking": (risk_ranking, {"hazard": f"one of {list(HAZARDS)}"}),
    "forecast": (forecast, {"region": "Cameroon region or town", "metric": f"one of {list(METRICS)}", "horizon": "1-10 years"}),
}


def run_tool(name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"Unknown tool '{name}'. Available: {list(TOOLS)}"}
    try:
        return TOOLS[name][0](**args)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"error": str(error)}
    except httpx.HTTPError as error:
        return {"error": f"NASA POWER unavailable: {error}"}


# ------------------------------------------------------------------ the agent loop
def _system_prompt(lang: str, context: str) -> str:
    catalogue = "\n".join(f"- {name}({', '.join(f'{k}: {v}' for k, v in args.items())}): {fn.__doc__.strip().splitlines()[0]}"
                          for name, (fn, args) in TOOLS.items())
    variables = "\n".join(f"- {k}: {v[3]} [{v[2]}]" for k, v in VARIABLES.items())
    language = {"fr": "French", "en": "English"}.get(lang, "French")
    return f"""You are ArtisanConnect, a climate-data assistant for Cameroon. Data: NASA POWER (MERRA-2 reanalysis),
daily, {config.START_YEAR}-{config.END_YEAR}, one ~50 km grid cell per place.

You can call these TOOLS (prewritten functions that compute on the NASA data):
{catalogue}

Variables available:
{variables}

RULES
1. Every number you give must come from a tool result. Never invent or estimate numbers yourself.
2. Reply with exactly ONE JSON object and nothing else:
   {{"tool": "<tool name>", "args": {{...}}}}  to call a tool, or
   {{"answer": "<your final answer in markdown>"}}  when you have what you need.
3. Call several tools if needed (one per message), at most {MAX_STEPS - 1}.
4. The final answer is in {language}, short and plain: what changed, by how much, how sure, and WHAT IT MEANS
   for people (health, water, crops, buildings). Say when a period is too short for a trend test.
   Never show internal codes like very_likely or very_high: say them in plain words.
5. If the question does not name a place, use the one in CONTEXT.

CONTEXT: {context}"""


def _parse(text: str) -> dict:
    """The JSON object in the model reply (tolerates code fences and text around it)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {"answer": text.strip()}  # the model answered in plain text: accept it as the final answer


def _short(result: dict) -> str:
    """One line describing a tool result, for the trace shown under the answer."""
    if "error" in result:
        return f"error: {result['error']}"
    keys = [k for k in result if k not in ("variables", "values", "months", "years", "regions", "places")]
    return ", ".join(f"{k}={result[k]}" for k in keys[:4])


def run_agent(question: str, lang: str = "fr", region: str | None = None, hazard: str | None = None, llm=complete) -> dict:
    """Answer a question by letting the model call tools. Returns the answer and every tool call made."""
    if region in REGIONS_BY_ID:
        r = REGIONS_BY_ID[region]
        context = f"The user is looking at {r.name_en} (place id '{region}', capital {r.capital})"
    else:
        context = "The user is looking at Cameroon as a whole"
    context += f", hazard '{hazard}'." if hazard else "."
    messages = [{"role": "system", "content": _system_prompt(lang, context)}, {"role": "user", "content": question}]
    steps, model = [], None
    for step in range(MAX_STEPS):
        last = step == MAX_STEPS - 1
        if last:
            messages.append({"role": "user", "content": 'Now give the final answer as {"answer": "..."}.'})
        reply = llm(messages, max_tokens=900, temperature=0.2)
        model = reply["model"]
        action = _parse(reply["answer"])
        if "tool" in action and not last:
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            result = run_tool(str(action["tool"]), args)
            steps.append({"tool": str(action["tool"]), "args": args, "ok": "error" not in result, "summary": _short(result)})
            messages.append({"role": "assistant", "content": json.dumps({"tool": action["tool"], "args": args})})
            messages.append({"role": "user", "content": f"TOOL RESULT ({action['tool']}):\n{json.dumps(result, ensure_ascii=False, default=str)[:6000]}"})
            continue
        answer = action.get("answer") or reply["answer"]
        return {"answer": str(answer).strip(), "model": model, "steps": steps}
    return {"answer": "", "model": model, "steps": steps}
