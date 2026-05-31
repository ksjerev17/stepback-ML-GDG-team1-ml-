# 출처: CLAUDE.md §9.2 + 운영 보강 (metrics) + v9.4.3 §4.2 (context cache)
"""POST /label + GET /context/today (BE 조회용)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.labeler import (
    _kst_day_str,
    apply_context_cache,
    cache_context,
    get_cached_context,
    label_text,
)
from app.infra.metrics import Timer, get_metrics
from app.infra.quota_manager import QuotaExceededError
from app.schemas.label import LabelRequest, LabelResult
from app.schemas.recommend import Context


router = APIRouter()


@router.post("/label", response_model=LabelResult)
def post_label(req: LabelRequest) -> LabelResult:
    get_metrics().incr("label_request", "total")
    with Timer("label_latency"):
        try:
            raw = label_text(req.text, req.user_id)
        except QuotaExceededError as e:
            get_metrics().incr("label_quota_exceeded", e.scope)
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "QUOTA_EXCEEDED",
                    "message": str(e),
                    "scope": e.scope,
                    "retry_after_seconds": e.retry_after_seconds,
                },
            )
    if raw.get("crisis_detected"):
        get_metrics().incr("label_crisis_detected", "true")
    return LabelResult.model_validate(raw)


class ContextTodayResponse(BaseModel):
    """v9.4.3 §4.2: BE가 같은 날 두 번째·세 번째 입력 시 호출.

    sleep_hours / social_today / exercise_today 3개를 캐시 또는 기본값으로 반환.
    self_condition은 캐시 X (매번 입력).
    """
    user_id: str
    day: str
    cached: bool = Field(description="True = 캐시에서 가져옴 / False = 기본값")
    sleep_hours: float
    social_today: str
    exercise_today: float


@router.get("/context/today", response_model=ContextTodayResponse)
def get_context_today(
    user_id: str = Query(..., min_length=1, max_length=64),
) -> ContextTodayResponse:
    """v9.4.3 §4.2: 오늘 입력했던 맥락 변수 (sleep/social/exercise) 조회.

    BE가 입력 화면에서 호출:
    - cached=True → 사용자에게 "어제 잠 몇 시간"·"오늘 사교" 등 물어볼 필요 X
    - cached=False → 첫 입력. 사용자에게 4개 모두 물어봄 (기본값 prefill).
    """
    day = _kst_day_str()
    cached = get_cached_context(user_id, day)
    if cached is not None:
        return ContextTodayResponse(
            user_id=user_id,
            day=day,
            cached=True,
            sleep_hours=float(cached.get("sleep_hours", 7.0)),
            social_today=str(cached.get("social_today", "보통")),
            exercise_today=float(cached.get("exercise_today", 0.0)),
        )
    return ContextTodayResponse(
        user_id=user_id,
        day=day,
        cached=False,
        sleep_hours=7.0,
        social_today="보통",
        exercise_today=0.0,
    )


class CacheContextRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    sleep_hours: float = Field(..., ge=0.0, le=12.0)
    social_today: str
    exercise_today: float = Field(..., ge=0.0, le=12.0)


@router.post("/context/today", response_model=ContextTodayResponse)
def post_context_today(req: CacheContextRequest) -> ContextTodayResponse:
    """v9.4.3 §4.2: 사용자가 맥락 변수 입력 시 (첫 입력 또는 명시 갱신) BE가 호출.

    하루 1회 입력 원칙 — 같은 날 후속 입력에는 이 캐시 값을 재사용.
    """
    day = _kst_day_str()
    cache_context(req.user_id, day, {
        "sleep_hours": req.sleep_hours,
        "social_today": req.social_today,
        "exercise_today": req.exercise_today,
    })
    return ContextTodayResponse(
        user_id=req.user_id,
        day=day,
        cached=True,
        sleep_hours=req.sleep_hours,
        social_today=req.social_today,
        exercise_today=req.exercise_today,
    )



class UserDataExport(BaseModel):
    """v9.4.3 P2: GDPR — 사용자가 자기 ML 측 데이터 조회.

    ML은 entries 보관 X (BE 영역). ML 측만 보유한 것:
    - 오늘 캐시된 맥락 변수 (sleep/social/exercise)
    - audit log (사용자 hash로만 — 조회 불가)
    """
    user_id: str
    cached_context_today: dict | None
    note: str


@router.get("/export/user_data", response_model=UserDataExport)
def export_user_data(
    user_id: str = Query(..., min_length=1, max_length=64),
) -> UserDataExport:
    """v9.4.3 P2: 사용자의 ML 측 데이터 조회.

    entries·feedback·insights 등은 BE의 PostgreSQL이 보유.
    ML 측은 메모리 캐시(맥락 변수)와 audit log(hash)만 가짐.
    audit log는 user_hash만 저장되어 평문 조회 불가 (의도된 설계).
    """
    day = _kst_day_str()
    cached = get_cached_context(user_id, day)
    return UserDataExport(
        user_id=user_id,
        cached_context_today=cached,
        note=(
            "ML 서비스는 entries·feedback을 보관하지 않습니다. "
            "전체 데이터 export는 BE의 GET /api/me/export를 사용하세요. "
            "ML 측은 오늘 캐시된 맥락 변수만 가집니다 (다른 날짜·다른 데이터 없음)."
        ),
    )
