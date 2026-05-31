# 출처: 명세서 §9.1 + §7.3 dominant 8색 / v9.5 일 1회 정책
"""GET /calendar?user_id=&month=YYYY-MM — 월간 캘린더 dominant 분포.

ML 단독으로는 entries 보관 X. BE가 한 달치 entries 전달.
ML이 직접 호출 시 데모용 가상 entries 생성.

v9.5 일 1회 정책:
- 일별 entry는 1개 (slots 길이 = 1 일반)
- time_of_day 필드는 옛 호환만 — 일 1회 정책에선 의미 X (옵셔널 유지)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel


router = APIRouter()


class DailyDot(BaseModel):
    date: str
    # v9.5 일 1회 정책: 일반적으로 slots 길이 = 1.
    # 옛 데이터 호환을 위해 list 유지 (max 3 — 옛 일 3회 데이터 호환).
    slots: list[dict]
    avg_condition: float | None = None


class MonthlyCalendar(BaseModel):
    user_id: str
    month: str
    days: list[DailyDot]


def _build_calendar(user_id: str, month: str, entries: list[dict]) -> dict:
    by_date: dict[str, list[dict]] = defaultdict(list)
    cond_by_date: dict[str, list[int]] = defaultdict(list)
    for e in entries:
        try:
            dt = datetime.fromisoformat(e["created_at"])
        except (KeyError, ValueError):
            continue
        d = dt.date().isoformat()
        if not d.startswith(month):
            continue
        by_date[d].append({
            "time_of_day": e.get("time_of_day"),
            "dominant": (e.get("label_result", {}) or {}).get("calendar_dominant", "weak_signal_positive"),
        })
        sc = e.get("self_condition")
        if sc is not None:
            cond_by_date[d].append(int(sc))

    days: list[dict] = []
    for d in sorted(by_date.keys()):
        slots = by_date[d][:3]  # 최대 3개
        cond_vals = cond_by_date.get(d, [])
        days.append({
            "date": d,
            "slots": slots,
            "avg_condition": round(sum(cond_vals) / len(cond_vals), 2) if cond_vals else None,
        })
    return {"user_id": user_id, "month": month, "days": days}


def _demo_entries_for_calendar(month: str) -> list[dict]:
    """v9.5: GET /calendar 데모용 entries — 일 1회 정책 (서로 다른 5일).

    실서비스에서는 BE가 POST /calendar로 실 entries 전달.
    """
    return [
        {"created_at": f"{month}-15T09:00:00+00:00",
         "label_result": {"calendar_dominant": "emotion_anxiety"}, "self_condition": 3},
        {"created_at": f"{month}-16T09:00:00+00:00",
         "label_result": {"calendar_dominant": "cognitive_dominant"}, "self_condition": 4},
        {"created_at": f"{month}-17T09:00:00+00:00",
         "label_result": {"calendar_dominant": "weak_signal_positive"}, "self_condition": 4},
        {"created_at": f"{month}-18T09:00:00+00:00",
         "label_result": {"calendar_dominant": "behavior_dominant"}, "self_condition": 2},
        {"created_at": f"{month}-19T09:00:00+00:00",
         "label_result": {"calendar_dominant": "emotion_depression"}, "self_condition": 2},
    ]


@router.get("/calendar", response_model=MonthlyCalendar)
def get_calendar(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")] = date.today().strftime("%Y-%m"),
    demo: Annotated[bool, Query()] = False,
) -> MonthlyCalendar:
    """v9.4.3: 데모용 — demo=true 시 가상 entries로 캘린더 채움. 실서비스는 POST /calendar."""
    entries = _demo_entries_for_calendar(month) if demo else []
    return MonthlyCalendar.model_validate(_build_calendar(user_id, month, entries))


@router.post("/calendar", response_model=MonthlyCalendar)
def post_calendar(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    month: Annotated[str, Body(pattern=r"^\d{4}-\d{2}$")],
    entries: Annotated[list[dict], Body()],
) -> MonthlyCalendar:
    return MonthlyCalendar.model_validate(_build_calendar(user_id, month, entries))


class DailyDetailResponse(BaseModel):
    user_id: str
    date: str
    entries: list[dict]  # text·context·llm_result.calendar_dominant·drill_id·drill_complete (helpful 비공개)


@router.post("/daily", response_model=DailyDetailResponse)
def post_daily_detail(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    target_date: Annotated[str, Body(pattern=r"^\d{4}-\d{2}-\d{2}$", alias="date")],
    entries: Annotated[list[dict], Body()],
) -> DailyDetailResponse:
    """v9.4.3: 일별 상세 모달 — 평가(helpful) 비공개. drill_complete만 노출."""
    cleaned: list[dict] = []
    for e in entries:
        if not str(e.get("created_at", "")).startswith(target_date):
            continue
        cleaned.append({
            "time_of_day": e.get("time_of_day"),
            "text": e.get("text"),
            "self_condition": e.get("self_condition"),
            "context": e.get("context"),
            "calendar_dominant": (e.get("label_result", {}) or {}).get("calendar_dominant"),
            "drill_id": e.get("drill_id"),
            "drill_title": e.get("drill_title"),
            "drill_complete": bool(e.get("drill_complete", False)),
            # helpful은 의도적으로 제외 (§9.1, §4.4)
        })
    return DailyDetailResponse(user_id=user_id, date=target_date, entries=cleaned)
