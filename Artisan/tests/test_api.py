from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_regions():
    response = client.get("/api/regions")
    assert response.status_code == 200
    assert len(response.json()) == 10


def test_risk_map_has_all_regions(fake_power):
    response = client.get("/api/risk", params={"hazard": "heat"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 10
    assert all(0 <= row["score"] <= 100 for row in rows)


def test_analysis_contains_chart_data(fake_power):
    data = client.get("/api/analysis", params={"region": "centre", "hazard": "flood"}).json()
    assert len(data["series"]["years"]) == len(data["series"]["values"]) == 35
    assert data["line"]["years"][-1] == 2030
    assert "p_value" in data["trend"]


def test_bad_inputs_are_rejected(fake_power):
    assert client.get("/api/analysis", params={"region": "paris", "hazard": "heat"}).status_code == 404
    assert client.get("/api/analysis", params={"region": "centre", "hazard": "volcano"}).status_code == 422
    empty = {"region": "centre", "hazard": "heat", "lang": "fr", "question": ""}
    assert client.post("/api/chat", json=empty).status_code == 422


def test_prevention_actions_exist_for_every_hazard():
    hazards = client.get("/api/hazards").json()
    assert all(len(info["prevention"]["fr"]) >= 3 and len(info["prevention"]["en"]) >= 3 for info in hazards.values())