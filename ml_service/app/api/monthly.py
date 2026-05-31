# 출처: v9.5 월간 리포트.
"""POST /monthly — 월간 리포트 빌더 경로.

GET /monthly 는 데모용 — BE는 POST /monthly로 실 entries 전달.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

from app.core.monthly_report import build_monthly_report
from app.schemas.monthly import MonthlyReport


router = APIRouter()


class MonthlyRequest(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    user_id: str = Field(..., min_length=1, max_length=64)
    entries: list[dict] = Field(default_factory=list, max_length=40)
    drills_recommended: int = Field(0, ge=0, le=100)
    drills_practiced: int = Field(0, ge=0, le=100)


@router.post("/monthly", response_model=MonthlyReport)
def post_monthly(req: MonthlyRequest) -> MonthlyReport:
    raw = build_monthly_report(
        month=req.month,
        user_id=req.user_id,
        entries=req.entries,
        drills_recommended=req.drills_recommended,
        drills_practiced=req.drills_practiced,
    )
    return MonthlyReport.model_validate(raw)


@router.get("/monthly", response_model=MonthlyReport)
def get_monthly_demo(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")] = "2026-05",
) -> MonthlyReport:
    """데모용 — 일 1회 × 30일 가상 entries."""
    from datetime import datetime, timezone, timedelta

    year_s, mo_s = month.split("-")
    year, mo = int(year_s), int(mo_s)
    if mo == 12:
        next_first = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_first = datetime(year, mo + 1, 1, tzinfo=timezone.utc)
    days_in_month = (next_first - datetime(year, mo, 1, tzinfo=timezone.utc)).days

    demo_entries = []
    doms = [
        "emotion_anxiety", "cognitive_dominant", "weak_signal_positive",
        "emotion_depression", "behavior_dominant", "emotion_anger",
        "weak_signal_positive", "cognitive_dominant",
    ]
    for d in range(1, days_in_month + 1):
        dom = doms[(d - 1) % len(doms)]
        # 컨디션 — 주 후반에 회복 패턴 흉내
        dt = datetime(year, mo, d, 19, 0, tzinfo=timezone.utc)
        dow = dt.isoweekday()
        sc = 2 if dow <= 3 else 4
        demo_entries.append({
            "created_at": dt.isoformat(),
            "self_condition": sc,
            "label_result": {
                "patterns": {"미래예측": 0.5 if dom == "cognitive_dominant" else 0.1,
                             "독심술": 0, "자기비난": 0, "이분법": 0,
                             "당위진술": 0, "과잉일반화": 0},
                "behaviors": {"회피미루기": 0.5 if dom == "behavior_dominant" else 0,
                              "동기저하": 0},
                "emotions": {"불안": 0.6 if dom == "emotion_anxiety" else 0.1,
                             "우울": 0.6 if dom == "emotion_depression" else 0.1,
                             "분노": 0.6 if dom == "emotion_anger" else 0.05,
                             "죄책": 0.05, "중립": 0.3},
                "calendar_dominant": dom,
            },
        })

    raw = build_monthly_report(
        month=month,
        user_id=user_id,
        entries=demo_entries,
        drills_recommended=days_in_month,
        drills_practiced=int(days_in_month * 0.6),
    )
    return MonthlyReport.model_validate(raw)
