"""v9.5 변경사항 통합 검증.

- 일 1회 정책
- drill_id 정수
- 욕설 → intensity 가산
- 기쁨 차원
- 짧은 입력 카피
- 월간 리포트
- 주간 회복 패턴
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.labeler import label_text
from app.core.monthly_report import build_monthly_report
from app.infra.llm_client import LLMClient, _has_profanity

_mock_client = LLMClient(force_mock=True)
_mock_label = _mock_client._mock_label
from app.infra.quota_manager import get_quota_manager
from app.main import app


client = TestClient(app)


# ============================================================================
# 정책: 일 1회
# ============================================================================

@pytest.mark.integration
def test_quota_day_limit_is_1() -> None:
    """일 1회 정책 — 두 번째 호출 즉시 거절."""
    qm = get_quota_manager()
    qm.reset()
    r1 = client.post("/label", json={"text": "오늘 발표 망할 것 같아", "user_id": "u_q1"})
    assert r1.status_code == 200
    r2 = client.post("/label", json={"text": "또 망함", "user_id": "u_q1"})
    assert r2.status_code == 429


# ============================================================================
# drill_id 정수
# ============================================================================

@pytest.mark.integration
def test_drill_id_is_integer() -> None:
    r = client.get("/drills/1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert isinstance(body["id"], int)
    # legacy_id도 응답에 있는지 (마이그레이션 호환)
    assert "legacy_id" not in body or isinstance(body.get("legacy_id"), str)


@pytest.mark.integration
def test_drill_legacy_id_still_lookup() -> None:
    """get_drill('D01')도 호환 (마이그레이션 안전)."""
    from app.core.drill_catalog import get_drill
    d = get_drill("D01")
    assert d is not None
    assert d["id"] == 1


# ============================================================================
# 욕설 → intensity 가산
# ============================================================================

@pytest.mark.integration
def test_profanity_detected() -> None:
    assert _has_profanity("씨발 진짜 다 좆같다") is True
    assert _has_profanity("ㅅㅂ 짜증나") is True
    assert _has_profanity("오늘 좋았어") is False


@pytest.mark.integration
def test_profanity_boosts_intensity() -> None:
    no_prof = _mock_label("오늘 좀 짜증나는 일이 있었어")
    with_prof = _mock_label("씨발 진짜 좆같다 짜증나")
    assert with_prof["intensity"] >= no_prof["intensity"]
    assert with_prof.get("_profanity_detected") is True


# ============================================================================
# 짧은 입력 카피
# ============================================================================

@pytest.mark.integration
def test_short_input_copy_no_quote() -> None:
    """1~3자 입력 시 evidence_span 인용 X — 자연스러운 카피."""
    from app.core.recommender import _build_copy
    drill = {"title": "5-4-3-2-1 감각", "duration_min": 3}
    copy = _build_copy(drill, evidence_span="ㅠ", confidence=0.4)
    # 1자 인용 안 들어가는지
    assert "'ㅠ'" not in (copy["line1"] or "")
    assert "마음" in (copy["line1"] or "")


# ============================================================================
# 월간 리포트
# ============================================================================

@pytest.mark.integration
def test_monthly_report_basic() -> None:
    """월간 리포트 6 블록 응답."""
    from datetime import datetime, timezone
    entries = [
        {
            "created_at": datetime(2026, 5, d, 19, 0, tzinfo=timezone.utc).isoformat(),
            "self_condition": 3,
            "label_result": {
                "patterns": {"미래예측": 0.5, "독심술": 0, "자기비난": 0,
                             "이분법": 0, "당위진술": 0, "과잉일반화": 0},
                "behaviors": {"회피미루기": 0, "동기저하": 0},
                "emotions": {"불안": 0.4, "우울": 0.1, "분노": 0, "죄책": 0,
                             "중립": 0.5},
                "calendar_dominant": "emotion_anxiety",
            },
        }
        for d in range(1, 31)
    ]
    report = build_monthly_report(
        month="2026-05",
        user_id="u_m",
        entries=entries,
        drills_recommended=30,
        drills_practiced=20,
    )
    assert report["month"] == "2026-05"
    assert report["overview"]["recorded_days"] == 30
    assert report["overview"]["total_entries"] == 30
    assert report["dominant_pattern"]["dominant_key"] == "미래예측"
    assert "axes" in report["emotion_pentagon"]
    assert len(report["emotion_pentagon"]["axes"]) == 5
    assert "weeks" in report["condition_trend"]
    assert report["drill_action"]["practice_rate"] == round(20/30, 2)


@pytest.mark.integration
def test_monthly_endpoint_get_demo() -> None:
    """GET /monthly?user_id=...&month=2026-05 데모 응답."""
    r = client.get("/monthly", params={"user_id": "u_demo", "month": "2026-05"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["month"] == "2026-05"
    assert body["overview"]["total_entries"] > 20
