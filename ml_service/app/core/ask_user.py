# 출처: CLAUDE.md §10.4, §4.3
"""약신호 + 컨디션 낮음 → 사용자에게 묻기.

v9.4.4 추가 (ask-first 정책):
- 텍스트(LLM) 신호가 약하지만 맥락 변수 (컨디션/수면/사교) 가 낮을 때,
  바로 드릴 추천하지 않고 "받으실래요?" 먼저 묻는다.
- 사용자 "예" → /recommend/after_ask 호출 시 offer_category 사용해 맥락 기반 드릴 추천.
- 사용자 "아니오" → skip.
"""
from __future__ import annotations

from typing import Optional

from app.schemas.common import CategoryEn, RecommendType


ASK_QUESTION = "유의미한 신호가 약해요. 그래도 드릴 받으시겠어요?"


def build_ask_user(*, reason: str = "신호 약함 + 맥락 애매") -> dict:
    return {
        "type": RecommendType.ASK_USER.value,
        "reason": reason,
        "question": ASK_QUESTION,
        "options": [
            {"value": "yes", "label": "네, 받을게요"},
            {"value": "no", "label": "기록만"},
        ],
    }


def build_skip(message: str = "오늘 기록만 남겨둘게요.") -> dict:
    return {
        "type": RecommendType.SKIP.value,
        "message": message,
    }


# ============================================================================
# v9.4.4: ask-first 정책 — 맥락 기반 드릴 추천 전 사용자 동의 받기.
# ============================================================================

# (reason_type, category, 톤 C 메시지 템플릿)
_DRILL_OFFER_CONFIG = {
    "low_condition": {
        "category": CategoryEn.GROUNDING.value,
        "template": (
            "텍스트는 잔잔한데 컨디션이 좀 낮으시네요 ({value}점). "
            "잠시 그라운딩 해보실래요?"
        ),
        "reason_short": "컨디션 낮음",
    },
    "short_sleep": {
        "category": CategoryEn.SLEEP_CIRCADIAN.value,
        "template": (
            "텍스트는 괜찮은데 어젯밤 잠이 짧으셨네요 ({value}시간). "
            "수면 루틴 드릴 받아보실래요?"
        ),
        "reason_short": "수면 부족",
    },
    "social_conflict": {
        "category": CategoryEn.SELF_COMPASSION.value,
        "template": (
            "텍스트는 잔잔한데 오늘 사람 관계가 좀 힘드셨네요. "
            "자기 자비 드릴 받아보실래요?"
        ),
        "reason_short": "사교 갈등",
    },
}


def build_ask_drill_offer(
    *,
    reason_type: str,
    context_value: Optional[float] = None,
) -> dict:
    """v9.4.4: 약신호 + 맥락 나쁨 시 "드릴 받으실래요?" 카드.

    reason_type: "low_condition" / "short_sleep" / "social_conflict"
    context_value: 컨디션 점수 / 수면 시간 (응답에 노출 — 투명성)

    응답에 offer_category가 포함됨 — FE는 사용자가 "yes" 누르면
    POST /recommend/after_ask 호출 시 user_choice="yes" + offer_category 그대로 전달.
    """
    cfg = _DRILL_OFFER_CONFIG.get(reason_type)
    if not cfg:
        # 알 수 없는 reason_type → 일반 ask_user로 fallback
        return build_ask_user(reason="신호 약함 + 맥락 애매")

    # 값 포맷
    if reason_type == "low_condition" and context_value is not None:
        value_str = f"{int(context_value)}"
    elif reason_type == "short_sleep" and context_value is not None:
        value_str = f"{context_value:.1f}"
    else:
        value_str = ""

    question = cfg["template"].format(value=value_str)
    return {
        "type": RecommendType.ASK_USER.value,
        "reason": f"약신호 + {cfg['reason_short']} — 동의 후 추천",
        "question": question,
        "options": [
            {"value": "yes", "label": "네, 받을게요"},
            {"value": "no", "label": "괜찮아요, 기록만"},
        ],
        # FE가 user_choice="yes" 시 그대로 보내야 할 카테고리 — ask-first 약속
        "offer_category": cfg["category"],
        "offer_reason_type": reason_type,
        "offer_context_value": context_value,
    }
