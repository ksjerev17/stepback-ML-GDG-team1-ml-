# 출처: 명세서 §4.8, §8, §9.2, §9.3
"""/weekly 응답 스키마 — 5블록 + 흐름·패턴 변화·발견·baseline 카드."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Block1Overview(BaseModel):
    recorded_days: int
    avg_self_condition: float
    prev_week_avg: Optional[float] = None
    delta_vs_prev: Optional[float] = None


class Block2DominantPattern(BaseModel):
    dominant_key: str
    ratio_percent: float
    occurrences: int


class Block3DrillAction(BaseModel):
    recommended_count: int
    practiced_count: int
    practice_rate: float


class QuizOption(BaseModel):
    value: str
    label: str


class Block4SelfCheckQuiz(BaseModel):
    """자가진단 퀴즈 응답 — v9.4.3: correct_value·actual_ratio_percent 노출 X.

    정답은 server-side cache(self_check_quiz._quiz_answers)에만 보관.
    PATCH /weekly/quiz가 cache 조회로 정오답 판정."""
    question: str
    options: list[QuizOption]


class Block5CalendarDistribution(BaseModel):
    distribution: dict[str, int]


class FlowPoint(BaseModel):
    dow: str
    avg_condition: Optional[float] = None
    count: int


class ConditionFlow(BaseModel):
    points: list[FlowPoint]


class PatternDiffRow(BaseModel):
    pattern: str
    current_percent: float
    prev_percent: float
    delta_percent: float
    arrow: str  # up / down / flat


class DiscoveryCard(BaseModel):
    """자동 발견 카드 — 4 알고리즘이 만드는 모든 필드 통합 표현."""
    model_config = {"extra": "allow"}  # 향후 알고리즘 추가 시 깨지지 X

    text: str
    category: str
    source: str
    # top_evidence_spans 알고리즘
    count: Optional[int] = None
    # context_pattern_correlation 알고리즘
    low_avg: Optional[float] = None
    high_avg: Optional[float] = None
    delta: Optional[float] = None
    # top_helpful_drill 알고리즘
    drill_id: Optional[int] = None   # v9.5: int
    helpful_ratio: Optional[float] = None
    sample: Optional[int] = None
    # v9.5: weekly_recovery_pattern (주 전반 vs 후반)
    pattern_type: Optional[str] = None  # recovery / fatigue / early_load / late_load
    early_condition_avg: Optional[float] = None
    late_condition_avg: Optional[float] = None
    condition_delta: Optional[float] = None
    early_signal_avg: Optional[float] = None
    late_signal_avg: Optional[float] = None
    sample_early: Optional[int] = None
    sample_late: Optional[int] = None
    # v9.4.x 호환 필드 (옛 클라이언트 — Optional 유지)
    morning_condition_avg: Optional[float] = None
    evening_condition_avg: Optional[float] = None
    morning_signal_avg: Optional[float] = None
    evening_signal_avg: Optional[float] = None
    sample_morning: Optional[int] = None
    sample_evening: Optional[int] = None


class BaselineCard(BaseModel):
    user_id: str
    week: str
    deltas: dict[str, float]
    top_increase: Optional[dict] = None


class EmotionPentagonAxis(BaseModel):
    """v9.4.3 추가: 5각형 한 축 (불안/우울/분노/죄책/중립 중 하나)."""
    label: str
    value: float = Field(..., ge=0.0, le=1.0)


class EmotionPentagon(BaseModel):
    """v9.5: 주간 5감정 분포 — 오각형 radar chart 시각화용.

    7개 entries (일 1회 × 7일) 평균. FE는 axes 5개를 받아 등간 5각형 위에 점 5개 + 다각형 polygon.
    """
    axes: list[EmotionPentagonAxis] = Field(..., min_length=5, max_length=5)
    dominant: str
    entries_used: int = Field(..., ge=0)


# ============================================================================
# v9.6: 주간 개인화 코칭 — 상태 추론 + 경향 narrative + 다음 주 초점
# ============================================================================

class CoachingState(BaseModel):
    model_config = {"extra": "allow"}
    key: str            # recovery / fatigue / loaded / turbulent / stable / low / observing
    label: str          # "회복기" 등 한국어
    summary: str
    confidence: str     # "관찰" / "부족"
    avg_condition: Optional[float] = None


class CoachingTendency(BaseModel):
    model_config = {"extra": "allow"}
    kind: str           # sleep_pattern / condition_pattern / weekday
    text: str
    detail: Optional[str] = None
    strength: str = "관찰"


class CoachingNextFocus(BaseModel):
    category: str
    label_ko: str
    reason: str
    source: str         # state / weekly_signal / personalization / default


class CoachingPersonalizationNote(BaseModel):
    model_config = {"extra": "allow"}
    text: str
    is_active: bool
    top_category: Optional[str] = None
    top_category_label: Optional[str] = None


class WeeklyCoaching(BaseModel):
    """v9.6: 시스템이 사용자와 함께 변화함을 보여주는 개인화 코칭 블록."""
    state: CoachingState
    tendencies: list[CoachingTendency] = Field(default_factory=list)
    tendencies_message: Optional[str] = None
    next_week_focus: CoachingNextFocus
    personalization_note: Optional[CoachingPersonalizationNote] = None
    insufficient: bool = False


class WeeklyReport(BaseModel):
    week: str = Field(..., pattern=r"^\d{4}-W\d{2}$")
    user_id: str
    overview: Block1Overview
    dominant_pattern: Block2DominantPattern
    drill_action: Block3DrillAction
    self_check_quiz: Block4SelfCheckQuiz
    calendar_distribution: Block5CalendarDistribution
    condition_flow: Optional[ConditionFlow] = None
    pattern_diff: Optional[list[PatternDiffRow]] = None
    pattern_diff_message: Optional[str] = None    # v9.5: "분석을 제공하기 위한 데이터가 부족합니다"
    discoveries: Optional[list[DiscoveryCard]] = None
    discoveries_message: Optional[str] = None    # v9.5
    baseline_card: Optional[BaselineCard] = None
    emotion_pentagon: Optional[EmotionPentagon] = None
    insufficient_data: bool = False    # v9.5: 표본 부족 플래그 (recorded_days < 4)
    weekly_coaching: Optional[WeeklyCoaching] = None    # v9.6: 개인화 코칭 블록


# Quiz answer storage
class QuizAnswerRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    week: str = Field(..., pattern=r"^\d{4}-W\d{2}$")
    predicted: str  # 패턴 이름 또는 "모르겠다"


class QuizAnswerResponse(BaseModel):
    user_id: str
    week_of: str
    predicted: str
    correct: str
    match: bool
    is_dont_know: bool
    actual_ratio_percent: float
