"""baseline recompute + compare — 명세서 §10.2."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import baselines
from app.main import app


client = TestClient(app)


@pytest.fixture
def tmp_baselines_db(tmp_path, monkeypatch):
    db = tmp_path / "baselines.db"
    monkeypatch.setattr(baselines, "BASELINES_DB", db)
    yield db


@pytest.mark.integration
def test_baseline_recompute_stores_avg(tmp_baselines_db) -> None:
    entries = [
        {"label_result": {"patterns": {"미래예측": 0.6, "자기비난": 0.0}, "behaviors": {"회피미루기": 0.4, "동기저하": 0.0}, "emotions": {}}},
        {"label_result": {"patterns": {"미래예측": 0.4, "자기비난": 0.2}, "behaviors": {"회피미루기": 0.2, "동기저하": 0.0}, "emotions": {}}},
    ]
    resp = client.post(
        "/baseline/recompute",
        json={"user_id": "u_b", "entries": entries, "rejected_drills": ["D77"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert abs(body["patterns_avg"]["미래예측"] - 0.5) < 1e-3
    assert body["sample_count"] == 2
    assert "D77" in body["rejected_drills"]


@pytest.mark.integration
def test_baseline_get_after_recompute(tmp_baselines_db) -> None:
    client.post("/baseline/recompute", json={"user_id": "u_b2", "entries": [], "rejected_drills": []})
    resp = client.get("/baseline", params={"user_id": "u_b2"})
    assert resp.status_code == 200


@pytest.mark.integration
def test_baseline_get_404_when_missing(tmp_baselines_db) -> None:
    resp = client.get("/baseline", params={"user_id": "u_nope"})
    assert resp.status_code == 404


@pytest.mark.integration
def test_baseline_compare_card(tmp_baselines_db) -> None:
    entries = [{"label_result": {"patterns": {"미래예측": 0.2, "자기비난": 0.1, "독심술": 0.0, "이분법": 0.0, "당위진술": 0.0, "과잉일반화": 0.0}, "behaviors": {"회피미루기": 0.1, "동기저하": 0.0}, "emotions": {}}}]
    baselines.recompute_baseline(user_id="u_b3", entries=entries)
    cmp = baselines.compare_to_baseline(
        "u_b3",
        current_patterns_avg={"미래예측": 0.5, "자기비난": 0.1, "독심술": 0.0, "이분법": 0.0, "당위진술": 0.0, "과잉일반화": 0.0},
        current_behaviors_avg={"회피미루기": 0.1, "동기저하": 0.0},
    )
    assert cmp is not None
    assert cmp["top_increase"] is not None
    assert cmp["top_increase"]["name"] == "미래예측"
