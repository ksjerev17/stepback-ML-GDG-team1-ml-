# 출처: CLAUDE.md §10.3, §4.3
"""긍정 카드 4종 로테이션 — 약신호 + self_condition >= 3."""
from __future__ import annotations

from collections import defaultdict
from typing import Final

from app.schemas.common import RecommendType


POSITIVE_MESSAGES: Final[tuple[str, ...]] = (
    "오늘 평온한 하루였네요.",
    "신호가 잔잔해요. 잘 쉬세요.",
    "오늘은 조용히 흘러가는 하루네요.",
    "별일 없이 지나가는 시간도 소중해요.",
)


_recent_idx: dict[str, int] = defaultdict(int)


def pick_message(user_id: str = "_anon") -> str:
    idx = _recent_idx[user_id] % len(POSITIVE_MESSAGES)
    _recent_idx[user_id] = (idx + 1) % len(POSITIVE_MESSAGES)
    return POSITIVE_MESSAGES[idx]


def build_positive_card(user_id: str, *, reason: str = "신호 약함 + 컨디션 양호") -> dict:
    return {
        "type": RecommendType.POSITIVE_CARD.value,
        "reason": reason,
        "message": pick_message(user_id),
    }
