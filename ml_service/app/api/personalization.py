# 출처: v9.6 — 개인화 엔진 노출 엔드포인트.
"""GET /personalization/profile, POST /personalization/event, GET /personalization/next_focus.

개인화 학습 결과(카테고리별 보상·UCB 가산점)를 BE/FE가 조회·갱신.
- 보통은 POST /entries, POST /feedback, POST /reject가 자동으로 학습을 갱신하므로
  BE는 이 엔드포인트를 직접 호출할 필요가 거의 없다.
- /event는 BE가 별도 경로로 결과를 푸시하고 싶을 때를 위한 보조 채널.
- /profile, /next_focus는 FE가 "지금까지 X가 잘 맞으셨어요" 카드를 그릴 때 사용.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core import personalization
from app.core.weekly_coaching import build_next_week_focus

router = APIRouter()


@router.get("/personalization/profile")
def get_profile(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict:
    """사용자 개인화 프로파일 — 카테고리별 통계·보상 추정·UCB 가산점.

    reward_estimate는 사용자 본인의 선택(완료/도움됨/거부)을 집계한 값이라 노출 허용
    (라벨링 내부 점수와 달라 §13 점수 비공개 정책에 저촉되지 않음).
    """
    return personalization.get_profile(user_id)


class PersonalizationEvent(BaseModel):
    """BE가 학습 이벤트를 직접 푸시할 때 사용 (보조 채널)."""
    user_id: str = Field(..., min_length=1, max_length=64)
    category: str = Field(..., min_length=1, max_length=64)
    event: Literal["offer", "complete", "helpful", "reject"]


@router.post("/personalization/event")
def post_event(req: PersonalizationEvent) -> dict:
    """개인화 학습 이벤트 1건 반영."""
    if req.event == "offer":
        personalization.record_offer(req.user_id, req.category)
    elif req.event == "complete":
        personalization.record_outcome(req.user_id, req.category, completed=True, helpful=False)
    elif req.event == "helpful":
        personalization.record_outcome(req.user_id, req.category, completed=True, helpful=True)
    elif req.event == "reject":
        personalization.record_reject(req.user_id, req.category)
    return {"accepted": True, "user_id": req.user_id, "category": req.category, "event": req.event}


@router.get("/personalization/next_focus")
def get_next_focus(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    state_key: Annotated[str, Query()] = "stable",
) -> dict:
    """다음 주 추천 초점 — 개인화 프로파일 기반 (entries 없이 프로파일만으로).

    주간 리포트의 weekly_coaching.next_week_focus와 동일 로직.
    BE/FE가 entries를 다시 보내지 않고 빠르게 초점만 받고 싶을 때.
    """
    return build_next_week_focus([], user_id, state_key=state_key)
