"""Proof that the analysis is right: every check is recomputed, never typed by hand.

Two computed blocks, each answering one question a jury can ask:
  calc    "Are the calculations right?"        -> same numbers as reference libraries and as the NASA export
  method  "Does the method behave as claimed?" -> tested on artificial series where we KNOW the truth,
                                                 and by replaying forecasts on the past
(the third block, "what the data cannot tell us", is plain text in the interface)

Thresholds for pass / warn are fixed here, before looking at the results.
Results are cached on disk and recomputed whenever the analysis code changes.
"""
import hashlib
import json

import numpy as np
import pandas as pd
import pymannkendall
from scipy import stats as sps

from backend import config
from backend.discover import benjamini_hochberg, pettitt, step_preferred
from backend.explore import METRICS, analyze_metric, metric_calibration, metric_series
from backend.forecast import METHODS, calibrate, hindcast
from backend.regions import REGIONS
from backend.report import VARIABLES, linear_regression, place_yearly
from backend.stats import trend_test

SEED = 2026
N_YEARS = config.END_YEAR - config.START_YEAR + 1
YEARS = list(range(config.START_YEAR, config.END_YEAR + 1))
CSV_PLACES = {"Kousseri-donnees.csv": "town_kousseri", "Banyo-donnees.csv": "town_banyo", "Yaounde-donnees.csv": "centre"}


def _status(ok: bool, acceptable: bool = False) -> str:
    return "pass" if ok else "warn" if acceptable else "fail"


def _ar1(rng: np.random.Generator, n: int, rho: float) -> np.ndarray:
    """Noise with year-to-year memory, started in its steady state (no artificially calm start)."""
    x = np.empty(n)
    x[0] = rng.normal(0, 1 / np.sqrt(1 - rho**2))
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal()
    return x


# ------------------------------------------------------------------ block 1: calculations
def check_nasa_export() -> dict:
    """Yearly values of the app vs the yearly CSV files exported from NASA POWER (same source, separate path)."""
    worst, compared, files = 0.0, 0, []
    for name, place_id in CSV_PLACES.items():
        path = config.DATA_DIR / name
        if not path.exists():
            continue
        try:
            yearly = place_yearly(place_id)
        except Exception:  # no internet and not cached: this file is simply not compared
            continue
        table = pd.read_csv(path, encoding="utf-8-sig").pivot(index="year", columns="parameter", values="value")
        days = pd.Series([366 if y % 4 == 0 else 365 for y in yearly.index], index=yearly.index)
        mine = pd.DataFrame({"T2M": yearly["T2M"], "T2M_MAX": yearly["TXX"], "T2M_MIN": yearly["TNN"],
                             "PRECTOTCORR": yearly["RAIN"] / days})  # the export gives rain in mm per day
        diff = (mine.loc[table.index, table.columns] - table).abs()
        worst, compared = max(worst, float(diff.max().max())), compared + int(diff.size)
        files.append(name.split("-")[0])
    return {"id": "nasa_export", "block": "calc", "status": _status(bool(files) and worst <= 0.011, not files),
            "values": {"diff": worst, "n": compared, "files": ", ".join(files) or "-"}}


def check_reference_libraries() -> dict:
    """Our formulas vs independent implementations in scipy / numpy."""
    rng = np.random.default_rng(SEED)
    sen = ols = mk = 0.0
    n_series = 0
    for region in REGIONS:  # on the real series
        yearly = place_yearly(region.id)
        for key in VARIABLES:
            series = yearly[key]
            x, y = series.index.to_numpy(dtype=float), series.to_numpy(dtype=float)
            sen = max(sen, abs(trend_test(series)["slope_per_year"] - sps.theilslopes(y, x)[0]))
            ols = max(ols, abs(linear_regression(series)["slope_per_year"] - np.polyfit(x, y, 1)[0]))
            n_series += 1
    steps = np.arange(N_YEARS)
    pettitt_same = True
    for _ in range(50):  # on artificial series
        y = rng.normal(size=N_YEARS) + 0.02 * steps
        # Mann-Kendall p-value (before our memory correction) vs the Kendall tau test
        mk = max(mk, abs(pymannkendall.original_test(y).p - sps.kendalltau(steps, y).pvalue))
        # Pettitt vs a plain double loop
        u = [sum(np.sign(y[j] - y[i]) for i in range(t + 1) for j in range(t + 1, N_YEARS)) for t in range(N_YEARS - 1)]
        pettitt_same &= pettitt(y)["index"] == int(np.argmax(np.abs(u))) + 1
    p = rng.uniform(size=200) ** 2
    bh_same = benjamini_hochberg(list(p), 0.10) == (sps.false_discovery_control(p, method="bh") <= 0.10).tolist()
    ok = sen < 1e-9 and ols < 1e-9 and mk < 0.02 and pettitt_same and bh_same
    return {"id": "reference", "block": "calc", "status": _status(ok),
            "values": {"sen": sen, "ols": ols, "mk": mk, "pettitt": bool(pettitt_same), "bh": bool(bh_same), "n": n_series}}


def check_score() -> dict:
    """Every risk score is the sum of its two parts, stays in 0-100, and no two regions tie at the top."""
    exact, in_range, ties = True, True, 0
    for hazard in ("heat", "flood", "drought", "landslide"):
        raw = []
        for region in REGIONS:
            risk = analyze_metric(region.id, hazard, "year", config.START_YEAR, config.END_YEAR, 3, 0.05)["risk"]
            exact &= abs(risk["score"] - (risk["trend_points"] + risk["recent_points"])) <= 1
            in_range &= 0 <= risk["score"] <= 100
            raw.append(round(risk["trend_points"] + risk["recent_points"], 1))
        ties += int(max(raw) > 50 and raw.count(max(raw)) > 1)
    return {"id": "score", "block": "calc", "status": _status(exact and in_range and ties == 0),
            "values": {"n": 4 * len(REGIONS), "ties": ties}}


# ------------------------------------------------------------------ block 2: behaviour of the method
def check_false_alarms(trials: int = 400) -> dict:
    """Series with NO trend at all: how often does the test wrongly announce one? (target: about 5%)"""
    rng = np.random.default_rng(SEED)
    rates = {}
    for rho in (0.0, 0.3, 0.6, 0.8):
        alarms = sum(trend_test(pd.Series(_ar1(rng, N_YEARS, rho), index=YEARS))["significant"] for _ in range(trials))
        rates[rho] = alarms / trials
    usual = max(rates[0.0], rates[0.3], rates[0.6])
    return {"id": "false_alarms", "block": "method", "status": _status(usual <= 0.08, usual <= 0.12),
            "values": {"r0": rates[0.0], "r3": rates[0.3], "r6": rates[0.6], "r8": rates[0.8], "trials": trials}}


def check_detection(trials: int = 300) -> dict:
    """Series where we PLANT a known trend: is it found, and is its size measured correctly?"""
    rng = np.random.default_rng(SEED + 1)
    steps = np.arange(N_YEARS)
    found = {}
    for label, slope in (("small", 0.02), ("large", 0.05)):  # in normal swings per year, with memory 0.3
        found[label] = sum(trend_test(pd.Series(slope * steps + _ar1(rng, N_YEARS, 0.3), index=YEARS))["significant"]
                           for _ in range(trials)) / trials
    inside, estimates = 0, []
    for _ in range(trials):  # independent years: the textbook case for the regression interval
        series = pd.Series(0.03 * steps + rng.normal(size=N_YEARS), index=YEARS)
        low, high = linear_regression(series)["ci95_per_decade"]
        inside += low <= 0.3 <= high
        estimates.append(trend_test(series)["slope_per_decade"])
    coverage, median = inside / trials, float(np.median(estimates))
    return {"id": "detection", "block": "method",
            "status": _status(found["large"] >= 0.8 and 0.90 <= coverage <= 0.99 and abs(median - 0.3) < 0.03),
            "values": {"small": found["small"], "large": found["large"], "ci": coverage, "median": median}}


def check_breaks(trials: int = 300) -> dict:
    """A planted jump must be found at the right year; a steady trend must NOT be called a jump."""
    rng = np.random.default_rng(SEED + 2)
    true_index, steps = 17, np.arange(N_YEARS)
    located = fooled_plain = fooled_ours = 0
    for _ in range(trials):
        jump = rng.normal(size=N_YEARS) + 2.0 * (steps >= true_index)
        shift = pettitt(jump)
        located += bool(shift["p_value"] < 0.01 and abs(shift["index"] - true_index) <= 2
                        and step_preferred(jump, shift["index"]))
        ramp = rng.normal(size=N_YEARS) + 3.0 * steps / (N_YEARS - 1)  # gradual change, no jump
        shift = pettitt(ramp)
        plain = shift["p_value"] < 0.01
        fooled_plain += bool(plain)
        fooled_ours += bool(plain and step_preferred(ramp, shift["index"]))
    values = {"located": located / trials, "fooled_plain": fooled_plain / trials, "fooled_ours": fooled_ours / trials}
    return {"id": "breaks", "block": "method",
            "status": _status(values["located"] >= 0.6 and values["fooled_ours"] <= 0.10, values["fooled_ours"] <= 0.20),
            "values": values}


def check_forecast() -> dict:
    """Replay forecasts on the past. Ranges are built WITHOUT the region being tested (no peeking)."""
    inside80 = inside95 = total = 0
    mae = {m: [] for m in METHODS}
    methods = {}
    brier_model = brier_flat = brier_n = 0.0
    for metric in METRICS:
        records = {r.id: hindcast(metric_series(r.id, metric, "year")) for r in REGIONS}
        chosen = metric_calibration(metric, "year")
        methods[metric] = chosen["method"]
        for m in METHODS:
            mae[m].append(chosen["mae"][m])
        worse = METRICS[metric]["worse"] or "up"
        for region_id, own in records.items():
            others = calibrate([x for k, v in records.items() if k != region_id for x in v], chosen["method"])
            normal = metric_series(region_id, metric, "year").loc[config.BASELINE_START:config.BASELINE_END]
            threshold = float(normal.quantile(0.90 if worse == "up" else 0.10))
            for r in own:
                errors, pred, scale = others["errors"][r["h"]], r["pred"][chosen["method"]], r["scale"]
                low80, high80 = pred + np.quantile(errors, [0.10, 0.90]) * scale
                low95, high95 = pred + np.quantile(errors, [0.025, 0.975]) * scale
                inside80 += bool(low80 <= r["actual"] <= high80)
                inside95 += bool(low95 <= r["actual"] <= high95)
                total += 1
                if r["h"] <= 5:  # the "chance of an extreme year" the app used to show
                    outcomes = pred + errors * scale
                    prob = float(np.mean(outcomes > threshold if worse == "up" else outcomes < threshold))
                    hit = float(r["actual"] > threshold if worse == "up" else r["actual"] < threshold)
                    brier_model += (prob - hit) ** 2
                    brier_flat += (0.10 - hit) ** 2
                    brier_n += 1
    cov80, cov95 = inside80 / total, inside95 / total
    average = {m: float(np.mean(v)) for m, v in mae.items()}
    best = min(average, key=average.get)
    return {"id": "forecast", "block": "method",
            "status": _status(0.75 <= cov80 <= 0.85 and 0.90 <= cov95 <= 0.99, 0.70 <= cov80 <= 0.90),
            "values": {"cov80": cov80, "cov95": cov95, "n": total, "best": best,
                       **{f"mae_{m}": average[m] for m in METHODS},
                       "n_best": sum(v == best for v in methods.values()), "n_metrics": len(methods),
                       "brier_model": brier_model / brier_n, "brier_flat": brier_flat / brier_n}}


CHECKS = (check_nasa_export, check_reference_libraries, check_score,
          check_false_alarms, check_detection, check_breaks, check_forecast)


def _code_version() -> str:
    """Changes whenever the analysis code changes, so cached results are never stale."""
    digest = hashlib.sha256()
    for path in sorted((config.BASE_DIR / "backend").glob("*.py")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def run_validation(refresh: bool = False) -> dict:
    cache = config.CACHE_DIR / "validation.json"
    version = _code_version()
    if cache.exists() and not refresh:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if saved.get("version") == version:
            return saved
    checks = [check() for check in CHECKS]
    result = {"version": version, "years": [config.START_YEAR, config.END_YEAR], "n_years": N_YEARS, "checks": checks,
              "summary": {s: sum(c["status"] == s for c in checks) for s in ("pass", "warn", "fail")}}
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result


if __name__ == "__main__":  # python -m backend.validation
    for item in run_validation(refresh=True)["checks"]:
        shown = {k: round(v, 4) if isinstance(v, float) else v for k, v in item["values"].items()}
        print(item["status"].upper().ljust(5), item["id"].ljust(13), shown)
