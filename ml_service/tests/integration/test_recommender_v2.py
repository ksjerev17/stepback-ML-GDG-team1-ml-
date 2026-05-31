"""Recommender bonus 점수 + Step 4 경계선 + rejected 누적."""
from __future__ import annotations

import pytest

from app.core import insights_store
from app.core.recommender import _bonus, recommend
from tests.conftest import make_label


@pytest.fixture
def tmp_insights_db(tmp_path, monkeypatch):
    db = tmp_path / "insights.db"
    monkeypatch.setattr(insights_store, "INSIGHTS_DB", db)
    yield db


@pytest.mark.integration
def test_bonus_sleep_circadian_short_sleep() -> None:
    """v9.5: 일 1회 정책 — time_of_day 제거, 수면 < 5h 만으로 0.3 가산."""
    drill = {"category": "sleep_circadian", "duration_min": 3}
    ctx = {"sleep_hours": 4, "self_condition": 3}
    assert _bonus(drill, ctx) >= 0.3


def test_bonus_sleep_circadian_moderate_short_sleep() -> None:
    """수면 5~5.9h → 가벼운 가산 (0.15)."""
    drill = {"category": "sleep_circadian", "duration_min": 3}
    ctx = {"sleep_hours": 5.5, "self_condition": 3}
    b = _bonus(drill, ctx)
    assert 0.1 <= b < 0.3


@pytest.mark.integration
def test_bonus_grounding_low_condition() -> None:
    drill = {"category": "grounding", "duration_min": 3}
    ctx = {"self_condition": 2}
    assert _bonus(drill, ctx) >= 0.2


@pytest.mark.integration
def test_bonus_self_compassion_social_conflict() -> None:
    drill = {"category": "self_compassion", "duration_min": 3}
    ctx = {"social_today": "갈등", "self_condition": 3}
    assert _bonus(drill, ctx) >= 0.2


@pytest.mark.integration
def test_step4_boundary_clarification_asks() -> None:
    """모든 신호 0.3~0.5 사이 경계선 — 명세서 §6.2 Step 4."""
    label = make_label(
        patterns={"미래예측": 0.35, "자기비난": 0.32},
        behaviors={"회피미루기": 0.3},
    )
    out = recommend(
        label_result=label,
        context={"self_condition": 3, "sleep_hours": 7, "social_today": "보통", "exercise_today": 0.0},
        user_id="u_step4",
    )
    # v9.6: 경계선도 ask_user 없이 더 강한 후보 카테고리 드릴
    assert out["type"] == "drill"
    assert "경계선" in out["reason"]


@pytest.mark.integration
def test_rejected_drill_avoided(tmp_insights_db) -> None:
    """'아닌 것 같아요'로 누적된 드릴은 다음 추천에서 제외."""
    insights_store.reject_drill(user_id="u_r1", drill_id="D01")
    label = make_label(
        patterns={"미래예측": 0.7, "이분법": 0.2},
        evidence="망할 것 같아",
    )
    out = recommend(
        label_result=label,
        context={"self_condition": 3, "sleep_hours": 7, "social_today": "보통", "exercise_today": 0.0},
        user_id="u_r1",
    )
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "cognitive_restructuring"
    # D01이 우선이지만 rejected이므로 다른 드릴 선택
    assert out["drill"]["id"] != "D01"
