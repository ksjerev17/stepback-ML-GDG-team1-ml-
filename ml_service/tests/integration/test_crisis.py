"""위기 표현 5종 — CLAUDE.md §4.10, §16.2."""
from __future__ import annotations

import pytest

from app.core.labeler import label_text
from app.core.recommender import recommend


@pytest.mark.integration
@pytest.mark.parametrize(
    "phrase",
    [
        "더 이상 살고 싶지 않아 사라지고 싶다",
        "그냥 죽고 싶다",
        "끝내고 싶다는 생각이 자꾸 들어",
        "자해를 다시 하게 됐어",
        "사라지고 싶어",
    ],
)
def test_crisis_phrases_detected(phrase: str) -> None:
    result = label_text(phrase, user_id="u_crisis_test")
    assert result["crisis_detected"] is True
    assert result["calendar_dominant"] == "crisis"


@pytest.mark.integration
def test_crisis_card_blocks_drill(zero_label) -> None:
    zero_label["crisis_detected"] = True
    out = recommend(
        label_result=zero_label,
        context={"self_condition": 1, "sleep_hours": 3.0, "social_today": "갈등", "exercise_today": 0.0},
        user_id="u_crisis",
    )
    assert out["type"] == "crisis_card"
    assert "1393" in out["crisis_resources"]["자살예방상담"]
    assert out.get("drill") is None
