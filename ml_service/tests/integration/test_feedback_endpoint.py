"""POST /feedback, GET /feedback — 점수 비공개 검증."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import feedback_store
from app.core.feedback_store import _kst_today
from app.main import app


client = TestClient(app)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "feedback.db"
    monkeypatch.setattr(feedback_store, "DB_PATH", db)
    yield db


@pytest.mark.integration
def test_post_feedback_accepted(tmp_db) -> None:
    today = _kst_today()
    resp = client.post(
        "/feedback",
        json={
            "user_id": "u_fb",
            "drill_id": 1,
            "rating": "helpful",
            "recommended_at": today.isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert "can_edit_until" in body


@pytest.mark.integration
def test_post_feedback_invalid_rating_422(tmp_db) -> None:
    resp = client.post(
        "/feedback",
        json={
            "user_id": "u_fb2",
            "drill_id": 1,
            "rating": "love_it",
            "recommended_at": _kst_today().isoformat(),
        },
    )
    assert resp.status_code == 422


@pytest.mark.integration
def test_get_feedback_does_not_expose_rating(tmp_db) -> None:
    today = _kst_today()
    client.post(
        "/feedback",
        json={"user_id": "u_fb3", "drill_id": 1, "rating": "helpful", "recommended_at": today.isoformat()},
    )
    client.post(
        "/feedback",
        json={"user_id": "u_fb3", "drill_id": 2, "rating": "unhelpful", "recommended_at": today.isoformat()},
    )
    resp = client.get("/feedback", params={"user_id": "u_fb3"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 2
    assert "rating" not in body
    assert "helpful" not in str(body)
    assert "unhelpful" not in str(body)


@pytest.mark.integration
def test_idempotent_update_same_day(tmp_db) -> None:
    today = _kst_today()
    for rating in ("meh", "helpful", "unhelpful"):
        resp = client.post(
            "/feedback",
            json={"user_id": "u_fb4", "drill_id": 1, "rating": rating, "recommended_at": today.isoformat()},
        )
        assert resp.status_code == 200
    summary = client.get("/feedback", params={"user_id": "u_fb4"}).json()
    assert summary["total_count"] == 1  # UNIQUE(user_hash, drill_id, recommended_at)
