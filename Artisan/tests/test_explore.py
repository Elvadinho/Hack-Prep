import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.forecast import backtest, calibrate, forecast, hindcast, point_forecast
from backend.main import app

YEARS = range(1981, 2026)
client = TestClient(app)


def warming_series(seed=0, slope=0.05, noise=0.2):
    rng = np.random.default_rng(seed)
    return pd.Series(24 + slope * np.arange(len(YEARS)) + rng.normal(0, noise, len(YEARS)), index=YEARS)


def test_trend_method_continues_a_clear_trend():
    series = warming_series()
    assert point_forecast(series, "trend", 5)[-1] > series.iloc[-10:].mean()
    assert point_forecast(series, "persistence", 2) == [series.iloc[-1]] * 2


def test_method_is_chosen_by_replaying_the_past():
    # strong steady warming: extrapolating the trend must win; pure noise: the long-term mean must win
    assert calibrate(hindcast(warming_series(slope=0.08, noise=0.15)))["method"] == "trend"
    noise = pd.Series(np.random.default_rng(5).normal(0, 1, len(YEARS)), index=YEARS)
    assert calibrate(hindcast(noise))["method"] in ("mean", "smooth")


def test_forecast_ranges_come_from_past_errors_and_respect_limits():
    series = warming_series()
    calibration = calibrate(hindcast(series))
    fc = forecast(series, 5, calibration, "°C")
    assert fc["years"] == [2026, 2027, 2028, 2029, 2030]
    assert all(lo95 <= lo80 <= m <= hi80 <= hi95 for lo95, lo80, m, hi80, hi95
               in zip(fc["lo95"], fc["lo80"], fc["mean"], fc["hi80"], fc["hi95"]))
    wet = pd.Series(np.clip(0.95 + np.random.default_rng(1).normal(0, 0.05, len(YEARS)), 0, 1), index=YEARS)
    soil = forecast(wet, 5, calibrate(hindcast(wet)), "0-1")
    assert max(soil["hi95"]) <= 1.0 and min(soil["lo95"]) >= 0.0  # soil wetness stays between 0 and 1


def test_eighty_percent_range_holds_on_series_it_was_not_built_from():
    """The honesty check: ranges built from 6 series must contain ~80% of the values of 6 other series."""
    def make(seed):
        rng = np.random.default_rng(seed)
        noise = np.zeros(len(YEARS))
        for i in range(1, len(YEARS)):
            noise[i] = 0.5 * noise[i - 1] + rng.normal(0, 1)
        return pd.Series(20 + 0.03 * np.arange(len(YEARS)) + noise, index=YEARS)

    calibration = calibrate([r for seed in range(6) for r in hindcast(make(seed))])
    inside = total = 0
    for seed in range(100, 106):
        for r in hindcast(make(seed)):
            errors = calibration["errors"][r["h"]]
            pred = r["pred"][calibration["method"]]
            low, high = pred + np.quantile(errors, 0.10) * r["scale"], pred + np.quantile(errors, 0.90) * r["scale"]
            inside += low <= r["actual"] <= high
            total += 1
    assert 0.70 <= inside / total <= 0.90


def test_backtest_compares_with_the_average_and_with_last_year():
    result = backtest(warming_series(slope=0.08, noise=0.15), 3, "trend")
    assert result["n_forecasts"] > 0
    assert result["skill"] > 0 and result["skill_persistence"] is not None


def test_explore_api_with_filters(fake_power):
    params = {"region": "centre", "metric": "T2M", "period": "JJA", "start": 1995, "end": 2025, "horizon": 3, "alpha": 0.01}
    data = client.get("/api/explore", params=params).json()
    assert data["range"] == [1995, 2025]
    assert data["forecast"]["years"] == [2026, 2027, 2028]
    assert data["alpha"] == 0.01


def test_explore_api_rejects_bad_filters(fake_power):
    base = {"region": "centre", "metric": "heat"}
    assert client.get("/api/explore", params={**base, "horizon": 50}).status_code == 422
    assert client.get("/api/explore", params={**base, "start": 2020, "end": 2025}).status_code == 422  # < 10 years
    assert client.get("/api/explore", params={**base, "period": "JJA"}).status_code == 422  # hazards are yearly
    assert client.get("/api/explore", params={"region": "centre", "metric": "volcano"}).status_code == 422


def test_table_has_ten_regions(fake_power):
    rows = client.get("/api/table", params={"metric": "drought", "horizon": 2}).json()
    assert len(rows) == 10
    assert all(row["risk_score"] is not None for row in rows)


def test_advice_is_concrete(fake_power):
    data = client.get("/api/advice", params={"region": "littoral", "hazard": "flood", "lang": "en"}).json()
    assert data["priority"] in ("urgent", "prepare", "watch")
    assert len(data["actions"]) >= 3
    assert "month" in data["timing"].lower()
    assert len(data["facts"]) >= 3


def test_year_filter_does_not_shrink_the_normal_period(fake_power):
    """The risk score always compares with the full 1991-2020 normal, whatever years are displayed."""
    from backend.explore import analyze_metric

    late = analyze_metric("centre", "heat", "year", 2014, 2025, 3, 0.05)
    full = analyze_metric("centre", "heat", "year", 1991, 2025, 3, 0.05)
    assert late["risk"]["recent_anomaly"]["baseline_mean"] == pytest.approx(full["risk"]["recent_anomaly"]["baseline_mean"])
