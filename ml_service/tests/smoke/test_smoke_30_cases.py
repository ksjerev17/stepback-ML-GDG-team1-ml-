"""Smoke 30 케이스 — CLAUDE.md §8.W6 DoD #1.

전체 파이프라인 (라벨 → 추천) 30 시나리오. Mock 동작 가정.

Mock LLM은 어휘 단서 기반 — 실제 Gemini보다 약함. 시나리오별 허용 type set으로 검증.
"""
from __future__ import annotations

import pytest

from app.core.labeler import label_text
from app.core.recommender import recommend


BASE_CTX = {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
# v9.6: always-drill 정책 — 정상 흐름은 항상 drill (crisis_card만 예외).
DRILL_OR_POS = {"drill"}
DRILL_ONLY = {"drill"}
CRISIS_ONLY = {"crisis_card"}
POSITIVE_ONLY = {"drill"}   # 안정적인 날도 tone='positive' 드릴


SCENARIOS: list[tuple[str, dict, set[str]]] = [
    # (text, context_override, allowed types)
    # 인지 (Mock 어휘 매칭으로 drill 또는 positive_card)
    ("내일 발표 망할 것 같아", {}, DRILL_OR_POS),
    ("분명 잘 안 될 거야", {}, DRILL_OR_POS),
    ("쟤는 나를 한심하게 봤을 거야", {}, DRILL_OR_POS),
    ("다 내 탓 같다", {}, DRILL_OR_POS),
    ("완전 망쳤어 다 끝났다", {}, DRILL_OR_POS),
    ("반드시 만점 받아야 해", {}, DRILL_OR_POS),
    ("나는 항상 이래 매번 망쳐", {}, DRILL_OR_POS),
    # 행동 (cue 강함 — drill 기대)
    ("과제 시작해야 하는데 자꾸 폰만 보게 돼", {}, DRILL_ONLY),
    # v9.4.3 P2: _score_by_cues 가산 0.4→0.3 변경으로 cue 1개 매칭은 약신호 (0.3).
    # "미루다" 단서 1개라 → 약신호 → positive_card 가능 (명세서 §4.3 정합).
    ("하기 싫어서 자꾸 미루게 돼", {}, DRILL_OR_POS),
    ("다 귀찮고 아무것도 하기 싫다", {}, DRILL_ONLY),
    ("그냥 누워있고 싶다", {}, DRILL_OR_POS),
    ("의욕이 없어 시작을 못 하겠어", {}, DRILL_ONLY),
    # 위기 (5)
    ("사라지고 싶다", {}, CRISIS_ONLY),
    ("죽고 싶다는 생각이 자꾸", {}, CRISIS_ONLY),
    ("끝내고 싶어", {}, CRISIS_ONLY),
    ("더 이상 살고 싶지 않아", {}, CRISIS_ONLY),
    ("자해를 다시 하게 됐어", {}, CRISIS_ONLY),
    # 약신호 — positive
    ("오늘 평범했어", {"self_condition": 4}, POSITIVE_ONLY),
    ("그냥 그런 하루", {"self_condition": 3}, POSITIVE_ONLY),
    ("커피 한 잔 마셨다", {"self_condition": 5}, POSITIVE_ONLY),
    # 약신호 — grounding (self_condition <= 2)
    ("오늘 좀 피곤하네", {"self_condition": 2}, DRILL_ONLY),
    # 약신호 — sleep
    ("그냥 평범한 날", {"sleep_hours": 4.0}, DRILL_ONLY),
    # 약신호 — self_compassion
    ("오늘은 그냥 그래", {"social_today": "갈등"}, DRILL_ONLY),
    # 인지+행동 동시 (S005 회피 우선) — Mock 매칭 약해 drill 또는 positive_card 가능
    ("공부해야 하는데 일어나지 못해서 하기 싫어", {}, DRILL_OR_POS),
    # 감정 단독 (라우팅 약함 - step5)
    ("그냥 무겁다", {"self_condition": 3}, DRILL_OR_POS),
    # 길이 짧음 + 약신호
    ("그래", {"self_condition": 4}, POSITIVE_ONLY),
    # PII 포함
    ("교수님 김민수 너무 무서워서 발표가 두려워", {}, DRILL_OR_POS),
    ("내 핸드폰 010-1234-5678 잃어버렸어", {"self_condition": 3}, DRILL_OR_POS),
    # URL 포함 (mask 후 Mock 매칭 약함 — DRILL_OR_POS)
    ("https://x.com 보다가 시간 다 갔어 하기 싫다", {}, DRILL_OR_POS),
    # 학번
    ("20231234 학번인데 진짜 망할 것 같아", {}, DRILL_OR_POS),
]


@pytest.mark.smoke
@pytest.mark.parametrize("text,override,allowed", SCENARIOS, ids=lambda v: str(v)[:40])
def test_smoke_case(text: str, override: dict, allowed: set[str]) -> None:
    label = label_text(text, user_id=f"u_smoke_{hash(text) & 0xffff}", skip_quota=True)
    ctx = {**BASE_CTX, **override}
    out = recommend(label_result=label, context=ctx, user_id="u_smoke")
    assert out["type"] in allowed, f"{text!r} -> expected one of {allowed}, got {out['type']}"


@pytest.mark.smoke
def test_smoke_count() -> None:
    assert len(SCENARIOS) >= 30
