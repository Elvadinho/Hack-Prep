"""Discovery engine: let the NASA data tell us things we did not ask about.

Instead of only testing the 4 hazards we chose, we scan EVERY combination of
  4 NASA POWER variables x 5 periods (year + 4 seasons) x 10 regions = 200 series
and look for:
  - strong trends            (what is changing fastest, relative to normal swings)
  - opposite trends          (same variable rising in one region, falling in another)
  - seasonal shifts          (one season changing while the yearly average is not)
  - regime shifts            (a year when the average suddenly jumped - Pettitt test)
  - recent records           (the latest year is the highest/lowest in 45 years)

Testing 200 series means some will look "significant" by pure luck, so we
control the False Discovery Rate with the Benjamini-Hochberg method.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from backend.nasa_power import load_daily
from backend.regions import REGIONS, region_to_dict
from backend.stats import robustness, trend_line, trend_test

FDR_Q = 0.10  # accept that at most ~10% of reported discoveries could be false
PROJECT_TO = 2030

VARIABLES: dict[str, dict] = {
    "T2M": {"fr": "température moyenne", "en": "average temperature", "unit": "°C", "how": "mean"},
    "T2M_MAX": {"fr": "température maximale", "en": "maximum temperature", "unit": "°C", "how": "mean"},
    "PRECTOTCORR": {"fr": "pluie totale", "en": "total rainfall", "unit": "mm", "how": "sum"},
    "GWETROOT": {"fr": "humidité du sol", "en": "soil moisture", "unit": "0-1", "how": "mean"},
}

PERIODS: dict[str, dict] = {
    "year": {"fr": "sur l'année", "en": "over the year", "months": list(range(1, 13))},
    "DJF": {"fr": "en déc-jan-fév", "en": "in Dec-Jan-Feb", "months": [12, 1, 2]},
    "MAM": {"fr": "en mars-avr-mai", "en": "in Mar-Apr-May", "months": [3, 4, 5]},
    "JJA": {"fr": "en juin-juil-août", "en": "in Jun-Jul-Aug", "months": [6, 7, 8]},
    "SON": {"fr": "en sept-oct-nov", "en": "in Sep-Oct-Nov", "months": [9, 10, 11]},
}


# ---------------------------------------------------------------- statistics
def benjamini_hochberg(p_values: list[float], q: float = FDR_Q) -> list[bool]:
    """Which tests remain significant after False Discovery Rate control."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    thresholds = q * np.arange(1, m + 1) / m
    passed = p[order] <= thresholds
    keep = np.zeros(m, dtype=bool)
    if passed.any():
        last = np.max(np.nonzero(passed)[0])
        keep[order[: last + 1]] = True
    return keep.tolist()


def pettitt(values: np.ndarray) -> dict:
    """Pettitt (1979) change-point test: the year where the level shifted most."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    signs = np.sign(x[None, :] - x[:, None])  # signs[i, j] = sign(x_j - x_i)
    u = np.array([signs[: t + 1, t + 1 :].sum() for t in range(n - 1)])
    k = int(np.argmax(np.abs(u)))
    big_k = float(abs(u[k]))
    p_value = float(min(1.0, 2 * np.exp(-6 * big_k**2 / (n**3 + n**2))))
    return {"index": k + 1, "p_value": p_value}  # first index of the "after" segment


def step_preferred(values: np.ndarray, index: int, margin: float = 6.0) -> bool:
    """Is a sudden jump at `index` a better description than a steady trend alone?

    Pettitt cannot tell a jump from a gradual trend (a pure trend triggers it most
    of the time), so we fit both and compare them with the BIC, which penalises
    the extra parameter: line only  vs  line + step.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    steps = np.arange(n)
    line = np.column_stack([np.ones(n), steps])
    with_step = np.column_stack([line, (steps >= index).astype(float)])

    def bic(design: np.ndarray) -> float:
        residuals = x - design @ np.linalg.lstsq(design, x, rcond=None)[0]
        return n * np.log(max(float(residuals @ residuals), 1e-12) / n) + design.shape[1] * np.log(n)

    # BIC difference: above 2 = positive evidence, above 6 = strong evidence (Kass and Raftery, 1995)
    return bic(with_step) < bic(line) - margin


# ---------------------------------------------------------------- series
def period_series(daily: pd.DataFrame, variable: str, period: str) -> pd.Series:
    """Yearly series of one variable for one period (December counts toward next year's DJF)."""
    column = daily[variable]
    months = PERIODS[period]["months"]
    selected = column[column.index.month.isin(months)]
    shift = (selected.index.month == 12).astype(int) if period == "DJF" else 0
    grouped = selected.groupby(selected.index.year + shift)
    series = grouped.sum() if VARIABLES[variable]["how"] == "sum" else grouped.mean()
    if period == "DJF":  # first and last DJF are incomplete
        series = series.iloc[1:-1]
    series.index.name = "year"
    return series.astype(float)


def _scan() -> list[dict]:
    """Run the trend test on all 200 series."""
    rows = []
    for region in REGIONS:
        daily = load_daily(region)
        for variable in VARIABLES:
            for period in PERIODS:
                series = period_series(daily, variable, period)
                trend = trend_test(series)
                std = float(series.std(ddof=1))
                rows.append({
                    "region": region,
                    "variable": variable,
                    "period": period,
                    "series": series,
                    "trend": trend,
                    "size": trend["change_over_period"] / std if std > 0 else 0.0,
                })
    keep = benjamini_hochberg([row["trend"]["p_value"] for row in rows])
    for row, kept in zip(rows, keep):
        row["discovery"] = kept
    return rows


# ---------------------------------------------------------------- wording
def _fmt(value: float, unit: str) -> str:
    if unit == "0-1":
        return f"{value:+.3f}"
    return f"{value:+.1f} {unit}"


def _evidence(row: dict) -> dict:
    series = row["series"]
    return {
        "region": region_to_dict(row["region"]),
        "variable": row["variable"],
        "variable_label": {lang: VARIABLES[row["variable"]][lang] for lang in ("fr", "en")},
        "period": row["period"],
        "period_label": {lang: PERIODS[row["period"]][lang] for lang in ("fr", "en")},
        "unit": VARIABLES[row["variable"]]["unit"],
        "years": [int(y) for y in series.index],
        "values": series.round(3).tolist(),
        "trend": row["trend"],
        "robustness": robustness(series, row["trend"]),
        "line": trend_line(series, row["trend"], project_to=PROJECT_TO),
    }


def _labels(row: dict, lang: str) -> tuple[str, str, str]:
    region = row["region"].name_fr if lang == "fr" else row["region"].name_en
    return region, VARIABLES[row["variable"]][lang], PERIODS[row["period"]][lang]


def _strong_trend(row: dict) -> dict:
    t, unit = row["trend"], VARIABLES[row["variable"]]["unit"]
    evidence = _evidence(row)
    projection = evidence["line"]["trend"][-1]
    shown_unit = "" if unit == "0-1" else f" {unit}"
    text = {}
    for lang in ("fr", "en"):
        region, var, per = _labels(row, lang)
        if lang == "fr":
            verb = "augmente" if t["slope_per_year"] > 0 else "diminue"
            text[lang] = (
                f"{region} : la {var} {per} {verb} de {_fmt(t['slope_per_decade'], unit)} par décennie "
                f"(p = {t['p_value']:.4f}). Si la tendance continue : ~{projection:.2f}{shown_unit} en {PROJECT_TO}."
            )
        else:
            verb = "is rising" if t["slope_per_year"] > 0 else "is falling"
            text[lang] = (
                f"{region}: {var} {per} {verb} by {_fmt(t['slope_per_decade'], unit)} per decade "
                f"(p = {t['p_value']:.4f}). If the trend continues: ~{projection:.2f}{shown_unit} by {PROJECT_TO}."
            )
    status = evidence["robustness"]["status"]
    text["fr"] += " " + ROBUST_TEXT[status]["fr"]
    text["en"] += " " + ROBUST_TEXT[status]["en"]
    score = abs(row["size"]) * (1.0 if status == "robust" else 0.5)  # robust findings first
    return {"type": "strong_trend", "score": score, "text": text, "evidence": [evidence]}


ROBUST_TEXT = {
    "robust": {"fr": "✔ Confirmé aussi depuis 2000.", "en": "✔ Also confirmed since 2000."},
    "consistent": {"fr": "≈ Même sens depuis 2000, mais moins net.", "en": "≈ Same direction since 2000, but weaker."},
    "not_robust": {"fr": "⚠ Ne se confirme pas depuis 2000 : prudence.", "en": "⚠ Not confirmed since 2000: treat with caution."},
    "no_trend": {"fr": "", "en": ""},
}


def _opposite(up: dict, down: dict) -> dict:
    text = {}
    for lang in ("fr", "en"):
        r_up, var, per = _labels(up, lang)
        r_down = _labels(down, lang)[0]
        if lang == "fr":
            text[lang] = (
                f"Même variable, sens opposés : la {var} {per} augmente en {r_up} "
                f"mais diminue en {r_down}. Une seule réponse nationale ne suffit pas."
            )
        else:
            text[lang] = (
                f"Same variable, opposite directions: {var} {per} is rising in {r_up} "
                f"but falling in {r_down}. One national response will not fit all regions."
            )
    score = abs(up["size"]) + abs(down["size"])
    return {"type": "opposite_trends", "score": score, "text": text, "evidence": [_evidence(up), _evidence(down)]}


def _seasonal_shift(season_row: dict, year_row: dict) -> dict:
    t, unit = season_row["trend"], VARIABLES[season_row["variable"]]["unit"]
    text = {}
    for lang in ("fr", "en"):
        region, var, per = _labels(season_row, lang)
        if lang == "fr":
            sens = "hausse" if t["slope_per_year"] > 0 else "baisse"
            text[lang] = (
                f"{region} : changement caché dans une saison. La {var} {per} est en {sens} "
                f"({_fmt(t['slope_per_decade'], unit)}/décennie) alors que la moyenne annuelle ne montre "
                f"pas de tendance détectable : le changement est concentré sur cette saison."
            )
        else:
            sens = "rising" if t["slope_per_year"] > 0 else "falling"
            text[lang] = (
                f"{region}: a change hidden inside one season. {var.capitalize()} {per} is {sens} "
                f"({_fmt(t['slope_per_decade'], unit)}/decade) while the yearly average shows no detectable trend: "
                f"the change is concentrated in this season."
            )
    return {
        "type": "seasonal_shift",
        "score": abs(season_row["size"]),
        "text": text,
        "evidence": [_evidence(season_row), _evidence(year_row)],
    }


def _regime_shift(row: dict, shift: dict) -> dict:
    series = row["series"]
    year = int(series.index[shift["index"]])
    before = float(series.iloc[: shift["index"]].mean())
    after = float(series.iloc[shift["index"] :].mean())
    unit = VARIABLES[row["variable"]]["unit"]
    shown_unit = "" if unit == "0-1" else f" {unit}"
    text = {}
    for lang in ("fr", "en"):
        region, var, per = _labels(row, lang)
        if lang == "fr":
            text[lang] = (
                f"{region} : rupture vers {year}. La {var} {per} est passée d'une moyenne de "
                f"{before:.2f} à {after:.2f}{shown_unit} (test de Pettitt, p = {shift['p_value']:.4f})."
            )
        else:
            text[lang] = (
                f"{region}: a break around {year}. {var.capitalize()} {per} jumped from an average of "
                f"{before:.2f} to {after:.2f}{shown_unit} (Pettitt test, p = {shift['p_value']:.4f})."
            )
    evidence = _evidence(row)
    evidence["change_year"] = year
    evidence["before_after"] = [before, after]
    score = abs(after - before) / max(float(series.std(ddof=1)), 1e-9)
    return {"type": "regime_shift", "score": score, "text": text, "evidence": [evidence]}


def _record(row: dict, kind: str) -> dict:
    series = row["series"]
    unit = VARIABLES[row["variable"]]["unit"]
    shown_unit = "" if unit == "0-1" else f" {unit}"
    year, value = int(series.index[-1]), float(series.iloc[-1])
    first = int(series.index[0])
    text = {}
    for lang in ("fr", "en"):
        region, var, per = _labels(row, lang)
        if lang == "fr":
            mot = "la plus élevée" if kind == "max" else "la plus basse"
            text[lang] = f"{region} : en {year}, la {var} {per} ({value:.2f}{shown_unit}) est {mot} depuis {first}."
        else:
            word = "highest" if kind == "max" else "lowest"
            text[lang] = f"{region}: in {year}, {var} {per} ({value:.2f}{shown_unit}) was the {word} since {first}."
    past = series.iloc[:-1]
    z = abs(value - past.mean()) / max(float(past.std(ddof=1)), 1e-9)
    return {"type": "record", "score": float(z), "text": text, "evidence": [_evidence(row)]}


def _data_alerts(yearly: dict, shifts: dict, min_regions: int = 3) -> list[dict]:
    """A jump in the SAME year in many distant regions is suspicious.

    Real climate rarely shifts everywhere at once; a change in the observations
    feeding a reanalysis (new satellites, new instruments) can. We flag it so
    users treat those trends with care (cross-checking with satellite data is future work).
    """
    alerts = []
    for variable in VARIABLES:
        years = {rid: int(yearly[(rid, v)]["series"].index[s["index"]])
                 for (rid, v), s in shifts.items() if v == variable}
        if not years:
            continue
        counts = {y: sum(abs(other - y) <= 1 for other in years.values()) for y in set(years.values())}
        year, count = max(counts.items(), key=lambda item: item[1])
        if count < min_regions:
            continue
        regions = [rid for rid, y in years.items() if abs(y - year) <= 1]
        steps = []
        for rid in regions:
            row, shift = yearly[(rid, variable)], shifts[(rid, variable)]
            series = row["series"]
            steps.append(float(series.iloc[shift["index"]:].mean() - series.iloc[: shift["index"]].mean()))
        unit = VARIABLES[variable]["unit"]
        step = f"{np.mean(steps):+.2f}" + ("" if unit == "0-1" else f" {unit}")
        text = {
            "fr": (
                f"À savoir sur les données : la {VARIABLES[variable]['fr']} change brusquement de niveau ({step} en moyenne) "
                f"vers {year} dans {count} régions sur 10. Ailleurs, le changement est progressif. Un changement des "
                f"observations utilisées par la réanalyse MERRA-2 est une cause possible, le fort El Niño de 1997-98 en est une autre. "
                f"Chaque tendance est donc revérifiée à partir de 2000."
            ),
            "en": (
                f"Good to know about the data: {VARIABLES[variable]['en']} changes level abruptly ({step} on average) around {year} "
                f"in {count} of 10 regions. Elsewhere the change is gradual. A change in the observations fed into the "
                f"MERRA-2 reanalysis is one possible cause, the strong 1997-98 El Niño is another. "
                f"Every trend is therefore re-checked from 2000 onward."
            ),
        }
        evidence = [_evidence(yearly[(rid, variable)]) for rid in regions[:4]]
        for item in evidence:
            item["change_year"] = year
        alerts.append({"type": "data_alert", "score": float(count), "text": text, "evidence": evidence,
                       "year": year, "regions": regions, "variable": variable})
    return alerts


# ---------------------------------------------------------------- main entry
@lru_cache(maxsize=1)
def discoveries(limit_per_type: int = 6) -> dict:
    """All automatic findings, strongest first, grouped by type."""
    rows = _scan()
    found = [r for r in rows if r["discovery"]]
    kinds = ("data_alert", "strong_trend", "opposite_trends", "seasonal_shift", "regime_shift", "record")
    results: dict[str, list] = {key: [] for key in kinds}

    for row in found:
        results["strong_trend"].append(_strong_trend(row))

    groups: dict[tuple, list] = {}
    for row in found:
        groups.setdefault((row["variable"], row["period"]), []).append(row)
    for group in groups.values():
        ups = [r for r in group if r["trend"]["slope_per_year"] > 0]
        downs = [r for r in group if r["trend"]["slope_per_year"] < 0]
        if ups and downs:
            results["opposite_trends"].append(
                _opposite(max(ups, key=lambda r: r["size"]), min(downs, key=lambda r: r["size"]))
            )

    yearly = {(r["region"].id, r["variable"]): r for r in rows if r["period"] == "year"}
    shifts = {}
    for key, row in yearly.items():
        shift = pettitt(row["series"].to_numpy())
        inside = 3 <= shift["index"] <= len(row["series"]) - 3
        if shift["p_value"] < 0.01 and inside and step_preferred(row["series"].to_numpy(), shift["index"], margin=2.0):
            shifts[key] = shift  # a jump describes the series better than a gradual trend alone

    for row in found:
        if row["period"] == "year":
            continue
        key = (row["region"].id, row["variable"])
        year_row = yearly[key]
        # "hidden in one season": yearly average flat AND no big jump explaining it
        if year_row["trend"]["p_value"] >= 0.10 and key not in shifts:
            results["seasonal_shift"].append(_seasonal_shift(row, year_row))

    for key, shift in shifts.items():  # announced as a "break" only with strong evidence
        if step_preferred(yearly[key]["series"].to_numpy(), shift["index"]):
            results["regime_shift"].append(_regime_shift(yearly[key], shift))
    results["data_alert"] = _data_alerts(yearly, shifts)

    for row in yearly.values():
        series = row["series"]
        if series.iloc[-1] >= series.max():
            results["record"].append(_record(row, "max"))
        elif series.iloc[-1] <= series.min():
            results["record"].append(_record(row, "min"))

    for key in results:
        results[key] = sorted(results[key], key=lambda d: -d["score"])[:limit_per_type]

    return {
        "tested": len(rows),
        "significant_raw": sum(r["trend"]["p_value"] < 0.05 for r in rows),
        "significant_after_fdr": len(found),
        "fdr_q": FDR_Q,
        "findings": results,
    }
