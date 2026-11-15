"""Advice engine: turns the NASA results into concrete, timed actions.

Rules are simple and transparent (judges can read them):
  1. PRIORITY from the results: urgent / prepare / watch
  2. TIMING from the region's own NASA monthly climate (hottest / wettest / driest month)
  3. ACTIONS per hazard, each linked to an artisan trade
  4. FACTS: the numbers that justify the advice (trend, forecast and how reliable it was on the past)
"""
from functools import lru_cache

import pandas as pd

from backend import config
from backend.artisans import find_artisans
from backend.explore import analyze_metric
from backend.nasa_power import load_daily
from backend.regions import get_region

MONTHS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}

ACTIONS: dict[str, list[dict]] = {
    "heat": [
        {"fr": "Isoler et ventiler les toits des écoles, centres de santé et logements", "en": "Insulate and ventilate roofs of schools, clinics and homes", "trade": "roof"},
        {"fr": "Installer de l'ombre : auvents, brise-soleil, arbres", "en": "Add shade: awnings, sun breakers, trees", "trade": "shading"},
        {"fr": "Prévoir des points d'eau potable et décaler le travail en plein air tôt le matin", "en": "Provide drinking-water points and move outdoor work to early morning", "trade": "water"},
        {"fr": "Alerter et suivre les personnes âgées et les enfants pendant les pics de chaleur", "en": "Warn and check on elderly people and children during heat peaks", "trade": None},
    ],
    "flood": [
        {"fr": "Curer et agrandir les caniveaux et buses", "en": "Clean and widen drains and culverts", "trade": "drain"},
        {"fr": "Surélever seuils et fondations dans les zones basses", "en": "Raise doorsteps and foundations in low areas", "trade": "foundation"},
        {"fr": "Ne pas construire dans les bas-fonds et lits de rivières", "en": "Do not build in low-lying areas and river beds", "trade": None},
        {"fr": "Préparer un plan d'évacuation et un kit d'urgence par quartier", "en": "Prepare an evacuation plan and an emergency kit per neighbourhood", "trade": None},
    ],
    "drought": [
        {"fr": "Construire des citernes pour stocker l'eau de pluie avant la saison sèche", "en": "Build tanks to store rainwater before the dry season", "trade": "tank"},
        {"fr": "Réhabiliter ou creuser des puits et forages", "en": "Repair or dig wells and boreholes", "trade": "well"},
        {"fr": "Passer à l'irrigation goutte-à-goutte et aux semences résistantes", "en": "Switch to drip irrigation and drought-tolerant seeds", "trade": "irrigation"},
        {"fr": "Organiser des réserves de fourrage et d'eau pour le bétail", "en": "Organise fodder and water reserves for livestock", "trade": None},
    ],
    "landslide": [
        {"fr": "Construire des murs de soutènement et gabions sur les pentes habitées", "en": "Build retaining walls and gabions on inhabited slopes", "trade": "retaining"},
        {"fr": "Drainer les pentes pour évacuer l'eau de pluie", "en": "Drain slopes to evacuate rainwater", "trade": "drain"},
        {"fr": "Replanter la végétation sur les talus dénudés", "en": "Replant vegetation on bare embankments", "trade": "revegetation"},
        {"fr": "Évacuer les maisons à risque après plusieurs jours de forte pluie", "en": "Evacuate at-risk homes after several days of heavy rain", "trade": None},
    ],
}

PRIORITY_TEXT = {
    "urgent": {"fr": "Agir maintenant", "en": "Act now"},
    "prepare": {"fr": "Se préparer cette année", "en": "Prepare this year"},
    "watch": {"fr": "Surveiller", "en": "Keep watching"},
}


@lru_cache(maxsize=16)
def monthly_climate(region_id: str) -> pd.DataFrame:
    """Average month-by-month climate of the region (NASA POWER, baseline period)."""
    daily = load_daily(get_region(region_id)).loc[f"{config.BASELINE_START}":f"{config.BASELINE_END}"]
    by_month = daily.groupby(daily.index.month)
    years = daily.index.year.nunique()
    return pd.DataFrame({
        "tmax": by_month["T2M_MAX"].mean(),
        "rain": by_month["PRECTOTCORR"].sum() / years,  # mm per month
        "soil": by_month["GWETROOT"].mean(),
    })


def _timing(hazard: str, climate: pd.DataFrame, lang: str) -> str:
    month = lambda m: MONTHS[lang][(m - 1) % 12]  # noqa: E731
    if hazard == "heat":
        peak = int(climate["tmax"].idxmax())
        return (f"Mois le plus chaud : {month(peak)} — finir les travaux avant {month(peak - 1)}."
                if lang == "fr" else f"Hottest month: {month(peak)} — finish the work before {month(peak - 1)}.")
    if hazard in ("flood", "landslide"):
        peak = int(climate["rain"].idxmax())
        return (f"Mois le plus pluvieux : {month(peak)} ({climate['rain'].max():.0f} mm) — agir avant {month(peak - 2)}."
                if lang == "fr" else f"Wettest month: {month(peak)} ({climate['rain'].max():.0f} mm) — act before {month(peak - 2)}.")
    dry = int(climate["soil"].idxmin())
    wet = int(climate["rain"].idxmax())
    return (f"Sol le plus sec en {month(dry)} — remplir les citernes pendant les pluies de {month(wet)}."
            if lang == "fr" else f"Driest soil in {month(dry)} — fill tanks during the {month(wet)} rains.")


def _fmt(value: float, unit: str) -> str:
    digits = 3 if unit == "0-1" else 1 if unit in ("mm", "days") else 2
    text = f"{value:.{digits}f}"
    return text if unit == "0-1" else f"{text} {'jours' if unit == 'days' else unit}"


def build_advice(region_id: str, hazard: str, horizon: int, lang: str) -> dict:
    a = analyze_metric(region_id, hazard, "year", config.START_YEAR, config.END_YEAR, horizon, 0.05)
    fc, ex, trend, risk, bt = a["forecast"], a["extreme"], a["trend"], a["risk"], a["backtest"]
    # priority from the risk score; one step up when next year's whole likely range is beyond normal
    if risk["level"] == "very_high" or (risk["level"] == "high" and ex["beyond_normal"]):
        priority = "urgent"
    elif risk["level"] == "high" or ex["beyond_normal"]:
        priority = "prepare"
    else:
        priority = "watch"

    unit = a["unit"].replace("days", "jours" if lang == "fr" else "days")
    y1 = fc["years"][0]
    side_fr = "au-dessus" if ex["direction"] == "up" else "en dessous"
    side_en = "above" if ex["direction"] == "up" else "below"
    if lang == "fr":
        facts = [
            f"Tendance {trend['first_year']}-{trend['last_year']} : {trend['slope_per_decade']:+.2f} {unit} par décennie (p = {trend['p_value']:.3f}).",
            f"Prévision {y1} : environ {_fmt(fc['mean'][0], a['unit'])} (80 % de chances entre {_fmt(fc['lo80'][0], a['unit'])} et {_fmt(fc['hi80'][0], a['unit'])}) ; normale : {_fmt(a['baseline_mean'], a['unit'])}.",
            f"Fiabilité : sur {bt['n_forecasts']} prévisions rejouées dans le passé, erreur moyenne de {_fmt(bt['mae_model'], a['unit'])}, "
            f"contre {_fmt(bt['mae_climatology'], a['unit'])} en prenant la moyenne des 30 dernières années.",
        ]
        if ex["beyond_normal"]:
            facts.append(f"Toute la plage probable de {y1} est {side_fr} de la normale 1991-2020.")
    else:
        facts = [
            f"Trend {trend['first_year']}-{trend['last_year']}: {trend['slope_per_decade']:+.2f} {unit} per decade (p = {trend['p_value']:.3f}).",
            f"Forecast {y1}: about {_fmt(fc['mean'][0], a['unit']).replace('jours', 'days')} (80% chance between {_fmt(fc['lo80'][0], a['unit']).replace('jours', 'days')} and {_fmt(fc['hi80'][0], a['unit']).replace('jours', 'days')}); normal: {_fmt(a['baseline_mean'], a['unit']).replace('jours', 'days')}.",
            f"Reliability: over {bt['n_forecasts']} forecasts replayed on the past, average error {_fmt(bt['mae_model'], a['unit']).replace('jours', 'days')}, "
            f"versus {_fmt(bt['mae_climatology'], a['unit']).replace('jours', 'days')} when using the average of the last 30 years.",
        ]
        if ex["beyond_normal"]:
            facts.append(f"The whole likely range for {y1} is {side_en} the 1991-2020 normal.")
    if a["robustness"]["status"] == "not_robust":
        facts.append("⚠ La tendance ne se confirme pas depuis 2000 (possible artefact MERRA-2 de 1998)." if lang == "fr"
                     else "⚠ The trend is not confirmed since 2000 (possible 1998 MERRA-2 artifact).")

    artisans = find_artisans(region_id, hazard, limit=6)
    keywords = {"roof": ["roof", "couvreur"], "shading": ["shading", "carpenter"], "water": ["tank", "well"],
                "drain": ["drain", "plumber", "mason"], "foundation": ["foundation", "mason"],
                "tank": ["tank"], "well": ["well"], "irrigation": ["irrigation"],
                "retaining": ["retaining", "gabion", "mason"], "revegetation": ["revegetation", "landscaper"]}
    actions = []
    for item in ACTIONS[hazard]:
        match = []
        if item["trade"]:
            words = keywords[item["trade"]]
            match = [x["name"] for x in artisans if any(w in (x["trade_en"] + x["services_en"]).lower() for w in words)][:2]
        actions.append({"text": item[lang], "artisans": match})

    return {
        "region": a["region"],
        "hazard": hazard,
        "priority": priority,
        "priority_label": PRIORITY_TEXT[priority][lang],
        "facts": facts,
        "timing": _timing(hazard, monthly_climate(region_id), lang),
        "actions": actions,
        "artisans": artisans,
    }
