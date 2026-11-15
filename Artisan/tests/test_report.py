from fastapi.testclient import TestClient

from backend.main import app
from backend.towns import PLACES

client = TestClient(app)


def test_kousseri_is_available():
    assert "town_kousseri" in PLACES
    assert len(client.get("/api/places").json()) >= 50


def test_report_has_table_facts_and_recommendations(fake_power):
    data = client.get("/api/report", params={"place": "town_kousseri", "start": 1981, "end": 2025, "lang": "fr"}).json()
    keys = [v["key"] for v in data["variables"]]
    assert keys == ["T2M", "TXX", "TNN", "RAIN", "HOT", "SOIL"]
    t2m = data["variables"][0]
    assert t2m["min"] <= t2m["median"] <= t2m["max"]
    assert t2m["trend"]["significant"]  # fake data warms by 0.5 °C/decade
    assert t2m["first_period"] == [1991, 2000] and t2m["last_period"] == [2016, 2025]  # fake data starts 1991
    assert data["period"] == [1991, 2025]  # the report states the years actually covered
    assert len(data["facts"]) >= 6
    assert [axis["axis"] for axis in data["recommendations"]] == ["A", "B", "C", "D"]


def test_report_follows_the_year_filter(fake_power):
    data = client.get("/api/report", params={"place": "centre", "start": 2000, "end": 2020, "lang": "en"}).json()
    assert data["period"] == [2000, 2020] and data["n_years"] == 21
    assert data["variables"][0]["series"]["years"][0] == 2000


def test_report_rejects_unknown_place_and_short_period(fake_power):
    assert client.get("/api/report", params={"place": "paris"}).status_code == 404
    assert client.get("/api/report", params={"place": "centre", "start": 2020, "end": 2025}).status_code == 422


def test_first_and_last_periods_never_overlap_and_slope_has_an_interval():
    import pandas as pd
    from backend.report import _variable_block, linear_regression

    years = list(range(2005, 2021))  # 16 years: two 10-year windows would overlap
    series = pd.Series([20 + 0.05 * (y - 2005) + 0.1 * ((y * 7) % 3 - 1) for y in years], index=years)
    block = _variable_block("T2M", series, "en")
    assert block["first_period"][1] < block["last_period"][0]

    ols = linear_regression(series)
    low, high = ols["ci95_per_decade"]
    assert low < ols["slope_per_decade"] < high
    assert abs(ols["slope_per_decade"] - 0.5) < 0.15  # true slope: 0.05 per year


def test_score_has_no_ceiling_ties():
    from backend.risk import points

    assert points(2.0, 2.0) == 45
    assert points(2.5, 2.0) < points(3.5, 2.0) < 50
    assert points(-1.0, 2.0) == 0


def test_exceptional_years_are_measured_around_the_trend():
    """On a steady trend the last years are high but not 'exceptional'; a real spike is."""
    import pandas as pd
    from backend.report import _variable_block

    years = list(range(1981, 2026))
    values = [20 + 0.05 * (y - 1981) + 0.05 * ((y * 7) % 5 - 2) for y in years]
    values[20] += 1.5  # one real spike in 2001
    block = _variable_block("T2M", pd.Series(values, index=years), "en")
    assert [o["year"] for o in block["outliers"]] == [2001]


def test_step_test_separates_a_jump_from_a_gradual_change():
    import numpy as np
    from backend.discover import pettitt, step_preferred

    rng = np.random.default_rng(3)
    steps = np.arange(45)
    jump = rng.normal(size=45) + 2.5 * (steps >= 17)
    ramp = rng.normal(size=45) + 3.0 * steps / 44
    assert step_preferred(jump, pettitt(jump)["index"])
    assert not step_preferred(ramp, pettitt(ramp)["index"])


def test_validation_api_lists_every_check(fake_power, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import validation
    from backend.main import app

    fake = {"version": "x", "years": [1981, 2025], "n_years": 45, "summary": {"pass": 1, "warn": 0, "fail": 0},
            "checks": [{"id": "score", "block": "calc", "status": "pass", "values": {"n": 40, "ties": 0}}]}
    monkeypatch.setattr(validation, "run_validation", lambda refresh=False: fake)
    data = TestClient(app).get("/api/validation").json()
    assert data["checks"][0]["status"] == "pass"
