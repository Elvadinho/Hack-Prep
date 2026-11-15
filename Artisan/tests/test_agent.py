"""The AI agent: its tools compute on (fake) NASA data, and the loop follows the tool protocol."""
import json

import numpy as np
import pandas as pd
import pytest

from backend import agent
from tests.conftest import make_daily


@pytest.fixture
def fake_extra(monkeypatch):
    """Temperature, rain... and humidity/wind, all fake: no internet."""
    dates = pd.date_range("1991-01-01", "2025-12-31", freq="D")
    extra = pd.DataFrame({"RH2M": 70 + np.random.default_rng(0).normal(0, 5, len(dates)), "WS2M": 2.0}, index=dates)
    monkeypatch.setattr(agent, "_extra_daily", lambda place_id: extra)
    monkeypatch.setattr(agent, "load_daily", lambda region: make_daily(warming_per_year=0.05))


def test_places_are_found_with_or_without_accents():
    assert agent.resolve_place("kousseri") == "town_kousseri"
    assert agent.resolve_place("Extrême-Nord") == "extreme_nord"
    with pytest.raises(ValueError):
        agent.resolve_place("Paris")


def test_short_period_gives_values_and_normal_instead_of_a_trend(fake_extra):
    result = agent.period_statistics("centre", 2012, 2018, ["max_temperature", "humidity"])
    heat = result["variables"]["max_temperature"]
    assert heat["n_years"] == 7 and "trend_note" in heat and len(heat["values"]) == 7
    assert heat["difference_from_normal"] > 0  # the fake data warms by 0.05 °C a year
    assert result["variables"]["humidity"]["unit"] == "%"


def test_long_period_has_a_trend_and_tools_report_errors_cleanly(fake_extra):
    result = agent.period_statistics("centre", 1995, 2025, ["temperature"])
    assert result["variables"]["temperature"]["trend_per_decade"] == pytest.approx(0.5, abs=0.15)
    assert "error" in agent.run_tool("period_statistics", {"place": "centre", "start": 2030, "end": 2040, "variables": ["rain"]})
    assert "error" in agent.run_tool("no_such_tool", {})


def test_agent_loop_calls_a_tool_then_answers(fake_extra):
    """A scripted model: first asks for a tool, then answers using its result."""
    seen = []

    def scripted(messages, **_):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            return {"model": "test", "answer": json.dumps({"tool": "compare_periods", "args": {
                "place": "Yaoundé", "variable": "temperature", "a_start": 1991, "a_end": 2000, "b_start": 2016, "b_end": 2025}})}
        return {"model": "test", "answer": '```json\n{"answer": "Plus chaud de 1 °C."}\n```'}

    out = agent.run_agent("Compare les années 90 et aujourd'hui", "fr", region="centre", llm=scripted)
    assert out["answer"] == "Plus chaud de 1 °C."
    assert [s["tool"] for s in out["steps"]] == ["compare_periods"] and out["steps"][0]["ok"]
    assert "TOOL RESULT (compare_periods)" in seen[1] and "difference_b_minus_a" in seen[1]


def test_plain_text_reply_is_accepted_as_the_answer(fake_extra):
    out = agent.run_agent("Bonjour", llm=lambda messages, **_: {"model": "test", "answer": "Bonjour !"})
    assert out == {"answer": "Bonjour !", "model": "test", "steps": []}
