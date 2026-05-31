# 출처: CLAUDE.md §5, §9.2
"""/label 요청·응답 스키마."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO


class LabelRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)   # v9.5: 자유 일기형 (200→500)
    user_id: str = Field(..., min_length=1, max_length=64)

    @field_validator("text")
    @classmethod
    def _validate_meaningful_text(cls, v: str) -> str:
        """v9.4.3: 공백만·이모지만·반복문자만 거절."""
        # 1) 공백·탭·줄바꿈 제거 후 빈 문자열
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must contain non-whitespace characters")

        # 2) 한글·영문·숫자가 최소 1개라도 있어야 함 (이모지/특수문자만 거절)
        import re
        if not re.search(r"[\w가-힣]", stripped):
            raise ValueError("text must contain at least one letter, digit, or Korean character")

        # 3) 같은 문자만 반복 (예: "ㅋㅋㅋㅋㅋㅋ" 또는 "aaaaa") 거절
        # — 고유 문자 1종이고 길이 3 이상이면 거절
        if len(stripped) >= 3 and len(set(stripped.replace(" ", ""))) == 1:
            raise ValueError("text must not be a single repeated character")

        return v


class PatternScores(BaseModel):
    미래예측: float = Field(0.0, ge=0.0, le=1.0)
    독심술: float = Field(0.0, ge=0.0, le=1.0)
    자기비난: float = Field(0.0, ge=0.0, le=1.0)
    이분법: float = Field(0.0, ge=0.0, le=1.0)
    당위진술: float = Field(0.0, ge=0.0, le=1.0)
    과잉일반화: float = Field(0.0, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in PATTERNS_KO}


class BehaviorScores(BaseModel):
    회피미루기: float = Field(0.0, ge=0.0, le=1.0)
    동기저하: float = Field(0.0, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in BEHAVIORS_KO}


class EmotionScores(BaseModel):
    불안: float = Field(0.0, ge=0.0, le=1.0)
    우울: float = Field(0.0, ge=0.0, le=1.0)
    분노: float = Field(0.0, ge=0.0, le=1.0)
    죄책: float = Field(0.0, ge=0.0, le=1.0)
    중립: float = Field(0.0, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {k: getattr(self, k) for k in EMOTIONS_KO}


class LabelResult(BaseModel):
    patterns: dict[str, float]
    behaviors: dict[str, float]
    emotions: dict[str, float]
    intensity: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence_span: str = ""
    crisis_detected: bool = False
    calendar_dominant: str = "weak_signal_positive"
    model_used: str = "mock"
    clarified_winner: Optional[str] = None
    labeled_at: datetime

    confidence_raw: Optional[float] = None
    confidence_adjusted_by: Optional[str] = None
    evidence_span_raw: Optional[str] = None
    evidence_span_adjusted: Optional[str] = None
    clarification_applied: Optional[dict] = None
    clarification_skipped: Optional[str] = None
    clarification_reason: Optional[str] = None
    # v9.5: 디자인 로딩 안내용 메타 (선택)
    processing_time_ms: Optional[int] = None
