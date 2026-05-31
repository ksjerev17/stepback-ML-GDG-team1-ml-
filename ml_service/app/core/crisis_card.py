# 출처: CLAUDE.md §10.2, §9.3
"""위기 카드 응답 — 드릴 절대 X. 1393/1388/1577-0199 안내."""
from __future__ import annotations

from app.schemas.common import CRISIS_RESOURCES, RecommendType


CRISIS_MESSAGE = "지금 많이 힘드신 것 같아요. 혼자 견디지 마세요."


def build_crisis_card() -> dict:
    return {
        "type": RecommendType.CRISIS_CARD.value,
        "reason": "위기 신호 감지 — 일반 드릴 차단",
        "crisis_resources": dict(CRISIS_RESOURCES),
        "user_message": CRISIS_MESSAGE,
    }
