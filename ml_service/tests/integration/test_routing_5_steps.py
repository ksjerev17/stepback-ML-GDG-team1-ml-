"""라우팅 5단계 회귀 — CLAUDE.md §6.3.

7 시나리오 PASS 필수: S001/S036/S040/S016/S005/S007 + step6 fallback.
"""
from __future__ import annotations

import pytest

from app.core.recommender import recommend
from tests.conftest import make_label


@pytest.mark.integration
def test_s001_future_prediction_routes_cognitive(base_context) -> None:
    label = make_label(
        patterns={"미래예측": 0.7, "이분법": 0.2},
        evidence="망할 것 같아",
    )
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "cognitive_restructuring"


@pytest.mark.integration
def test_s036_avoidance_routes_behavioral_activation(base_context) -> None:
    label = make_label(
        behaviors={"회피미루기": 0.75, "동기저하": 0.3},
        evidence="자꾸 폰만 보게 돼",
    )
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "behavioral_activation"


@pytest.mark.integration
def test_s040_motivation_routes_habit_design(base_context) -> None:
    label = make_label(
        behaviors={"회피미루기": 0.3, "동기저하": 0.8},
        evidence="다 귀찮고",
    )
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "habit_design"


@pytest.mark.integration
def test_s016_crisis_returns_crisis_card(base_context) -> None:
    label = make_label(crisis=True, evidence="위기 신호 감지")
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    assert out["type"] == "crisis_card"
    assert "1393" in out["crisis_resources"]["자살예방상담"]


@pytest.mark.integration
def test_s005_avoidance_priority_over_should_statement(base_context) -> None:
    """S005: 당위진술(인지) + 회피미루기(행동) 동시 — 회피가 우선."""
    label = make_label(
        patterns={"당위진술": 0.6},
        behaviors={"회피미루기": 0.7},
        evidence="일어나지 못함",
    )
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    assert out["type"] == "drill"
    assert out["drill"]["category"] == "behavioral_activation", (
        "v7 핵심 원칙: 인지 + 행동 동시 시 행동 라우팅 우선"
    )


@pytest.mark.integration
def test_s007_weak_signal_positive_drill_when_condition_ok(base_context) -> None:
    label = make_label(evidence="오늘 좀 피곤하네")
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    # v9.6: 약신호 + 컨디션 양호 → positive_card 대신 tone='positive' 유지형 드릴
    assert out["type"] == "drill"
    assert out["tone"] == "positive"


@pytest.mark.integration
def test_step6_fallback_when_signals_in_dead_zone(base_context) -> None:
    """모든 신호 0.3~0.4 사이 (step5 약신호 아닌데 step2~4 임계 미달)."""
    label = make_label(
        patterns={"미래예측": 0.35},  # < 0.4 (step2 미달)
        behaviors={"회피미루기": 0.35},  # < 0.5 (step3 미달)
        evidence="애매",
    )
    out = recommend(label_result=label, context=base_context, user_id="u_test")
    # v9.6: 항상 드릴 추천
    assert out["type"] == "drill"
