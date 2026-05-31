# 출처: 명세서 §8.4, §8.5, §11.1
"""user_insights — 자기 발견 저장 (자동·사용자)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InsightSource(str, Enum):
    SYSTEM = "system"
    USER = "user"


class InsightCategory(str, Enum):
    COGNITIVE = "cognitive"
    BEHAVIOR = "behavior"
    EMOTION = "emotion"
    CONTEXT = "context"
    DRILL = "drill"


class InsightItem(BaseModel):
    insight_id: Optional[int] = None
    user_id: str
    text: str = Field(..., min_length=1, max_length=400)
    source: InsightSource
    category: InsightCategory
    week_of: str = Field(..., pattern=r"^\d{4}-W\d{2}$")
    report_id: Optional[int] = None
    created_at: Optional[datetime] = None


class InsightCreate(BaseModel):
    user_id: str
    text: str = Field(..., min_length=1, max_length=400)
    category: InsightCategory = InsightCategory.COGNITIVE
    week_of: str = Field(..., pattern=r"^\d{4}-W\d{2}$")
    report_id: Optional[int] = None


class InsightList(BaseModel):
    user_id: str
    items: list[InsightItem]
