import numpy as np

from backend.discover import benjamini_hochberg, period_series, pettitt
from tests.conftest import make_daily


def test_fdr_keeps_strong_results_and_drops_borderline_ones():
    p_values = [0.0001, 0.001, 0.04, 0.5, 0.9]
    keep = benjamini_hochberg(p_values, q=0.05)
    assert keep[:2] == [True, True]
    assert keep[3:] == [False, False]


def test_fdr_with_nothing_significant():
    assert benjamini_hochberg([0.5, 0.6, 0.9]) == [False, False, False]


def test_pettitt_finds_a_jump():
    values = np.r_[np.full(20, 10.0), np.full(20, 12.0)] + np.random.default_rng(0).normal(0, 0.3, 40)
    result = pettitt(values)
    assert result["index"] == 20
    assert result["p_value"] < 0.01


def test_pettitt_ignores_pure_noise():
    values = np.random.default_rng(1).normal(0, 1, 40)
    assert pettitt(values)["p_value"] > 0.05


def test_seasonal_series_are_complete_years():
    daily = make_daily()
    assert len(period_series(daily, "T2M", "year")) == 35
    djf = period_series(daily, "PRECTOTCORR", "DJF")
    assert djf.index[0] == 1992 and djf.index[-1] == 2025  # incomplete first/last winters dropped
    assert np.all(np.diff(djf.index) == 1)
