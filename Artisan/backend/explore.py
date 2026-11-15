"""Flexible exploration: any indicator, any season, any years, any forecast horizon.

Used by the dashboard filters. Everything is computed from NASA POWER data and
cached in memory, so changing a filter back and forth is instant.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from backend import config
from backend.discover import PERIODS, VARIABLES, period_series
from backend.forecast import backtest, calibrate, forecast, hindcast
from backend.nasa_power import load_daily
from backend.regions import REGIONS, get_region, region_to_dict
from backend.risk import HAZARDS, annual_indicator, risk_score
from backend.stats import MIN_YEARS, robustness, trend_line, trend_test

# Which direction is dangerous for raw variables (None = both directions matter)
VARIABLE_WORSE = {"T2M": "up", "T2M_MAX": "up", "PRECTOTCORR": None, "GWETROOT": "down"}

METRICS: dict[str, dict] = {
    **{
        key: {"kind": "hazard", "fr": info["indicator_fr"], "en": info["indicator_en"],
              "unit": info["unit"], "worse": info["worse"], "hazard": key}
        for key, info in HAZARDS.items()
    },
    **{
        key: {"kind": "variable", "fr": info["fr"].capitalize(), "en": info["en"].capitalize(),
              "unit": info["unit"], "worse": VARIABLE_WORSE[key], "hazard": None}
        for key, info in VARIABLES.items()
    },
}


@lru_cache(maxsize=256)
def metric_series(region_id: str, metric: str, period: str = "year") -> pd.Series:
    """Yearly series for one region / metric / season (cached)."""
    if metric not in METRICS:
        raise ValueError(f"Unknown metric '{metric}'")
    if period not in PERIODS:
        raise ValueError(f"Unknown period '{period}'")
    daily = load_daily(get_region(region_id))
    if METRICS[metric]["kind"] == "hazard":
        if period != "year":
            raise ValueError("Hazard indicators are yearly: use period=year")
        return annual_indicator(daily, metric)
    return period_series(daily, metric, period)


@lru_cache(maxsize=64)
def metric_calibration(metric: str, period: str = "year") -> dict:
    """Best forecast method for this indicator and its past errors, from the 10 regions together."""
    records = [r for region in REGIONS for r in hindcast(metric_series(region.id, metric, period))]
    return calibrate(records)


def _baseline(series: pd.Series) -> pd.Series:
    return series.loc[config.BASELINE_START : config.BASELINE_END]


@lru_cache(maxsize=1024)
def analyze_metric(region_id: str, metric: str, period: str, start: int, end: int,
                   horizon: int, alpha: float) -> dict:
    """Trend + significance + robustness + forecast + back-test + extreme odds (+ risk)."""
    full = metric_series(region_id, metric, period)
    series = full.loc[start:end]
    if len(series.dropna()) < MIN_YEARS:
        raise ValueError(f"Choose at least {MIN_YEARS} years (got {len(series)}).")

    info = METRICS[metric]
    trend = dict(trend_test(series))
    trend["significant"] = trend["p_value"] < alpha
    trend["direction"] = ("increasing" if trend["slope_per_year"] > 0 else "decreasing") if trend["significant"] else "no_trend"

    check = robustness(series, trend) if series.index[0] <= config.ROBUST_FROM - 5 else {
        "status": "not_applicable", "from_year": config.ROBUST_FROM, "trend": None}

    calibration = metric_calibration(metric, period)
    fc = forecast(series, horizon, calibration, info["unit"])
    baseline = _baseline(full)
    worse_for_extremes = info["worse"] or "up"
    q = 0.90 if worse_for_extremes == "up" else 0.10
    threshold = float(baseline.quantile(q))
    baseline_mean = float(baseline.mean())
    # is next year's whole 80% range on the dangerous side of normal?
    beyond_normal = fc["lo80"][0] > baseline_mean if worse_for_extremes == "up" else fc["hi80"][0] < baseline_mean

    risk = None
    if info["worse"]:
        status = check["status"] if check["status"] != "not_applicable" else "robust"
        risk = risk_score(series, trend, info["worse"], status, baseline)

    return {
        "region": region_to_dict(get_region(region_id)),
        "metric": metric,
        "period": period,
        "label": {"fr": info["fr"], "en": info["en"]},
        "period_label": {"fr": PERIODS[period]["fr"], "en": PERIODS[period]["en"]},
        "unit": info["unit"],
        "worse": info["worse"],
        "range": [int(series.index[0]), int(series.index[-1])],
        "series": {"years": [int(y) for y in series.index], "values": series.round(4).tolist()},
        "trend": trend,
        "alpha": alpha,
        "robustness": check,
        "line": trend_line(series, trend),
        "forecast": fc,
        "backtest": backtest(full, horizon, calibration["method"]),
        "method_errors": calibration["mae"],  # average 1-5 year error of each method, in normal swings
        "extreme": {
            "threshold": threshold,
            "direction": worse_for_extremes,
            "beyond_normal": bool(beyond_normal),
        },
        "baseline_mean": baseline_mean,
        # plain "before -> now" comparison: average of the first 5 vs the last 5 years
        "before": {"years": [int(series.index[0]), int(series.index[4])], "mean": float(series.iloc[:5].mean())},
        "now": {"years": [int(series.index[-5]), int(series.index[-1])], "mean": float(series.iloc[-5:].mean())},
        "forecast_change": fc["mean"][-1] - baseline_mean,
        "forecast_change_sd": (fc["mean"][-1] - baseline_mean) / max(float(baseline.std(ddof=1)), 1e-9),
        "risk": risk,
        "source": f"NASA POWER (MERRA-2) daily, point {get_region(region_id).lat}N {get_region(region_id).lon}E",
    }


@lru_cache(maxsize=256)
def table_metric(metric: str, period: str, start: int, end: int, horizon: int, alpha: float) -> list[dict]:
    """One summary row per region: feeds the map colours and the comparison table."""
    rows = []
    for region in REGIONS:
        a = analyze_metric(region.id, metric, period, start, end, horizon, alpha)
        rows.append({
            "region": a["region"],
            "slope_per_decade": a["trend"]["slope_per_decade"],
            "p_value": a["trend"]["p_value"],
            "significant": a["trend"]["significant"],
            "confidence": a["trend"]["confidence"],
            "robustness": a["robustness"]["status"],
            "forecast_last": a["forecast"]["mean"][-1],
            "forecast_year": a["forecast"]["years"][-1],
            "forecast_change": a["forecast_change"],
            "forecast_change_sd": a["forecast_change_sd"],
            "beyond_normal": a["extreme"]["beyond_normal"],
            "skill": a["backtest"]["skill"],
            "risk_score": a["risk"]["score"] if a["risk"] else None,
            "risk_level": a["risk"]["level"] if a["risk"] else None,
            "risk_parts": {k: a["risk"][k] for k in ("trend_points", "recent_points", "recent_years", "recent_anomaly", "explain")}
            if a["risk"] else None,
            "baseline_mean": a["baseline_mean"],
            "unit": a["unit"],
            "before": a["before"],
            "now": a["now"],
        })
    return rows


def forecast_context(a: dict) -> str:
    """Plain text for the AI: the forecast part of an analysis."""
    fc, ex, bt = a["forecast"], a["extreme"], a["backtest"]
    lines = [
        f"Forecast method: '{fc['method']}' (chosen by back-test among trend, smoothing, persistence and the 30-year mean); "
        f"ranges come from past forecast errors. Normal (1991-2020 mean): {a['baseline_mean']:.3f} {a['unit']}.",
    ]
    for i, year in enumerate(fc["years"]):
        lines.append(
            f"  {year}: expected {fc['mean'][i]:.3f} {a['unit']} (80% range {fc['lo80'][i]:.3f}-{fc['hi80'][i]:.3f})"
        )
    if ex["beyond_normal"]:
        lines.append("Next year's whole 80% range is on the dangerous side of the 1991-2020 normal.")
    if bt["skill"] is not None:
        lines.append(f"Back-test: forecast error {bt['mae_model']:.3f} vs {bt['mae_climatology']:.3f} using the 30-year average "
                     f"and {bt['mae_persistence']:.3f} using last year's value.")
    return "\n".join(lines)
