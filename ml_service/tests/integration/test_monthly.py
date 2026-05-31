"""v9.5 신규: 월간 리포트 (POST /monthly, GET /monthly) — 일 1회 정책 기반.

검증:
- POST /monthly — BE entries 전달 흐름
- GET /monthly — 데모 entries 자동 생성
- monthly_overview / dominant_pattern / calendar_distribution / emotion_pentagon /
  condition_trend / drill_action 6 블록 모두 정확 산출
- 빈 entries 안전 처리
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.monthly_report import (
    build_monthly_report,
    monthly_calendar_distribution,
    monthly_condition_trend,
    monthly_dominant_pattern,
    monthly_emotion_pentagon,
    monthly_overview,
)
from app.main import app


client = TestClient(app)


# ============================================================================
# core 단위 — 각 블록
# ============================================================================

@pytest.mark.integration
def test_monthly_overview_avg_and_days() -> None:
    entries = [
        {"created_at": "2026-05-01T09:00:00+00:00", "self_condition": 3, "label_result": {}},
        {"created_at": "2026-05-02T09:00:00+00:00", "self_condition": 4, "label_result": {}},
        {"created_at": "2026-05-03T09:00:00+00:00", "self_condition": 5, "label_result": {}},
    ]
    o = monthly_overview(entries)
    assert o["recorded_days"] == 3
    assert o["total_entries"] == 3
    assert o["avg_self_condition"] == 4.0


@pytest.mark.integration
def test_monthly_dominant_pattern_picks_top() -> None:
    entries = [
        {"label_result": {"patterns": {"미래예측": 0.7}}},
        {"label_result": {"patterns": {"미래예측": 0.6}}},
        {"label_result": {"patterns": {"자기비난": 0.5}}},
    ]
    d = monthly_dominant_pattern(entries)
    assert d["dominant_key"] == "미래예측"
    assert d["occurrences"] == 2
    assert d["total_strong"] == 3


@pytest.mark.integration
def test_monthly_dominant_pattern_empty() -> None:
    """signal 약하면 dominant 0건."""
    entries = [{"label_result": {"patterns": {"미래예측": 0.2}}}]
    d = monthly_dominant_pattern(entries)
    assert d["occurrences"] == 0


@pytest.mark.integration
def test_monthly_calendar_distribution_counts() -> None:
    entries = [
        {"calendar_dominant": "emotion_anxiety"},
        {"calendar_dominant": "emotion_anxiety"},
        {"calendar_dominant": "weak_signal_positive"},
    ]
    d = monthly_calendar_distribution(entries)
    assert d["distribution"]["emotion_anxiety"] == 2
    assert d["distribution"]["weak_signal_positive"] == 1


@pytest.mark.integration
def test_monthly_emotion_pentagon_5_axes() -> None:
    entries = [
        {"label_result": {"emotions": {"불안": 0.5, "우울": 0.3, "분노": 0.0, "죄책": 0.1, "중립": 0.1}}},
        {"label_result": {"emotions": {"불안": 0.7, "우울": 0.2, "분노": 0.0, "죄책": 0.0, "중립": 0.1}}},
    ]
    p = monthly_emotion_pentagon(entries)
    assert len(p["axes"]) == 5
    labels = [a["label"] for a in p["axes"]]
    assert labels == ["불안", "우울", "분노", "죄책", "중립"]
    assert p["dominant"] == "불안"
    assert p["entries_used"] == 2


@pytest.mark.integration
def test_monthly_emotion_pentagon_empty_entries() -> None:
    p = monthly_emotion_pentagon([])
    assert len(p["axes"]) == 5
    assert all(a["value"] == 0.0 for a in p["axes"])
    assert p["entries_used"] == 0


@pytest.mark.integration
def test_monthly_condition_trend_4_weeks() -> None:
    entries = [
        {"created_at": "2026-05-01T09:00:00+00:00", "self_condition": 2, "label_result": {}},  # 1주
        {"created_at": "2026-05-08T09:00:00+00:00", "self_condition": 3, "label_result": {}},  # 2주
        {"created_at": "2026-05-15T09:00:00+00:00", "self_condition": 4, "label_result": {}},  # 3주
        {"created_at": "2026-05-22T09:00:00+00:00", "self_condition": 5, "label_result": {}},  # 4주
    ]
    t = monthly_condition_trend(entries)
    assert len(t["weeks"]) == 5  # 1~5 (5월은 5주차까지 가능)
    week1 = next(w for w in t["weeks"] if w["week_in_month"] == 1)
    assert week1["avg_condition"] == 2.0
    week4 = next(w for w in t["weeks"] if w["week_in_month"] == 4)
    assert week4["avg_condition"] == 5.0


# ============================================================================
# 전체 builder
# ============================================================================

@pytest.mark.integration
def test_build_monthly_report_full_structure() -> None:
    entries = [
        {"created_at": "2026-05-01T09:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.6}, "emotions": {"불안": 0.5}},
         "calendar_dominant": "emotion_anxiety"},
        {"created_at": "2026-05-15T09:00:00+00:00", "self_condition": 4,
         "label_result": {"patterns": {"미래예측": 0.5}, "emotions": {"중립": 0.7}},
         "calendar_dominant": "weak_signal_positive"},
    ]
    r = build_monthly_report(
        month="2026-05",
        user_id="u_monthly",
        entries=entries,
        drills_recommended=10,
        drills_practiced=6,
    )
    assert r["month"] == "2026-05"
    assert r["user_id"] == "u_monthly"
    assert "overview" in r
    assert "dominant_pattern" in r
    assert "calendar_distribution" in r
    assert "emotion_pentagon" in r
    assert "condition_trend" in r
    assert "drill_action" in r
    assert r["drill_action"]["practice_rate"] == 0.6


# ============================================================================
# 엔드포인트
# ============================================================================

@pytest.mark.integration
def test_get_monthly_demo_returns_full_report() -> None:
    """GET /monthly — 데모 entries로 6 블록 모두 채움."""
    resp = client.get("/monthly", params={"user_id": "u_test", "month": "2026-05"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["month"] == "2026-05"
    assert body["overview"]["recorded_days"] >= 1
    assert len(body["emotion_pentagon"]["axes"]) == 5
    assert len(body["condition_trend"]["weeks"]) == 5


@pytest.mark.integration
def test_post_monthly_with_entries() -> None:
    """POST /monthly — BE가 직접 entries 전달."""
    resp = client.post("/monthly", json={
        "month": "2026-05",
        "user_id": "u_post_monthly",
        "entries": [
            {"created_at": "2026-05-10T09:00:00+00:00", "self_condition": 4,
             "label_result": {"patterns": {"자기비난": 0.5}, "emotions": {"우울": 0.3}},
             "calendar_dominant": "cognitive_dominant"},
        ],
        "drills_recommended": 5,
        "drills_practiced": 3,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["drill_action"]["practice_rate"] == 0.6
    assert body["overview"]["total_entries"] == 1
