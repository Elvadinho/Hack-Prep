"""Forecasts for the next 1-10 years, chosen and calibrated by replaying the past.

We do not trust one formula. Four simple methods compete:
  trend        Sen trend line + last year's departure fading with the memory of the series
  smooth       simple exponential smoothing (recent years count more, no trend)
  persistence  "next year = last year"
  mean         the average of the last 30 years (climatology)

For each indicator we replay history ("had we forecast in 2005, 2006, ... how wrong
would we have been 1 to 10 years later?") on the 10 regions together and
  1. keep the method with the smallest average error (per indicator, not per
     series: 45 points are too few to choose series by series),
  2. take the ranges from the errors that method actually made, horizon by
     horizon. An "80% range" is therefore the range that contained 80% of the
     real values in the replay, not a theoretical formula.

This is NOT a weather forecast of a specific day or storm: it says what a typical
year is likely to look like, and how wrong such statements have been in the past.
"""
import numpy as np
import pandas as pd

from backend.stats import trend_test

METHODS = ("trend", "smooth", "persistence", "mean")
MIN_TRAIN_YEARS = 20
MAX_HORIZON = 10
CHOICE_HORIZONS = range(1, 6)  # the method is chosen on its 1-5 year errors
UPPER_LIMIT = {"0-1": 1.0, "days": 366.0}  # soil wetness and day counts have a ceiling
NON_NEGATIVE = ("mm", "days", "0-1")  # rain, counts and wetness cannot go below zero


def _smooth_level(values: np.ndarray) -> float:
    """Simple exponential smoothing; alpha picked by its own one-step errors."""
    best_level, best_sse = float(values[-1]), np.inf
    for alpha in np.arange(0.1, 1.0, 0.1):
        level, sse = float(values[0]), 0.0
        for value in values[1:]:
            sse += (value - level) ** 2
            level += alpha * (value - level)
        if sse < best_sse:
            best_level, best_sse = level, sse
    return best_level


def point_forecast(series: pd.Series, method: str, horizon: int) -> list[float]:
    """Central forecast of the `horizon` years after the end of `series`."""
    values = series.to_numpy(dtype=float)
    if method == "persistence":
        return [float(values[-1])] * horizon
    if method == "mean":
        return [float(values[-30:].mean())] * horizon
    if method == "smooth":
        return [_smooth_level(values)] * horizon
    if method == "trend":
        trend = trend_test(series)
        last_step = len(values) - 1
        last_residual = values[-1] - (trend["intercept"] + trend["slope_per_year"] * last_step)
        rho = trend["autocorrelation"]
        return [float(trend["intercept"] + trend["slope_per_year"] * (last_step + h) + rho**h * last_residual)
                for h in range(1, horizon + 1)]
    raise ValueError(f"Unknown forecast method {method!r}")


def hindcast(series: pd.Series, max_horizon: int = MAX_HORIZON) -> list[dict]:
    """Replay every method on the past of one series.

    One record per (forecast start, horizon): the real value, what each method
    said, and the spread of the data known at the time (used to pool series
    that have different units).
    """
    clean = series.dropna().sort_index()
    records = []
    for origin in range(MIN_TRAIN_YEARS, len(clean)):
        train, test = clean.iloc[:origin], clean.iloc[origin : origin + max_horizon]
        scale = float(train.std(ddof=1)) or 1.0
        predicted = {m: point_forecast(train, m, len(test)) for m in METHODS}
        for h, actual in enumerate(test.to_numpy(), start=1):
            records.append({"origin": int(train.index[-1]), "h": h, "actual": float(actual), "scale": scale,
                            "pred": {m: predicted[m][h - 1] for m in METHODS}})
    return records


def calibrate(records: list[dict], method: str | None = None) -> dict:
    """Choose the best method from pooled replays and keep its errors, by horizon.

    Errors are divided by the spread of each series so regions can be pooled.
    """
    if not records:
        return {"method": method or "mean", "mae": {}, "errors": {}, "n": 0}
    mae = {m: float(np.mean([abs(r["actual"] - r["pred"][m]) / r["scale"] for r in records if r["h"] in CHOICE_HORIZONS]))
           for m in METHODS}
    method = method or min(mae, key=mae.get)
    errors = {h: np.sort([(r["actual"] - r["pred"][method]) / r["scale"] for r in records if r["h"] == h])
              for h in sorted({r["h"] for r in records})}
    return {"method": method, "mae": mae, "errors": errors, "n": len(records)}


def _errors_at(calibration: dict, h: int) -> np.ndarray:
    known = sorted(calibration["errors"])
    return calibration["errors"][min(h, known[-1])] if known else np.zeros(1)


def forecast(series: pd.Series, horizon: int, calibration: dict, unit: str = "") -> dict:
    """Forecast with the calibrated method; ranges come from the past errors of that method."""
    clean = series.dropna().sort_index()
    method = calibration["method"]
    mean = point_forecast(clean, method, horizon)
    scale = float(clean.std(ddof=1)) or 1.0
    last_year = int(clean.index[-1])
    top = UPPER_LIMIT.get(unit, np.inf)
    floor = 0.0 if unit in NON_NEGATIVE else -np.inf

    out = {"method": method, "years": [], "mean": [], "lo80": [], "hi80": [], "lo95": [], "hi95": []}
    for h in range(1, horizon + 1):
        errors = _errors_at(calibration, h)
        out["years"].append(last_year + h)
        out["mean"].append(float(np.clip(mean[h - 1], floor, top)))
        for key, p in (("lo80", 0.10), ("hi80", 0.90), ("lo95", 0.025), ("hi95", 0.975)):
            out[key].append(float(np.clip(mean[h - 1] + np.quantile(errors, p) * scale, floor, top)))
    return out


def backtest(series: pd.Series, horizon: int, method: str) -> dict:
    """How wrong the chosen method was on THIS series, against the two simplest alternatives."""
    records = hindcast(series, horizon)
    if not records:
        return {"method": method, "n_forecasts": 0, "mae_model": None, "mae_climatology": None,
                "mae_persistence": None, "skill": None, "skill_persistence": None}
    mae = {m: float(np.mean([abs(r["actual"] - r["pred"][m]) for r in records])) for m in METHODS}
    skill = lambda ref: float(1 - mae[method] / mae[ref]) if mae[ref] > 0 else None  # noqa: E731
    return {
        "method": method,
        "n_forecasts": len(records),
        "mae_model": mae[method],
        "mae_climatology": mae["mean"],
        "mae_persistence": mae["persistence"],
        "skill": skill("mean"),                     # > 0: better than the 30-year average
        "skill_persistence": skill("persistence"),  # > 0: better than "same as last year"
    }
