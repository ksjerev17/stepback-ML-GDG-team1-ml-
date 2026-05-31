"""FastAPI 엔드포인트 통합 — /healthz, /label, /recommend."""
from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_healthz_ok() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["drills_loaded"] == 100
    assert body["catalog_version"] == "v6.4"


@pytest.mark.integration
def test_label_post_returns_schema() -> None:
    resp = client.post("/label", json={"text": "내일 발표 망할 것 같아", "user_id": "u_demo_label"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "patterns" in body
    assert "behaviors" in body
    assert "emotions" in body
    assert body["crisis_detected"] is False
    # 미래예측 cue 매칭 확인 (Mock)
    assert body["patterns"]["미래예측"] > 0


@pytest.mark.integration
def test_label_crisis_path() -> None:
    resp = client.post("/label", json={"text": "사라지고 싶다", "user_id": "u_demo_crisis"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["crisis_detected"] is True


@pytest.mark.integration
def test_recommend_drill_path(zero_label) -> None:
    label = zero_label.copy()
    label["patterns"] = dict(zero_label["patterns"])
    label["patterns"]["미래예측"] = 0.7
    label["evidence_span"] = "망할 것 같아"
    label["confidence"] = 0.7  # v9.4.3: 강한 신호 → 높은 confidence → 단정 카피
    payload = {
        "label_result": label,
        "context": {
            "self_condition": 3,
            "sleep_hours": 7.0,
            "social_today": "보통",
            "exercise_today": 0.0,
        },
        "user_id": "u_demo_rec",
        "recent_drill_ids": [],
    }
    resp = client.post("/recommend", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "drill"
    assert body["drill"]["category"] == "cognitive_restructuring"
    assert body["copy"]["line2"].startswith("이런 때는")


@pytest.mark.integration
def test_recommend_crisis_path(zero_label) -> None:
    zero_label["crisis_detected"] = True
    payload = {
        "label_result": zero_label,
        "context": {
            "self_condition": 3,
            "sleep_hours": 7.0,
            "social_today": "보통",
            "exercise_today": 0.0,
        },
        "user_id": "u_demo_crisis_rec",
    }
    resp = client.post("/recommend", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "crisis_card"


@pytest.mark.integration
def test_invalid_input_422() -> None:
    resp = client.post("/label", json={"text": "", "user_id": "u"})
    assert resp.status_code == 422
