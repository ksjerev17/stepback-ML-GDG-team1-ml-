"""calendar / drills / daily 엔드포인트."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_drill_detail_d01() -> None:
    resp = client.get("/drills/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["category"] == "cognitive_restructuring"
    assert "Beck" in (body.get("source_primary") or "") or "Beck" in (body.get("source_short") or "")


@pytest.mark.integration
def test_drill_not_found_404() -> None:
    resp = client.get("/drills/9999")
    assert resp.status_code == 404


@pytest.mark.integration
def test_drill_list_filter_by_category() -> None:
    resp = client.get("/drills", params={"category": "grounding"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 13
    assert all(d["category"] == "grounding" for d in body["drills"])


@pytest.mark.integration
def test_categories_endpoint_returns_6_items() -> None:
    """v9.5: GET /categories — BE/FE 정적 import 대신 API 호출용."""
    resp = client.get("/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 6
    keys = {c["key"] for c in body["categories"]}
    assert keys == {
        "cognitive_restructuring", "behavioral_activation", "habit_design",
        "grounding", "self_compassion", "sleep_circadian",
    }
    # 각 항목은 4 필드 + drill_count 합계 = 100
    total_drills = 0
    for c in body["categories"]:
        assert set(c.keys()) == {"key", "label_ko", "calendar_color", "drill_count"}
        assert c["drill_count"] > 0
        total_drills += c["drill_count"]
    assert total_drills == 100


@pytest.mark.integration
def test_categories_calendar_color_mapping_intact() -> None:
    """category → calendar_color 매핑은 BE/FE가 색 표시에 사용."""
    body = client.get("/categories").json()
    color_map = {c["key"]: c["calendar_color"] for c in body["categories"]}
    assert color_map["cognitive_restructuring"] == "pink_soft"
    assert color_map["grounding"] == "green_calm"
    assert color_map["sleep_circadian"] == "blue_night"


@pytest.mark.integration
def test_post_calendar() -> None:
    entries = [
        {"created_at": "2026-05-19T08:00:00+00:00", "self_condition": 3,
         "time_of_day": "morning",
         "label_result": {"calendar_dominant": "emotion_anxiety"}},
        {"created_at": "2026-05-19T13:00:00+00:00", "self_condition": 4,
         "time_of_day": "afternoon",
         "label_result": {"calendar_dominant": "weak_signal_positive"}},
        {"created_at": "2026-05-20T08:30:00+00:00", "self_condition": 5,
         "time_of_day": "morning",
         "label_result": {"calendar_dominant": "weak_signal_positive"}},
    ]
    resp = client.post(
        "/calendar",
        json={"user_id": "u_cal", "month": "2026-05", "entries": entries},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["month"] == "2026-05"
    assert len(body["days"]) == 2
    day1 = next(d for d in body["days"] if d["date"] == "2026-05-19")
    assert len(day1["slots"]) == 2
    assert day1["avg_condition"] == 3.5


@pytest.mark.integration
def test_post_daily_excludes_helpful() -> None:
    entries = [{
        "created_at": "2026-05-19T08:00:00+00:00",
        "text": "내일 발표 망할 것 같아",
        "self_condition": 3,
        "time_of_day": "morning",
        "context": {"sleep_hours": 5},
        "label_result": {"calendar_dominant": "emotion_anxiety"},
        "drill_id": 1,
        "drill_title": "증거 2:2 적기",
        "drill_complete": True,
        "helpful": True,  # 응답에 노출 안 됨
    }]
    resp = client.post(
        "/daily",
        json={"user_id": "u_d", "date": "2026-05-19", "entries": entries},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"][0]["drill_complete"] is True
    assert "helpful" not in body["entries"][0]
    assert "helpful" not in str(body)
