"""Artisan web API + static frontend.

Run from the Artisan folder:  python run.py   (or double-click run.bat)
"""
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import config
from backend.advice import build_advice
from backend.artisans import PREVENTION, find_artisans
from backend.chat import ask, build_context
from backend.discover import PERIODS, discoveries
from backend.explore import METRICS, analyze_metric, forecast_context, table_metric
from backend.regions import REGIONS, REGIONS_BY_ID, region_to_dict
from backend.report import build_report, compare_places, report_context
from backend.towns import PLACES, all_places
from backend.risk import HAZARDS, analyze

Hazard = Literal["heat", "flood", "drought", "landslide"]
Lang = Literal["fr", "en"]

app = FastAPI(title="Artisan - NASA hazard trends for Cameroon")


@app.middleware("http")
async def always_fresh_frontend(request, call_next):
    """Make the browser re-check page files on every load, so an update is never hidden by its cache."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _analysis(region_id: str, hazard: str) -> dict:
    """Shared helper: validate the region and turn NASA errors into clean HTTP errors."""
    if region_id not in REGIONS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region_id}'")
    try:
        return analyze(region_id, hazard)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"NASA POWER unavailable: {error}")


@app.get("/api/regions")
def list_regions():
    return [region_to_dict(region) for region in REGIONS]


@app.get("/api/hazards")
def list_hazards():
    return {key: {**info, "prevention": PREVENTION[key]} for key, info in HAZARDS.items()}


@app.get("/api/risk")
def risk_map(hazard: Hazard):
    """One row per region: everything the map needs to colour it."""
    rows = []
    for region in REGIONS:
        result = _analysis(region.id, hazard)
        rows.append({
            "region": result["region"],
            "score": result["risk"]["score"],
            "level": result["risk"]["level"],
            "direction": result["trend"]["direction"],
            "confidence": result["trend"]["confidence"],
            "slope_per_decade": result["trend"]["slope_per_decade"],
        })
    return rows


@app.get("/api/analysis")
def region_analysis(region: str, hazard: Hazard):
    return _analysis(region, hazard)


@app.get("/api/artisans")
def artisans(region: str, hazard: Hazard):
    if region not in REGIONS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'")
    return find_artisans(region, hazard)


@app.get("/api/overview")
def overview():
    """Every region x every hazard: the comparison table (like the MVP, for all 10 regions)."""
    rows = []
    for region in REGIONS:
        row = {"region": region_to_dict(region), "hazards": {}}
        for hazard in HAZARDS:
            result = _analysis(region.id, hazard)
            row["hazards"][hazard] = {
                "score": result["risk"]["score"],
                "level": result["risk"]["level"],
                "slope_per_decade": result["trend"]["slope_per_decade"],
                "p_value": result["trend"]["p_value"],
                "confidence": result["trend"]["confidence"],
                "robustness": result["robustness"]["status"],
            }
        rows.append(row)
    return {"period": [config.START_YEAR, config.END_YEAR], "rows": rows}


@app.get("/api/discoveries")
def list_discoveries():
    try:
        return discoveries()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"NASA POWER unavailable: {error}")


@app.get("/api/validation")
def validation():
    """Proof page: every check of the analysis, recomputed from the code and the NASA data."""
    from backend.validation import run_validation  # imported here: it is slow the first time
    return _guard(run_validation)


@app.get("/api/summary")
def ai_summary(lang: Lang = "fr"):
    """AI explanation of the whole country: risk table + automatic discoveries."""
    table = overview()
    found = list_discoveries()["findings"]
    lines = [f"Period analysed: {config.START_YEAR}-{config.END_YEAR}, NASA POWER (MERRA-2), 10 regions of Cameroon."]
    for row in table["rows"]:
        cells = ", ".join(
            f"{h} {v['score']}/100 ({v['slope_per_decade']:+.3f}/decade, p={v['p_value']:.3f}, {v['robustness']})"
            for h, v in row["hazards"].items()
        )
        lines.append(f"{row['region']['name_en']}: {cells}")
    for kind, items in found.items():
        for item in items[:3]:
            lines.append(f"Discovery [{kind}]: {item['text']['en']}")
    question = (
        "Summarise for local authorities what this means: the 3 most important risks, which regions need action "
        "first, the most surprising findings, the data-quality caution, and concrete prevention steps with local artisans."
    )
    try:
        return ask(question, lang, "\n".join(lines), max_tokens=1600)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))


# ---------------------------------------------------------------- dashboard filters
Metric = Literal["heat", "flood", "drought", "landslide", "T2M", "T2M_MAX", "PRECTOTCORR", "GWETROOT"]
Period = Literal["year", "DJF", "MAM", "JJA", "SON"]
Year = Annotated[int, Query(ge=config.START_YEAR, le=config.END_YEAR)]
Horizon = Annotated[int, Query(ge=1, le=10)]
Alpha = Annotated[float, Query(ge=0.001, le=0.2)]


def _guard(function, *args):
    """Run an analysis and turn data problems into clean HTTP errors."""
    try:
        return function(*args)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"NASA POWER unavailable: {error}")


@app.get("/api/metrics")
def list_metrics():
    return {"metrics": METRICS, "periods": PERIODS, "years": [config.START_YEAR, config.END_YEAR]}


@app.get("/api/explore")
def explore(region: str, metric: Metric, period: Period = "year", start: Year = config.START_YEAR,
            end: Year = config.END_YEAR, horizon: Horizon = 5, alpha: Alpha = 0.05):
    """One region, any filter combination: series, trend, significance, forecast, back-test."""
    if region not in REGIONS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'")
    return _guard(analyze_metric, region, metric, period, start, end, horizon, alpha)


@app.get("/api/table")
def table(metric: Metric, period: Period = "year", start: Year = config.START_YEAR,
          end: Year = config.END_YEAR, horizon: Horizon = 5, alpha: Alpha = 0.05):
    """All 10 regions for the current filters: map colours + comparison table."""
    return _guard(table_metric, metric, period, start, end, horizon, alpha)


@app.get("/api/advice")
def advice(region: str, hazard: Hazard, horizon: Horizon = 3, lang: Lang = "fr"):
    if region not in REGIONS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'")
    return _guard(build_advice, region, hazard, horizon, lang)


@app.get("/api/places")
def list_places():
    return all_places()


@app.get("/api/report")
def report(place: str, start: Year = config.START_YEAR, end: Year = config.END_YEAR, lang: Lang = "fr"):
    """Climate synthesis for one place: stats table, 5-year means, key facts, recommendations."""
    if place not in PLACES:
        raise HTTPException(status_code=404, detail=f"Unknown place '{place}'")
    return _guard(build_report, place, start, end, lang)


@app.get("/api/compare")
def compare(places: str, variable: Literal["T2M", "TXX", "TNN", "RAIN", "HOT", "SOIL"] = "T2M",
            start: Year = config.START_YEAR, end: Year = config.END_YEAR, lang: Lang = "fr"):
    """2-3 places (Cameroon towns or neighbouring capitals), one indicator, year by year."""
    ids = [p for p in places.split(",") if p][:4]
    unknown = [p for p in ids if p not in PLACES]
    if unknown or not ids:
        raise HTTPException(status_code=404, detail=f"Unknown place(s): {unknown or places}")
    return _guard(compare_places, ids, variable, start, end, lang)


@app.get("/api/report/ai")
def report_ai(place: str, start: Year = config.START_YEAR, end: Year = config.END_YEAR, lang: Lang = "fr"):
    """The AI writes the report as a short brief, using only the computed numbers."""
    data = report(place, start, end, lang)
    question = (
        f"Write a climate synthesis for {data['place']['name']} for local authorities, in this structure: "
        "1) one-paragraph overview of the climate and what is changing; "
        "2) a markdown table 'Indicator | Unit | Mean | Min (year) | Max (year) | Trend/decade (significance) | Change first vs last decade'; "
        "3) 'Key facts' as bullet points; 4) 'Recommendations' grouped by the axes A-D with concrete actions and artisans. "
        "Explain significance simply. Mention the since-2000 check when a trend is not robust."
    )
    try:
        return ask(question, lang, report_context(data), max_tokens=2200)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))


class ChatRequest(BaseModel):
    region: str
    hazard: Hazard
    lang: Lang = "fr"
    horizon: int = Field(default=5, ge=1, le=10)
    question: str = Field(min_length=1, max_length=500)


@app.post("/api/chat")
def chat(body: ChatRequest):
    result = _analysis(body.region, body.hazard)
    context = build_context(
        result, find_artisans(body.region, body.hazard), PREVENTION[body.hazard]["en"]
    )
    outlook = _guard(analyze_metric, body.region, body.hazard, "year", config.START_YEAR,
                     config.END_YEAR, body.horizon, 0.05)
    context += "\n" + forecast_context(outlook)
    try:
        return ask(body.question, body.lang, context)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))


# Serve the website (index.html, app.js...) at "/" - must come AFTER the API routes
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")