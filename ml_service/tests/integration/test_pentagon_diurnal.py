"""v9.5 — emotion_pentagon + weekly_recovery_pattern (일 1회 정책 반영).

이전 v9.4.x: diurnal_recovery (아침/저녁 비교) — 일 3회 가정.
현재 v9.5: weekly_recovery (월~수 vs 목~일 비교) — 일 1회 정책.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auto_discovery import (
    diurnal_recovery_pattern,   # alias 호환
    discover_all,
    weekly_recovery_pattern,
)
from app.core.weekly_report import build_report, emotion_pentagon
from app.main import app


client = TestClient(app)


# ============================================================================
# emotion_pentagon (변경 X — 단순 평균 통계)
# ============================================================================

@pytest.mark.integration
def test_emotion_pentagon_returns_5_axes() -> None:
    entries = [
        {"label_result": {"emotions": {"불안": 0.7, "우울": 0.2, "분노": 0.0, "죄책": 0.1, "중립": 0.1}}},
        {"label_result": {"emotions": {"불안": 0.5, "우울": 0.4, "분노": 0.0, "죄책": 0.0, "중립": 0.1}}},
    ]
    out = emotion_pentagon(entries)
    assert len(out["axes"]) == 5
    labels = [a["label"] for a in out["axes"]]
    assert labels == ["불안", "우울", "분노", "죄책", "중립"]
    for a in out["axes"]:
        assert 0.0 <= a["value"] <= 1.0
    assert out["dominant"] == "불안"
    assert out["entries_used"] == 2


@pytest.mark.integration
def test_emotion_pentagon_empty_entries() -> None:
    out = emotion_pentagon([])
    assert len(out["axes"]) == 5
    assert all(a["value"] == 0.0 for a in out["axes"])
    assert out["entries_used"] == 0


@pytest.mark.integration
def test_emotion_pentagon_zero_value_dominant_is_first() -> None:
    entries = [{"label_result": {"emotions": {"불안": 0.0, "우울": 0.0, "분노": 0.0, "죄책": 0.0, "중립": 0.0}}}]
    out = emotion_pentagon(entries)
    assert out["dominant"] == "불안"


# ============================================================================
# weekly_recovery_pattern — 주 전반(월~수) vs 후반(목~일)
# ============================================================================

@pytest.mark.integration
def test_weekly_recovery_detects_late_week_recovery() -> None:
    """월~수 컨디션 2 / 목~일 컨디션 4 → recovery 패턴."""
    entries = [
        # 월~수 (전반) - 컨디션 2
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 2,  # 월
         "label_result": {"patterns": {"미래예측": 0.5}}},
        {"created_at": "2026-05-19T19:00:00+00:00", "self_condition": 2,  # 화
         "label_result": {"patterns": {"미래예측": 0.5}}},
        {"created_at": "2026-05-20T19:00:00+00:00", "self_condition": 2,  # 수
         "label_result": {"patterns": {"미래예측": 0.5}}},
        # 목~일 (후반) - 컨디션 4
        {"created_at": "2026-05-21T19:00:00+00:00", "self_condition": 4,  # 목
         "label_result": {"patterns": {"미래예측": 0.1}}},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 4,  # 금
         "label_result": {"patterns": {"미래예측": 0.1}}},
        {"created_at": "2026-05-23T19:00:00+00:00", "self_condition": 4,  # 토
         "label_result": {"patterns": {"미래예측": 0.1}}},
        {"created_at": "2026-05-24T19:00:00+00:00", "self_condition": 4,  # 일
         "label_result": {"patterns": {"미래예측": 0.1}}},
    ]
    card = weekly_recovery_pattern(entries)
    assert card is not None
    assert card["pattern_type"] == "recovery"
    assert card["condition_delta"] >= 0.5
    assert "회복" in card["text"]
    assert card["sample_early"] == 3
    assert card["sample_late"] == 4


@pytest.mark.integration
def test_weekly_recovery_detects_fatigue() -> None:
    """월~수 컨디션 5 / 목~일 컨디션 2 → fatigue (전반이 더 좋음)."""
    entries = [
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 5,
         "label_result": {"patterns": {}}},
        {"created_at": "2026-05-19T19:00:00+00:00", "self_condition": 5,
         "label_result": {"patterns": {}}},
        {"created_at": "2026-05-20T19:00:00+00:00", "self_condition": 4,
         "label_result": {"patterns": {}}},
        {"created_at": "2026-05-21T19:00:00+00:00", "self_condition": 2,
         "label_result": {"patterns": {}}},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 2,
         "label_result": {"patterns": {}}},
    ]
    card = weekly_recovery_pattern(entries)
    assert card is not None
    assert card["pattern_type"] == "fatigue"
    assert card["condition_delta"] <= -0.5


@pytest.mark.integration
def test_weekly_early_load_signal_diff() -> None:
    """컨디션 차이는 작지만 전반에 인지 신호 강함 → early_load."""
    entries = [
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.7}}},
        {"created_at": "2026-05-19T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.7}}},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.1}}},
        {"created_at": "2026-05-23T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.1}}},
    ]
    card = weekly_recovery_pattern(entries)
    assert card is not None
    assert card["pattern_type"] == "early_load"


@pytest.mark.integration
def test_weekly_recovery_returns_none_if_no_variance() -> None:
    """전반·후반 동일하면 발견 X."""
    entries = [
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.3}}},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 3,
         "label_result": {"patterns": {"미래예측": 0.3}}},
    ]
    card = weekly_recovery_pattern(entries)
    assert card is None


@pytest.mark.integration
def test_diurnal_alias_still_works() -> None:
    """v9.4.x 호환 — 옛 이름으로 호출해도 동작."""
    entries = [
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 2,
         "label_result": {"patterns": {}}},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 4,
         "label_result": {"patterns": {}}},
    ]
    card = diurnal_recovery_pattern(entries)
    assert card is not None


# ============================================================================
# discover_all + build_report 통합
# ============================================================================

@pytest.mark.integration
def test_discover_all_includes_weekly_recovery() -> None:
    entries = [
        {"created_at": "2026-05-18T19:00:00+00:00", "self_condition": 2,
         "label_result": {"emotions": {"불안": 0.7}, "patterns": {"미래예측": 0.5}},
         "evidence_span": "망할 것 같아"},
        {"created_at": "2026-05-22T19:00:00+00:00", "self_condition": 4,
         "label_result": {"emotions": {"불안": 0.2}, "patterns": {}},
         "evidence_span": ""},
    ]
    cards = discover_all(entries, [])
    pattern_types = [c.get("pattern_type") for c in cards if "pattern_type" in c]
    assert any(pt in ("recovery", "fatigue", "early_load", "late_load") for pt in pattern_types)


@pytest.mark.integration
def test_build_report_includes_pentagon_and_weekly_recovery() -> None:
    """build_report 응답에 emotion_pentagon + weekly_recovery 포함."""
    entries = [
        {"created_at": f"2026-05-{18+i}T19:00:00+00:00",
         "self_condition": 2 if i < 3 else 4,
         "label_result": {
             "patterns": {"미래예측": 0.5 if i < 3 else 0.1, "독심술": 0, "자기비난": 0,
                          "이분법": 0, "당위진술": 0, "과잉일반화": 0},
             "behaviors": {"회피미루기": 0, "동기저하": 0},
             "emotions": {"불안": 0.6 if i < 3 else 0.1, "우울": 0.1, "분노": 0.0,
                          "죄책": 0.0, "중립": 0.3},
             "calendar_dominant": "emotion_anxiety" if i < 3 else "weak_signal_positive",
         },
        }
        for i in range(7)
    ]
    report = build_report(
        week="2026-W21",
        user_id="u_t",
        entries=entries,
        drills_recommended=7,
        drills_practiced=4,
    )
    assert "emotion_pentagon" in report
    assert report["emotion_pentagon"]["entries_used"] == 7
    # weekly_recovery 패턴 카드가 discoveries에 들어있는지
    discovery_texts = [d.get("text", "") for d in report.get("discoveries", [])]
    has_recovery = any("회복" in t or "전반" in t or "후반" in t for t in discovery_texts)
    assert has_recovery, f"weekly_recovery 카드 없음: {discovery_texts}"
