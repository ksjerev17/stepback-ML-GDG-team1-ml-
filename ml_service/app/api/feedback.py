# 출처: CLAUDE.md §9.5
"""POST /feedback, GET /feedback. 점수 비공개."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core import feedback_store
from app.core import drill_catalog, personalization
from app.schemas.feedback import FeedbackQueryResponse, FeedbackRequest, FeedbackResponse


router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(req: FeedbackRequest) -> FeedbackResponse:
    try:
        result = feedback_store.upsert_feedback(
            user_id=req.user_id,
            drill_id=req.drill_id,
            rating=req.rating.value,
            recommended_at=req.recommended_at,
            started_at=req.started_at,
            completed_at=req.completed_at,
        )
    except PermissionError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INPUT", "message": str(e)})
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": str(e)})

    # v9.6: 개인화 학습 — 드릴 카테고리별 보상 누적 (helpful/완료).
    try:
        drill = drill_catalog.get_drill(req.drill_id)
        cat = drill.get("category") if drill else None
        if cat:
            personalization.record_outcome(
                req.user_id,
                cat,
                completed=req.completed_at is not None or req.rating.value in ("helpful", "meh"),
                helpful=(req.rating.value == "helpful"),
            )
    except Exception:  # noqa: BLE001 (best-effort — 평가 저장은 이미 성공)
        pass

    return FeedbackResponse(**result)


@router.get("/feedback", response_model=FeedbackQueryResponse)
def get_feedback(user_id: str = Query(..., min_length=1, max_length=64)) -> FeedbackQueryResponse:
    summary = feedback_store.user_summary(user_id)
    return FeedbackQueryResponse(**summary)
