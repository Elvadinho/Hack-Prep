"""Trend statistics: what is changing, how much, and is it significant?

- Sen's slope        -> HOW MUCH (robust to outliers), reported per decade
- Mann-Kendall test   -> IS IT SIGNIFICANT, with an effective-sample-size
  correction for autocorrelation (climate years are not independent).
  Measured on 45-year simulations (backend/validation.py): 5-6% false alarms for memory
  up to 0.6, about 10% for very strong memory (0.8).
- Anomaly z-score    -> IS IT UNUSUAL NOW compared with the 1991-2020 normal
"""
import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy.stats import norm

MIN_YEARS = 10  # fewer points than this gives meaningless trend tests


def confidence_label(p_value: float) -> str:
    """Translate a p-value into a plain-language key (translated in the UI).

    Must return one of: "very_likely", "likely", "possible", "chance".
    """
    if p_value < 0.01:  # less than 1% chance it's random
        return "very_likely"
    if p_value < 0.05:  # the usual scientific "significant" line
        return "likely"
    if p_value < 0.10:  # weak hint, not proof
        return "possible"
    return "chance"  # everything else: could easily be random


def trend_test(series: pd.Series) -> dict:
    """Trend of an annual series indexed by year (int).

    Returns slope per decade, p-value, direction and a plain-language label.
    """
    clean = series.dropna().sort_index()
    if len(clean) < MIN_YEARS:
        raise ValueError(f"Need at least {MIN_YEARS} years, got {len(clean)}.")
    years = clean.index.to_numpy()
    if np.any(np.diff(years) != 1):
        raise ValueError("Years must be consecutive (no gaps) for Mann-Kendall.")

    values = clean.to_numpy(dtype=float)
    result = mk.original_test(values)  # Mann-Kendall S, z + Sen's slope
    slope = float(result.slope)  # Sen's slope, units per year
    rho = lag1_autocorrelation(values, result.intercept, slope)
    inflation = (1 + rho) / (1 - rho)  # variance inflation for AR(1) memory
    z = float(result.z) / np.sqrt(inflation)
    p_value = float(2 * norm.sf(abs(z)))  # sf keeps precision for tiny p-values
    if p_value < 0.05:
        direction = "increasing" if slope > 0 else "decreasing"
    else:
        direction = "no_trend"

    return {
        "n_years": int(len(clean)),
        "first_year": int(years[0]),
        "last_year": int(years[-1]),
        "slope_per_year": slope,
        "slope_per_decade": slope * 10,
        "change_over_period": slope * (len(clean) - 1),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "direction": direction,
        "confidence": confidence_label(p_value),
        "intercept": float(result.intercept),  # fitted value at first year
        "autocorrelation": rho,
    }


def lag1_autocorrelation(values: np.ndarray, intercept: float, slope: float) -> float:
    """Year-to-year memory of the series after removing the Sen trend.

    Small samples underestimate it, so we add the Marriott-Pope bias
    correction (1 + 4r)/n, then keep it in [0, 0.95].
    """
    n = len(values)
    residuals = values - (intercept + slope * np.arange(n))
    residuals = residuals - residuals.mean()
    denominator = float(np.sum(residuals**2))
    if denominator == 0:  # perfect straight line: no noise, no memory
        return 0.0
    r1 = float(np.sum(residuals[1:] * residuals[:-1])) / denominator
    r1 = r1 + (1 + 4 * r1) / n
    return min(max(r1, 0.0), 0.95)


def robustness(series: pd.Series, trend: dict, start: int | None = None) -> dict:
    """Does the trend survive if we only look at the recent part of the record?

    Protects against trends created by one jump in the data (e.g. a change in
    the satellites feeding the MERRA-2 reanalysis around 1998).
      robust      -> same direction AND still p < 0.10 after `start`
      consistent  -> same direction (or flat) since `start`, but not significant on its own
      not_robust  -> recent trend goes the other way: be careful
      no_trend    -> no trend signal at all (p >= 0.10), nothing to check

    Weak signals (0.05 <= p < 0.10) are checked too: the risk score gives them
    points, so they must pass the same test as significant trends.
    """
    from backend import config  # local import keeps stats.py usable on its own

    start = start or config.ROBUST_FROM
    recent = series.loc[start:]
    if len(recent.dropna()) < MIN_YEARS:
        return {"status": "consistent", "from_year": start, "trend": None}
    recent_trend = trend_test(recent)
    if trend["p_value"] >= 0.10:
        status = "no_trend"
    elif recent_trend["slope_per_year"] * trend["slope_per_year"] < 0:  # truly the other way; flat is not a reversal
        status = "not_robust"
    elif recent_trend["p_value"] < 0.10:
        status = "robust"
    else:
        status = "consistent"
    return {"status": status, "from_year": start, "trend": recent_trend}


def trend_line(series: pd.Series, trend: dict, project_to: int | None = None) -> dict:
    """Sen trend line over the data, optionally extended (projection) with a band.

    The band = trend +/- 1.96 x standard deviation of the residuals: the range
    where ~95% of individual years fall if the trend simply continues.
    This is an extrapolation, NOT a forecast of a specific disaster.
    """
    clean = series.dropna().sort_index()
    first = trend["first_year"]
    fitted = trend["intercept"] + trend["slope_per_year"] * (clean.index - first)
    spread = float(np.std(clean.to_numpy() - np.asarray(fitted), ddof=1))

    last = project_to or trend["last_year"]
    years = list(range(first, last + 1))
    line = [trend["intercept"] + trend["slope_per_year"] * (y - first) for y in years]
    return {
        "years": years,
        "trend": line,
        "upper": [v + 1.96 * spread for v in line],
        "lower": [v - 1.96 * spread for v in line],
        "projected_from": trend["last_year"] + 1 if last > trend["last_year"] else None,
    }


def anomaly(value: float, baseline: pd.Series) -> dict:
    """How unusual is `value` compared with the baseline years?"""
    clean = baseline.dropna()
    mean = float(clean.mean())
    std = float(clean.std(ddof=1))
    z = (value - mean) / std if std > 0 else 0.0
    percentile = float((clean < value).mean() * 100)
    return {"value": float(value), "baseline_mean": mean, "z_score": z, "percentile": percentile}