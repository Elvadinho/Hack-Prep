"""Shared test helpers: fake NASA POWER data so tests never call the internet."""
import numpy as np
import pandas as pd
import pytest


def make_daily(warming_per_year: float = 0.0, seed: int = 0) -> pd.DataFrame:
    """35 years of fake daily data shaped like NASA POWER output."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1991-01-01", "2025-12-31", freq="D")
    years_since_start = (dates.year - 1991).to_numpy()
    n = len(dates)
    return pd.DataFrame(
        {
            "T2M": 24 + warming_per_year * years_since_start + rng.normal(0, 1, n),
            "T2M_MAX": 30 + warming_per_year * years_since_start + rng.normal(0, 1.5, n),
            "T2M_MIN": 19 + warming_per_year * years_since_start + rng.normal(0, 1.5, n),
            "PRECTOTCORR": rng.gamma(0.6, 8, n),
            "GWETROOT": np.clip(0.6 + rng.normal(0, 0.05, n), 0, 1),
        },
        index=pd.DatetimeIndex(dates, name="date"),
    )


@pytest.fixture
def fake_power(monkeypatch):
    """Replace the real NASA download with fake data in every module that loads it."""
    from backend import advice, discover, explore, report, risk

    fake = lambda region: make_daily(warming_per_year=0.05)  # noqa: E731
    for module in (risk, explore, advice, discover, report):
        monkeypatch.setattr(module, "load_daily", fake)
    caches = (risk.analyze, explore.metric_series, explore.analyze_metric, explore.table_metric, explore.metric_calibration,
              advice.monthly_climate, discover.discoveries, report.place_yearly, report.variable_calibration)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()