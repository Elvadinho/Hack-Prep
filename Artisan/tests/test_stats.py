import numpy as np
import pandas as pd
import pytest

from backend.stats import anomaly, confidence_label, trend_line, trend_test

YEARS = range(1991, 2026)  # 35 years, like our NASA POWER period


def ar1_noise(rng, n, rho=0.3, sigma=1.0):
    """Red noise: each year partly remembers the previous one (like real climate)."""
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = rho * noise[i - 1] + rng.normal(0, sigma)
    return noise


def test_clear_warming_is_detected():
    rng = np.random.default_rng(1)
    values = 24 + 0.05 * np.arange(35) + rng.normal(0, 0.2, 35)  # +0.5 per decade
    result = trend_test(pd.Series(values, index=YEARS))
    assert result["significant"]
    assert result["direction"] == "increasing"
    assert result["slope_per_decade"] == pytest.approx(0.5, abs=0.15)


def test_decreasing_trend_is_detected():
    values = 100 - 1.0 * np.arange(35)
    result = trend_test(pd.Series(values, index=YEARS))
    assert result["direction"] == "decreasing"


def test_pure_noise_rarely_looks_significant():
    """False-alarm check: with NO real trend, about 5% of series may look significant.

    This is the check the MVP's method failed (9-23%). We allow up to 8%.
    """
    for rho in (0.0, 0.3, 0.6):
        rng = np.random.default_rng(42)
        trials = 500
        false_alarms = sum(
            trend_test(pd.Series(ar1_noise(rng, 35, rho=rho), index=YEARS))["significant"]
            for _ in range(trials)
        )
        assert false_alarms / trials <= 0.08, f"too many false alarms at rho={rho}"


def test_too_short_or_gappy_series_is_rejected():
    with pytest.raises(ValueError):
        trend_test(pd.Series([1.0, 2.0, 3.0], index=[2000, 2001, 2002]))
    with pytest.raises(ValueError):
        trend_test(pd.Series(range(12), index=[*range(2000, 2011), 2015]))


def test_confidence_labels():
    assert confidence_label(0.001) == "very_likely"
    assert confidence_label(0.03) == "likely"
    assert confidence_label(0.08) == "possible"
    assert confidence_label(0.5) == "chance"


def test_projection_extends_to_2030():
    values = 24 + 0.05 * np.arange(35)
    series = pd.Series(values, index=YEARS)
    line = trend_line(series, trend_test(series), project_to=2030)
    assert line["years"][-1] == 2030
    assert line["projected_from"] == 2026
    assert all(lo <= t <= up for lo, t, up in zip(line["lower"], line["trend"], line["upper"]))


def test_anomaly_z_score():
    baseline = pd.Series([10.0, 12.0, 14.0])  # mean 12, std 2
    result = anomaly(16.0, baseline)
    assert result["z_score"] == pytest.approx(2.0)
    assert result["percentile"] == pytest.approx(100.0)