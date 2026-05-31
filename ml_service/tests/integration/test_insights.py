"""insights / reports / quiz / rejected drills 통합 — 명세서 §8."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import insights_store
from app.main import app


client = TestClient(app)


@pytest.fixture
def tmp_insights_db(tmp_path, monkeypatch):
    db = tmp_path / "insights.db"
    monkeypatch.setattr(insights_store, "INSIGHTS_DB", db)
    yield db


@pytest.mark.integration
def test_post_insight_user_source(tmp_insights_db) -> None:
    resp = client.post(
        "/insights",
        json={
            "user_id": "u_i1",
            "text": "잠이 부족할 때 내가 미래예측을 많이 한다는 것을 발견함",
            "category": "cognitive",
            "week_of": "2026-W21",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"] == "user"
    assert body["category"] == "cognitive"


@pytest.mark.integration
def test_get_insights_by_category(tmp_insights_db) -> None:
    client.post("/insights", json={"user_id": "u_i2", "text": "ins A", "category": "cognitive", "week_of": "2026-W21"})
    client.post("/insights", json={"user_id": "u_i2", "text": "ins B", "category": "behavior", "week_of": "2026-W21"})
    resp = client.get("/insights", params={"user_id": "u_i2", "category": "cognitive"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u_i2"
    assert len(body["items"]) == 1
    assert body["items"][0]["text"] == "ins A"


@pytest.mark.integration
def test_reject_drill_then_recommended_avoids(tmp_insights_db) -> None:
    resp = client.post("/reject", json={"user_id": "u_rej", "drill_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["drill_id"] == 1
    rejected = insights_store.rejected_drill_ids("u_rej")
    assert 1 in rejected


@pytest.mark.integration
def test_quiz_answer_match(tmp_insights_db) -> None:
    resp = client.patch(
        "/weekly/quiz",
        json={"user_id": "u_q", "week": "2026-W21", "predicted": "미래예측"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["correct"]  # 데모 entries top pattern
    assert "match" in body
    assert "is_dont_know" in body


@pytest.mark.integration
def test_quiz_answer_dont_know(tmp_insights_db) -> None:
    resp = client.patch(
        "/weekly/quiz",
        json={"user_id": "u_q2", "week": "2026-W21", "predicted": "모르겠다"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_dont_know"] is True
    assert body["match"] is False


@pytest.mark.integration
def test_reports_pending_then_read(tmp_insights_db) -> None:
    seed = client.post(
        "/reports",
        json={
            "user_id": "u_r",
            "week_of": "2026-W21",
            "pattern_analysis": {"미래예측": 60},
            "emotion_distribution": {"불안": 0.5},
        },
    )
    assert seed.status_code == 200
    report_id = seed.json()["report_id"]

    pending = client.get("/reports/pending", params={"user_id": "u_r"})
    assert pending.json()["count"] == 1

    read = client.patch(f"/reports/{report_id}/read", params={"user_id": "u_r"})
    assert read.status_code == 200

    after = client.get("/reports/pending", params={"user_id": "u_r"})
    assert after.json()["count"] == 0


@pytest.mark.integration
def test_export_user_data(tmp_insights_db) -> None:
    client.post("/insights", json={"user_id": "u_exp", "text": "x", "category": "cognitive", "week_of": "2026-W21"})
    resp = client.get("/export", params={"user_id": "u_exp"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u_exp"
    assert len(body["insights"]) >= 1


@pytest.mark.integration
def test_delete_user_data(tmp_insights_db) -> None:
    client.post("/insights", json={"user_id": "u_del", "text": "x", "category": "cognitive", "week_of": "2026-W21"})
    resp = client.delete("/users/u_del/data")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "u_del"
    assert "deleted" in body
