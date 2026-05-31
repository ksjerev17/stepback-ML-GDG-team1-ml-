# 출처: CLAUDE.md §4.2, §9.3
"""/recommend 요청·응답 스키마."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import SocialToday
from .label import LabelResult


class Context(BaseModel):
    """v9.4.3 §4.3: 맥락 변수 4개 모두 필수 입력.

    기본값은 BE에서 채워서 전달 (§4.2 일 1회 입력 — 캐시된 값 또는 기본값).
    ML 입장에서는 4개 모두 명시 전달되어야 함.
    """
    self_condition: int = Field(..., ge=1, le=5)
    sleep_hours: float = Field(..., ge=0.0, le=12.0)
    social_today: SocialToday = Field(...)
    exercise_today: float = Field(..., ge=0.0, le=12.0)


class RecommendRequest(BaseModel):
    label_result: LabelResult
    context: Context
    user_id: str = Field(..., min_length=1, max_length=64)
    recent_drill_ids: list[int] = Field(default_factory=list, max_length=20)   # v9.5: int


class DrillPayload(BaseModel):
    id: int   # v9.5: ERD INT 호환
    name: str
    category: str
    duration_min: int
    instruction: str
    citation: str


class Copy3(BaseModel):
    line1: Optional[str] = None
    line2: str
    line3: str


class WhyFactor(BaseModel):
    """v9.6: 추천 근거 1개 (FE가 칩/아이콘으로 표시)."""
    model_config = ConfigDict(extra="allow")
    kind: str            # context / pattern / behavior / emotion / evidence
    label: str
    detail: Optional[str] = None
    phrase: Optional[str] = None


class WhyExplanation(BaseModel):
    """v9.6: "왜 이 드릴인지" 설명가능 추천. v9.7: 효용성·근거 추가."""
    text: str                       # 사용자 노출용 한 줄 (왜 골랐는지)
    factors: list[WhyFactor] = []   # 구조화 근거
    tone: str = "neutral"
    expected_benefit: Optional[str] = None   # v9.7: 이 드릴이 줄 도움 (효용성)
    mechanism: Optional[str] = None          # v9.7: 학술 근거 한 줄 (신뢰성/차별성)


class CrisisCardOption(BaseModel):
    value: str
    label: str


import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message=r'Field name "copy" .* shadows an attribute')

    class RecommendResponse(BaseModel):
        type: str
        reason: Optional[str] = None
        tone: Optional[str] = None          # v9.6: neutral / positive
        drill: Optional[DrillPayload] = None
        copy: Optional[Copy3] = None
        why: Optional[WhyExplanation] = None    # v9.6: 설명가능 추천
        crisis_resources: Optional[dict[str, str]] = None
        user_message: Optional[str] = None
        message: Optional[str] = None
        question: Optional[str] = None
        options: Optional[list[CrisisCardOption]] = None
        # v9.4.4: ask-first 정책 — ask_drill_offer 카드의 약속 정보
        offer_category: Optional[str] = None
        offer_reason_type: Optional[str] = None
        offer_context_value: Optional[float] = None
