# 출처: CLAUDE.md §4.4, §9.5
"""/feedback 요청·응답 스키마."""
from __future__ import annotations

from datetime import date as DateT
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Rating(str, Enum):
    HELPFUL = "helpful"
    MEH = "meh"
    UNHELPFUL = "unhelpful"


class FeedbackRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    drill_id: int = Field(..., ge=1, le=9999)   # v9.5: ERD INT 호환
    rating: Rating
    recommended_at: DateT
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FeedbackResponse(BaseModel):
    accepted: bool
    can_edit_until: datetime


class FeedbackQueryResponse(BaseModel):
    """GET /feedback — 응답에 점수 노출 X. 메타데이터만."""
    user_id: str
    total_count: int
    last_rated_at: Optional[datetime] = None
