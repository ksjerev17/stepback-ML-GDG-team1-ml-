# 출처: CLAUDE.md §5, §9
"""공통 상수 + Enum."""
from __future__ import annotations

from enum import Enum
from typing import Final


PATTERNS_KO: Final[tuple[str, ...]] = (
    "미래예측", "독심술", "자기비난", "이분법", "당위진술", "과잉일반화",
)
BEHAVIORS_KO: Final[tuple[str, ...]] = ("회피미루기", "동기저하")
EMOTIONS_KO: Final[tuple[str, ...]] = ("불안", "우울", "분노", "죄책", "중립")


class CategoryEn(str, Enum):
    COGNITIVE_RESTRUCTURING = "cognitive_restructuring"
    BEHAVIORAL_ACTIVATION = "behavioral_activation"
    HABIT_DESIGN = "habit_design"
    GROUNDING = "grounding"
    SELF_COMPASSION = "self_compassion"
    SLEEP_CIRCADIAN = "sleep_circadian"


# v9.5: 와이어프레임 캘린더 색·라벨 매핑.
# FE는 entry 응답의 drill_category로 색깔 결정.
CATEGORY_LABEL_KO: Final[dict[str, str]] = {
    "cognitive_restructuring": "생각 전환",
    "behavioral_activation": "산책",
    "habit_design": "긍정 확언",
    "grounding": "마음 챙김",
    "self_compassion": "자기 자비",
    "sleep_circadian": "수면 정돈",
}

# FE에서 사용할 캘린더 색 키 (소프트 톤). 실제 hex는 FE가 디자인 토큰으로 매핑.
CATEGORY_CALENDAR_COLOR: Final[dict[str, str]] = {
    "cognitive_restructuring": "pink_soft",
    "behavioral_activation": "white_soft",
    "habit_design": "pink_warm",
    "grounding": "green_calm",
    "self_compassion": "lavender",
    "sleep_circadian": "blue_night",
}


class SocialToday(str, Enum):
    GOOD = "좋음"
    NORMAL = "보통"
    CONFLICT = "갈등"


class RecommendType(str, Enum):
    DRILL = "drill"
    CRISIS_CARD = "crisis_card"
    POSITIVE_CARD = "positive_card"
    ASK_USER = "ask_user"
    SKIP = "skip"


class CalendarDominant(str, Enum):
    CRISIS = "crisis"
    COGNITIVE_DOMINANT = "cognitive_dominant"
    BEHAVIOR_DOMINANT = "behavior_dominant"
    EMOTION_ANGER = "emotion_anger"
    EMOTION_ANXIETY = "emotion_anxiety"
    EMOTION_DEPRESSION = "emotion_depression"
    EMOTION_GUILT = "emotion_guilt"
    WEAK_SIGNAL_POSITIVE = "weak_signal_positive"
    WEAK_SIGNAL_LOW = "weak_signal_low"


# v9.5: 디자인 캘린더 상세 화면의 한국어 태그 매핑.
# 사용자 노출용 짧은 라벨 — "안정", "불안" 등.
CALENDAR_DOMINANT_LABEL_KO: Final[dict[str, str]] = {
    "crisis": "주의",
    "cognitive_dominant": "사고 패턴",
    "behavior_dominant": "회피·미루기",
    "emotion_anger": "분노",
    "emotion_anxiety": "불안",
    "emotion_depression": "우울",
    "emotion_guilt": "죄책",
    "weak_signal_positive": "안정",
    "weak_signal_low": "잔잔",
}


CRISIS_RESOURCES: Final[dict[str, str]] = {
    "자살예방상담": "1393",
    "청소년상담": "1388",
    "정신건강위기상담": "1577-0199",
}


ERROR_CODES: Final[dict[str, int]] = {
    "INVALID_INPUT": 400,
    "VALIDATION_ERROR": 422,
    "QUOTA_EXCEEDED": 429,
    "ML_UNAVAILABLE": 503,
    "INTERNAL_ERROR": 500,
}
