# 출처: CLAUDE.md §4.9, §10.6
"""자가 진단 퀴즈 — 수치 미리 노출 + 4지선다 (정답 + 같은 그룹 오답 2 + '모르겠다').

v9.4.3 보안 패치: 정답(correct_value)을 응답에 노출 X.
GET /weekly 응답에는 정답 제외. 정답은 server-side cache에만 보관.
PATCH /weekly/quiz는 cache lookup으로 정오답 판정.
"""
from __future__ import annotations

import random
import threading
from typing import Sequence

from app.schemas.common import PATTERNS_KO


DONT_KNOW_LABEL = "모르겠다"
DONT_KNOW_VALUE = "모르겠다"


# (user_id, week) → {correct_value, actual_ratio_percent}
# v9.4.3 보안: 정답을 응답 JSON에 박지 X. server-side cache만.
_quiz_answers: dict[tuple[str, str], dict[str, object]] = {}
_lock = threading.Lock()


def _cache_answer(user_id: str, week: str, correct: str, actual_ratio: float) -> None:
    with _lock:
        _quiz_answers[(user_id, week)] = {
            "correct_value": correct,
            "actual_ratio_percent": round(actual_ratio, 1),
        }


def get_cached_answer(user_id: str, week: str) -> dict[str, object] | None:
    """PATCH /weekly/quiz에서 사용 — 응답에 노출 X, server-side만."""
    with _lock:
        return _quiz_answers.get((user_id, week))


def clear_cache() -> None:
    """테스트 reset 용."""
    with _lock:
        _quiz_answers.clear()


def build_quiz(
    *,
    dominant_pattern: str,
    actual_ratio_percent: float,
    rng: random.Random | None = None,
    pool: Sequence[str] = PATTERNS_KO,
    user_id: str | None = None,
    week: str | None = None,
) -> dict:
    """수치를 미리 노출하고 사용자가 패턴을 맞히는 4지선다.

    v9.4.3: correct_value·actual_ratio_percent는 응답에 노출 X.
    user_id + week가 주어지면 server-side cache에 정답 저장.
    """
    rng = rng or random.Random()
    if dominant_pattern not in pool:
        dominant_pattern = pool[0]
    distractors = [p for p in pool if p != dominant_pattern]
    rng.shuffle(distractors)
    chosen = [dominant_pattern, *distractors[:2]]
    rng.shuffle(chosen)
    options = [{"value": p, "label": p} for p in chosen]
    options.append({"value": DONT_KNOW_VALUE, "label": DONT_KNOW_LABEL})

    # server-side cache (응답에 정답 X)
    if user_id and week:
        _cache_answer(user_id, week, dominant_pattern, actual_ratio_percent)

    return {
        "question": (
            f"이번 주 가장 자주 보인 패턴이 {actual_ratio_percent:.0f}%였어요. 무엇이었을까요?"
        ),
        "options": options,
        # v9.4.3: correct_value, actual_ratio_percent는 응답에서 제외 (보안).
    }
