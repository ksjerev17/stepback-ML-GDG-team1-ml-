"""주간 리포트 + 자가진단 퀴즈 — CLAUDE.md §4.8, §4.9."""
from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.core.self_check_quiz import build_quiz
from app.core.weekly_report import build_report
from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_quiz_has_4_options_with_dont_know() -> None:
    # v9.4.3: correct_value는 응답에 노출 X (보안). user_id+week 주면 cache에 저장.
    from app.core.self_check_quiz import clear_cache, get_cached_answer
    clear_cache()
    quiz = build_quiz(
        dominant_pattern="미래예측",
        actual_ratio_percent=32.0,
        rng=random.Random(0),
        user_id="uW",
        week="2026-W21",
    )
    assert len(quiz["options"]) == 4
    labels = [o["label"] for o in quiz["options"]]
    assert "모르겠다" in labels
    assert "correct_value" not in quiz
    assert "actual_ratio_percent" not in quiz
    cached = get_cached_answer("uW", "2026-W21")
    assert cached is not None
    assert cached["correct_value"] == "미래예측"


@pytest.mark.integration
def test_quiz_no_judgment_words() -> None:
    quiz = build_quiz(dominant_pattern="미래예측", actual_ratio_percent=60.0)
    text = quiz["question"]
    assert "맞췄어요" not in text
    assert "틀렸어요" not in text


@pytest.mark.integration
def test_build_report_5_blocks() -> None:
    entries = [
        {"created_at": "2026-05-19T08:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.7}}, "calendar_dominant": "emotion_anxiety"},
        {"created_at": "2026-05-19T13:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.6}}, "calendar_dominant": "cognitive_dominant"},
        {"created_at": "2026-05-20T08:30:00+00:00", "self_condition": 4,
         "label_result": {"patterns": {"자기비난": 0.5}}, "calendar_dominant": "cognitive_dominant"},
    ]
    r = build_report(week="2026-W21", user_id="u_w", entries=entries, drills_recommended=10, drills_practiced=7, prev_week_avg=2.9)
    assert r["overview"]["recorded_days"] == 2
    assert r["overview"]["avg_self_condition"] > 0
    assert r["dominant_pattern"]["dominant_key"] == "미래예측"
    assert r["drill_action"]["recommended_count"] == 10
    assert "self_check_quiz" in r
    assert sum(r["calendar_distribution"]["distribution"].values()) == 3


@pytest.mark.integration
def test_weekly_endpoint_demo() -> None:
    resp = client.get("/weekly", params={"user_id": "u_demo", "week": "2026-W21"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["week"] == "2026-W21"
    assert "overview" in body
    assert "dominant_pattern" in body
    assert "self_check_quiz" in body
    assert len(body["self_check_quiz"]["options"]) == 4
