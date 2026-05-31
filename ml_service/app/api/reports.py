# 출처: 명세서 §8.1, §11.1
"""GET /reports/pending, PATCH /reports/{id}/read.

reports 테이블 — 매주 일요일 cron이 생성, 사용자 접속 시 인앱 팝업.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query

from app.core import insights_store


router = APIRouter()


@router.get("/reports/pending")
def get_pending_reports(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict:
    rows = insights_store.pending_reports(user_id)
    return {"user_id": user_id, "count": len(rows), "items": rows}


@router.post("/reports")
def post_report_seed(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    week_of: Annotated[str, Body(pattern=r"^\d{4}-W\d{2}$")],
    pattern_analysis: Annotated[dict, Body()],
    emotion_distribution: Annotated[dict, Body()],
) -> dict:
    """일요일 cron이 호출 — 주간 리포트 row 생성 ('pending'). BE에서도 동일 흐름."""
    return insights_store.upsert_report(
        user_id=user_id,
        week_of=week_of,
        pattern_analysis=pattern_analysis,
        emotion_distribution=emotion_distribution,
    )


@router.patch("/reports/{report_id}/read")
def patch_report_read(
    report_id: int,
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict:
    ok = insights_store.mark_report_read(user_id=user_id, report_id=report_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"code": "INVALID_INPUT", "message": "report not found or already read"},
        )
    return {"report_id": report_id, "user_id": user_id, "status": "read"}
