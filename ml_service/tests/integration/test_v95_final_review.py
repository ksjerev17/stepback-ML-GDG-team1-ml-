"""v9.5 최종 점검 — 시니어 페르소나 시뮬레이션으로 발견한 버그 회귀 방지.

발견 일자: 2026-05-24 최종 검토
발견 버그 3개:
  1. 강한 부정 감정 (≥0.5)인데 약신호로 분기 — Step 4.7 신규 추가로 해결
  2. EntriesRequest에 의미있는 텍스트 검증 누락 — _validate_meaningful_text 추가
  3. evidence_span 너무 길면 인용 어색 — 4~12자만 인용 규칙
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.labeler import label_text
from app.core.recommender import _build_copy, recommend
from app.infra.quota_manager import get_quota_manager
from app.main import app


client = TestClient(app)


# ============================================================================
# 버그 1: 강한 부정 감정 + 약한 인지/행동 → grounding 직접 추천 (Step 4.7)
# ============================================================================

@pytest.mark.integration
def test_strong_anger_with_weak_pattern_goes_grounding() -> None:
    """분노 0.6 + patterns/behaviors 모두 < 0.3 → grounding 드릴 (ask_user X)."""
    get_quota_manager().reset()
    lr = label_text("회사에서 동료랑 또 부딪혔어 답답하고 화나", user_id="t_anger")
    rec = recommend(
        label_result=lr,
        context={"self_condition": 2, "sleep_hours": 6.0,
                 "social_today": "갈등", "exercise_today": 0.0},
        user_id="t_anger",
    )
    # 절대로 ask_user로 빠지면 안 됨 — 강한 감정 신호
    assert rec["type"] == "drill", f"강한 감정인데 ask_user 분기: {rec}"
    assert rec["drill"]["category"] == "grounding"
    assert "강한 감정" in rec.get("reason", "")


@pytest.mark.integration
def test_strong_anxiety_with_weak_pattern_goes_grounding() -> None:
    """불안 0.6 + 인지 약함 → grounding."""
    # 직접 라벨 결과 주입 — Mock이 잡지 못하는 케이스 시뮬레이션
    fake_label = {
        "patterns": {"미래예측": 0.1, "독심술": 0.0, "자기비난": 0.0,
                     "이분법": 0.0, "당위진술": 0.0, "과잉일반화": 0.0},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {"불안": 0.7, "우울": 0.0, "분노": 0.0, "죄책": 0.0, "중립": 0.0},
        "intensity": 0.7,
        "confidence": 0.55,
        "evidence_span": "심장이 빨리",
        "crisis_detected": False,
    }
    rec = recommend(
        label_result=fake_label,
        context={"self_condition": 3, "sleep_hours": 7.0,
                 "social_today": "보통", "exercise_today": 0.0},
        user_id="t_strong_anx",
    )
    assert rec["type"] == "drill"
    assert rec["drill"]["category"] == "grounding"


@pytest.mark.integration
def test_neutral_only_does_not_trigger_step_4_7() -> None:
    """중립만 강함 → Step 4.7 발동 X. v9.6: positive_card 대신 tone='positive' 드릴."""
    fake_label = {
        "patterns": {k: 0.0 for k in ["미래예측", "독심술", "자기비난", "이분법", "당위진술", "과잉일반화"]},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {"불안": 0.0, "우울": 0.0, "분노": 0.0, "죄책": 0.0, "중립": 1.0},
        "intensity": 0.0, "confidence": 0.3, "evidence_span": "",
        "crisis_detected": False,
    }
    rec = recommend(
        label_result=fake_label,
        context={"self_condition": 4, "sleep_hours": 7.5,
                 "social_today": "보통", "exercise_today": 0.0},
        user_id="t_neutral",
    )
    # 중립만 강한 건 부정 감정 강함 X → Step 4.7 발동 X → 유지형 드릴(tone positive)
    assert rec["type"] == "drill"
    assert rec["tone"] == "positive"


# ============================================================================
# 버그 2: EntriesRequest 의미있는 텍스트 검증
# ============================================================================

@pytest.mark.integration
def test_entries_rejects_whitespace_only() -> None:
    r = client.post("/entries", json={"text": "      ", "user_id": "t_ws"})
    assert r.status_code == 422


@pytest.mark.integration
def test_entries_rejects_emoji_only() -> None:
    r = client.post("/entries", json={"text": "😭😭😭😭😭", "user_id": "t_emo"})
    assert r.status_code == 422


@pytest.mark.integration
def test_entries_rejects_repeated_chars() -> None:
    r = client.post("/entries", json={"text": "ㅋㅋㅋㅋㅋㅋㅋㅋ", "user_id": "t_rep"})
    assert r.status_code == 422


@pytest.mark.integration
def test_entries_accepts_short_meaningful() -> None:
    """1글자라도 의미있으면 통과."""
    get_quota_manager().reset()
    r = client.post("/entries", json={"text": "ㅠ", "user_id": "t_one"})
    assert r.status_code == 200


@pytest.mark.integration
def test_entries_accepts_max_500_chars() -> None:
    """max_length 500자 통일."""
    get_quota_manager().reset()
    long_text = "오늘 발표 망할 것 같아 떨려서 잠도 안 와. " * 15  # 약 450자
    assert len(long_text) <= 500
    r = client.post("/entries", json={"text": long_text, "user_id": "t_long"})
    assert r.status_code == 200


# ============================================================================
# 버그 3: evidence_span 길이 가드 (4~12자만 인용)
# ============================================================================

@pytest.mark.integration
def test_copy_does_not_quote_short_evidence() -> None:
    """1~3자 evidence는 인용 X."""
    drill = {"title": "5-4-3-2-1 감각", "duration_min": 3}
    copy = _build_copy(drill, evidence_span="ㅠ", confidence=0.4)
    assert "'ㅠ'" not in (copy["line1"] or "")
    assert "마음" in copy["line1"]


@pytest.mark.integration
def test_copy_does_not_quote_long_evidence() -> None:
    """13자 이상 evidence는 인용 X — 어색 방지."""
    drill = {"title": "5-4-3-2-1 감각", "duration_min": 3}
    long_ev = "회사에서 동료랑 또 부딪혔어 답답하고"  # 17자
    copy = _build_copy(drill, evidence_span=long_ev, confidence=0.5)
    assert long_ev not in (copy["line1"] or "")
    assert "마음" in copy["line1"]


@pytest.mark.integration
def test_copy_quotes_medium_evidence() -> None:
    """4~12자 evidence는 인용."""
    drill = {"title": "또 다른 가능성", "duration_min": 3}
    copy = _build_copy(drill, evidence_span="망할 것 같아", confidence=0.6)
    assert "'망할 것 같아'" in copy["line1"]
