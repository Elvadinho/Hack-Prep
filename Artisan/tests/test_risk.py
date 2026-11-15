import pytest

from backend.risk import HAZARDS, annual_indicator, risk_level, risk_score
from backend.stats import trend_test
from tests.conftest import make_daily


def test_warming_increases_extreme_heat_days_and_risk():
    series = annual_indicator(make_daily(warming_per_year=0.05), "heat")
    assert len(series) == 35
    assert series.iloc[-5:].mean() > series.iloc[:5].mean()
    risk = risk_score(series, trend_test(series), "up")
    assert risk["score"] >= 50
    assert risk["level"] in ("high", "very_high")


def test_no_change_gives_low_risk():
    series = annual_indicator(make_daily(warming_per_year=0.0, seed=3), "heat")
    risk = risk_score(series, trend_test(series), "up")
    assert risk["score"] < 50


@pytest.mark.parametrize("hazard", list(HAZARDS))
def test_every_hazard_gives_a_bounded_score(hazard):
    series = annual_indicator(make_daily(), hazard)
    risk = risk_score(series, trend_test(series), HAZARDS[hazard]["worse"])
    assert 0 <= risk["score"] <= 100


def test_unknown_hazard_is_rejected():
    with pytest.raises(KeyError):
        annual_indicator(make_daily(), "volcano")


@pytest.mark.parametrize(
    "score, level",
    [(0, "low"), (24, "low"), (25, "medium"), (49, "medium"), (50, "high"), (74, "high"), (75, "very_high"), (100, "very_high")],
)
def test_risk_levels(score, level):
    assert risk_level(score) == level

def test_weak_signal_that_reverses_after_2000_is_checked():
    """A 'possible' trend (0.05 <= p < 0.10) must go through the since-2000 check too.

    Before the fix it skipped the check (status 'no_trend', full weight), so a weak
    signal could earn more trend points than a strong one that failed the check.
    """
    import pandas as pd
    from backend.stats import robustness

    years = list(range(1981, 2026))
    falling_since_2000 = pd.Series([0.0 if y < 2000 else -0.1 * (y - 2000) for y in years], index=years)
    weak_rise = {"p_value": 0.07, "significant": False, "slope_per_year": 0.02}
    assert robustness(falling_since_2000, weak_rise)["status"] == "not_robust"
    no_signal = {**weak_rise, "p_value": 0.30}
    assert robustness(falling_since_2000, no_signal)["status"] == "no_trend"


def test_score_is_the_sum_of_its_parts():
    series = annual_indicator(make_daily(warming_per_year=0.05), "heat")
    risk = risk_score(series, trend_test(series), "up")
    assert abs(risk["score"] - (risk["trend_points"] + risk["recent_points"])) <= 1
    assert risk["explain"]["evidence_weight"] in (0.0, 0.5, 1.0)
