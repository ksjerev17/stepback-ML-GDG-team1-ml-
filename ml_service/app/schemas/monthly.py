# 출처: v9.5 월간 리포트.
"""월간 리포트 스키마."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MonthlyOverview(BaseModel):
    recorded_days: int
    total_entries: int
    avg_self_condition: float


class MonthlyDominantPattern(BaseModel):
    dominant_key: str
    ratio_percent: float
    occurrences: int
    total_strong: int


class MonthlyCalendarDistribution(BaseModel):
    distribution: dict[str, int]


class MonthlyEmotionPentagonAxis(BaseModel):
    label: str
    value: float = Field(..., ge=0.0, le=1.0)


class MonthlyEmotionPentagon(BaseModel):
    axes: list[MonthlyEmotionPentagonAxis] = Field(..., min_length=5, max_length=5)
    dominant: str
    entries_used: int = Field(..., ge=0)


class MonthlyConditionTrendWeek(BaseModel):
    week_in_month: int = Field(..., ge=1, le=5)
    avg_condition: Optional[float] = None
    count: int


class MonthlyConditionTrend(BaseModel):
    weeks: list[MonthlyConditionTrendWeek]


class MonthlyDrillAction(BaseModel):
    recommended_count: int
    practiced_count: int
    practice_rate: float


class MonthlyReport(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    user_id: str
    overview: MonthlyOverview
    dominant_pattern: MonthlyDominantPattern
    calendar_distribution: MonthlyCalendarDistribution
    emotion_pentagon: MonthlyEmotionPentagon
    condition_trend: MonthlyConditionTrend
    drill_action: MonthlyDrillAction
    monthly_coaching: Optional[dict] = None   # v9.6: 장기 코칭 (additive, FE optional)
