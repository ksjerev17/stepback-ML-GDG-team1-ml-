# 출처: 명세서 §10.2, §11.1
"""user baseline — 30일 누적 평균. 학습 전용, 사용자 미노출."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaselineSnapshot(BaseModel):
    user_id: str
    patterns_avg: dict[str, float] = Field(default_factory=dict)
    behaviors_avg: dict[str, float] = Field(default_factory=dict)
    emotions_avg: dict[str, float] = Field(default_factory=dict)
    rejected_drills: list[str] = Field(default_factory=list)
    sample_count: int = 0
    window_days: int = 30
    updated_at: datetime


class BaselineCompare(BaseModel):
    """현재 주차 vs baseline 비교 카드용."""
    user_id: str
    week: str
    deltas: dict[str, float]  # {"미래예측": +0.30, "회피미루기": -0.10, ...}
    top_increase: Optional[dict] = None  # {"name": "미래예측", "delta": 0.3, "card": "평소보다 미래예측 30% 높음"}
