"""Hazard indicators and risk scores, computed from daily NASA POWER data.

For each region and hazard we build ONE yearly indicator, test its trend,
and turn "is it getting worse?" + "were recent years unusual?" into a
0-100 risk score that the map can colour.
"""
import math
from functools import lru_cache

import pandas as pd

from backend import config
from backend.nasa_power import load_daily
from backend.regions import get_region, region_to_dict
from backend.stats import anomaly, robustness, trend_line, trend_test

WET_DAY_MM = 1.0  # a day with >= 1 mm of rain counts as "wet"
PROJECT_TO = 2030

# "worse": which direction of change increases the danger
HAZARDS: dict[str, dict] = {
    "heat": {
        "indicator_fr": "Jours de chaleur extrême par an",
        "indicator_en": "Extreme-heat days per year",
        "definition_fr": "Jours où la température max dépasse celle des 10 % de jours les plus chauds de 1991-2020",
        "definition_en": "Days hotter than the hottest 10% of days in 1991-2020",
        "unit": "days",
        "variable": "T2M_MAX",
        "worse": "up",
    },
    "flood": {
        "indicator_fr": "Jours de pluie très forte par an",
        "indicator_en": "Very heavy rain days per year",
        "definition_fr": "Jours plus pluvieux que les 5 % de jours de pluie les plus intenses de 1991-2020",
        "definition_en": "Days wetter than the top 5% of rainy days in 1991-2020",
        "unit": "days",
        "variable": "PRECTOTCORR",
        "worse": "up",
    },
    "drought": {
        "indicator_fr": "Humidité du sol (zone racinaire), moyenne annuelle",
        "indicator_en": "Root-zone soil wetness, yearly average",
        "definition_fr": "0 = sol complètement sec, 1 = sol saturé d'eau",
        "definition_en": "0 = completely dry soil, 1 = fully saturated soil",
        "unit": "0-1",
        "variable": "GWETROOT",
        "worse": "down",
    },
    "landslide": {
        "indicator_fr": "Pluie maximale cumulée sur 3 jours (mm)",
        "indicator_en": "Maximum 3-day rainfall total (mm)",
        "definition_fr": "Plusieurs jours de forte pluie saturent les pentes et déclenchent les glissements",
        "definition_en": "Several days of heavy rain saturate slopes and trigger landslides",
        "unit": "mm",
        "variable": "PRECTOTCORR",
        "worse": "up",
    },
}


def annual_indicator(daily: pd.DataFrame, hazard: str) -> pd.Series:
    """One value per year for the chosen hazard."""
    baseline = daily.loc[f"{config.BASELINE_START}":f"{config.BASELINE_END}"]
    year = daily.index.year
    rain = daily["PRECTOTCORR"]

    if hazard == "heat":
        threshold = baseline["T2M_MAX"].quantile(0.90)
        series = (daily["T2M_MAX"] > threshold).groupby(year).sum()
    elif hazard == "flood":
        wet_days = baseline["PRECTOTCORR"][baseline["PRECTOTCORR"] >= WET_DAY_MM]
        threshold = wet_days.quantile(0.95)
        series = (rain > threshold).groupby(year).sum()
    elif hazard == "drought":
        series = daily["GWETROOT"].groupby(year).mean()
    elif hazard == "landslide":
        series = rain.rolling(3).sum().groupby(year).max()
    else:
        raise KeyError(f"Unknown hazard '{hazard}'. Valid: {list(HAZARDS)}")

    series.index.name = "year"
    return series.astype(float)


def risk_level(score: float) -> str:
    """Turn a 0-100 score into a colour category for the map.

    Must return one of: "low", "medium", "high", "very_high".
    """
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "very_high"


FULL_POINTS, BONUS_POINTS = 45.0, 5.0  # per part: 45 at the "full" size + up to 5 beyond it = 50 max
ROBUSTNESS_WEIGHT = {"robust": 1.0, "consistent": 0.75, "not_robust": 0.25, "no_trend": 1.0}


def risk_score(series: pd.Series, trend: dict, worse: str, robustness: str = "robust",
               baseline: pd.Series | None = None) -> dict:
    """0-100 score = trend part (0-50) + recent-years part (0-50).

    - Trend part: only counts if the trend goes in the dangerous direction,
      full weight if significant (p < 0.05), half if only "possible" (p < 0.10).
      Size = total change over the period measured in "normal year-to-year
      swings" (baseline standard deviations). Reduced when the trend does not
      survive the post-2000 robustness check.
    - Recent part: how unusual the last 3 years are vs the 1991-2020 normal.
    """
    sign = 1 if worse == "up" else -1
    if baseline is None:  # callers that filter the years pass the full 1991-2020 normal instead
        baseline = series.loc[config.BASELINE_START:config.BASELINE_END]
    std = float(baseline.std(ddof=1))

    # A. trend part: total change over the period, in "normal year-to-year swings"
    size = sign * trend["change_over_period"] / std if std > 0 else 0.0
    evidence = 1.0 if trend["p_value"] < 0.05 else 0.5 if trend["p_value"] < 0.10 else 0.0
    check = ROBUSTNESS_WEIGHT[robustness]
    trend_points = points(size, full_at=2.0) * evidence * check if size > 0 else 0.0

    # B. recent part: are the last 3 years far from the 1991-2020 normal?
    recent = anomaly(float(series.iloc[-3:].mean()), baseline)
    recent_size = sign * recent["z_score"]
    recent_points = points(recent_size, full_at=2.5) if recent_size > 0 else 0.0

    score = round(trend_points + recent_points)
    return {
        "score": score,
        "level": risk_level(score),
        "trend_points": round(trend_points, 1),
        "recent_points": round(recent_points, 1),
        "recent_years": [int(y) for y in series.index[-3:]],
        "recent_anomaly": recent,
        # every ingredient, so the UI can show the calculation step by step
        "explain": {
            "normal_swing": std,  # 1991-2020 standard deviation, in the indicator's unit
            "change": float(trend["change_over_period"]),
            "change_in_swings": float(size),
            "p_value": float(trend["p_value"]),
            "evidence_weight": evidence,
            "check_weight": check,
            "robustness": robustness,
            "recent_in_swings": float(recent_size),
        },
    }


def points(size: float, full_at: float) -> float:
    """Turn a size measured in "normal swings" (standard deviations) into 0-50 points.

    `full_at` = the size that earns the full 50 points
    (trend part: 2 swings of change; recent part: 2.5 swings above normal).

    Straight line up to FULL_POINTS at `full_at`; beyond it, the last BONUS_POINTS
    are earned more and more slowly and 50 is never quite reached. So a bigger
    change always scores a little more: no ties at the ceiling.
    """
    if size <= full_at:
        return float(max(size, 0.0) / full_at * FULL_POINTS)
    return float(FULL_POINTS + BONUS_POINTS * (1 - math.exp(-(size - full_at) / full_at)))


@lru_cache(maxsize=64)
def analyze(region_id: str, hazard: str) -> dict:
    """Full analysis of one hazard in one region (cached in memory)."""
    if hazard not in HAZARDS:
        raise KeyError(f"Unknown hazard '{hazard}'")
    region = get_region(region_id)
    series = annual_indicator(load_daily(region), hazard)
    trend = trend_test(series)
    check = robustness(series, trend)
    return {
        "region": region_to_dict(region),
        "hazard": hazard,
        "info": HAZARDS[hazard],
        "series": {"years": [int(y) for y in series.index], "values": series.round(3).tolist()},
        "trend": trend,
        "robustness": check,
        "line": trend_line(series, trend, project_to=PROJECT_TO),
        "risk": risk_score(series, trend, HAZARDS[hazard]["worse"], check["status"]),
        "source": "NASA POWER (MERRA-2), daily, "
        f"{config.START_YEAR}-{config.END_YEAR}, point {region.lat}N {region.lon}E",
    }