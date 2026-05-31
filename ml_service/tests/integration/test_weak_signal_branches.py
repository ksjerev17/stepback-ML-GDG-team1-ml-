"""약신호 분기 — v9.6 always-drill 정책 검증.

변경 이력:
- v9.4.3: 약신호 + 컨디션/수면/사교 나쁨 → 바로 드릴.
- v9.4.4: 같은 조건 → ask_drill_offer("받으실래요?") 먼저.
- v9.6 (현재): 다시 "항상 드릴 추천" — 묻지 않고 맥락에 맞는 드릴 즉시.
              컨디션 양호 + 약신호 → tone="positive" 유지형 드릴 (positive_card 대체).
              ask_user / positive_card 는 정상 흐름에서 더 이상 반환되지 않음.
              crisis_card 만 별도 type 유지.
"""
from __future__ import annotations

import pytest

from app.core.recommender import recommend, recommend_after_ask_user


@pytest.mark.integration
def test_5a_low_condition_gives_grounding_drill(zero_label) -> None:
    ctx = {"self_condition": 2, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "grounding"


@pytest.mark.integration
def test_5b_short_sleep_gives_sleep_drill(zero_label) -> None:
    ctx = {"self_condition": 3, "sleep_hours": 4.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "sleep_circadian"


@pytest.mark.integration
def test_5c_social_conflict_gives_self_compassion_drill(zero_label) -> None:
    ctx = {"self_condition": 3, "sleep_hours": 7.0, "social_today": "갈등", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "self_compassion"


@pytest.mark.integration
def test_priority_b_severe_condition_beats_short_sleep(zero_label) -> None:
    """컨디션 1점 > 수면 4h → 컨디션(그라운딩) 우선."""
    ctx = {"self_condition": 1, "sleep_hours": 4.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "grounding"


@pytest.mark.integration
def test_priority_b_severe_sleep_beats_mild_condition(zero_label) -> None:
    """수면 3시간 > 컨디션 2점 → 수면 우선."""
    ctx = {"self_condition": 2, "sleep_hours": 3.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "sleep_circadian"


@pytest.mark.integration
def test_5d_high_condition_returns_positive_drill(zero_label) -> None:
    """컨디션 양호 + 약신호 → positive_card 대신 tone='positive' 유지형 드릴."""
    ctx = {"self_condition": 4, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
    assert out["type"] == "drill"
    assert out["tone"] == "positive"
    assert out["why"]["tone"] == "positive"


@pytest.mark.integration
def test_always_drill_never_ask_or_skip(zero_label) -> None:
    """다양한 약신호 맥락 어디서도 ask_user/positive_card/skip 안 나옴 (crisis 제외)."""
    for ctx in (
        {"self_condition": 1, "sleep_hours": 3.0, "social_today": "갈등", "exercise_today": 0.0},
        {"self_condition": 5, "sleep_hours": 8.0, "social_today": "좋음", "exercise_today": 1.0},
        {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0},
    ):
        out = recommend(label_result=zero_label, context=ctx, user_id="u_t")
        assert out["type"] == "drill"


# ── recommend_after_ask_user 는 하위호환용으로 유지 (FE는 더 이상 호출 안 함) ──

@pytest.mark.integration
def test_after_ask_yes_with_offer_returns_drill(zero_label) -> None:
    ctx = {"self_condition": 2, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend_after_ask_user(
        label_result=zero_label, context=ctx, user_id="u_t",
        user_choice="yes", offer_category="grounding",
    )
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "grounding"


@pytest.mark.integration
def test_after_ask_no_returns_skip(zero_label) -> None:
    ctx = {"self_condition": 2, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
    out = recommend_after_ask_user(
        label_result=zero_label, context=ctx, user_id="u_t",
        user_choice="no", offer_category="grounding",
    )
    assert out["type"] == "skip"
