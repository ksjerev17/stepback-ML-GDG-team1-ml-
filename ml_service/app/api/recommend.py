# 출처: CLAUDE.md §9.3 + v9.4.3 §4.3 ask_user 후속 흐름
"""POST /recommend, POST /recommend/after_ask."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.recommender import recommend, recommend_after_ask_user
from app.core import personalization
from app.schemas.common import RecommendType
from app.schemas.recommend import Context, RecommendRequest, RecommendResponse, LabelResult


router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
def post_recommend(req: RecommendRequest) -> RecommendResponse:
    raw = recommend(
        label_result=req.label_result.model_dump(),
        context=req.context.model_dump(mode="json"),
        user_id=req.user_id,
        recent_drill_ids=req.recent_drill_ids,
        pref_bonus=personalization.bonus_map(req.user_id),  # v9.6 개인화
    )
    _record_offer_if_drill(req.user_id, raw)
    return RecommendResponse.model_validate(raw)


class AfterAskRequest(BaseModel):
    """v9.4.3/4 §4.3: ask_user 응답 후 사용자 선택을 받아 다음 단계 진행.

    v9.4.4: offer_category 필드 추가 — ask-first 정책 지원.
    FE는 ask_drill_offer 카드의 응답에 담긴 offer_category 값을 그대로 재전송.
    """
    label_result: LabelResult
    context: Context
    user_id: str = Field(..., min_length=1, max_length=64)
    recent_drill_ids: list[int] = Field(default_factory=list, max_length=20)
    user_choice: Literal["yes", "no", "tie", "skip"]
    # tie 응답 시 — clarify 정밀화에서 어느 후보 선택했는지 (선택)
    chosen_candidate: str | None = None
    # v9.4.4: ask_drill_offer 카드가 약속한 카테고리 (서버가 카드에 박아 보낸 값)
    offer_category: str | None = None


@router.post("/recommend/after_ask", response_model=RecommendResponse)
def post_recommend_after_ask(req: AfterAskRequest) -> RecommendResponse:
    """v9.4.3/4 §4.3: ask_user 응답 처리.

    - user_choice="yes" + offer_category (v9.4.4) → 약속한 카테고리 드릴 추천
    - user_choice="yes" + offer_category 없음 → 상태값 기반 보조 드릴
    - user_choice="no" or "skip" → skip 응답 (기록만)
    - user_choice="tie" → 사용자 선택 후보 카테고리 드릴
    """
    raw = recommend_after_ask_user(
        label_result=req.label_result.model_dump(),
        context=req.context.model_dump(mode="json"),
        user_id=req.user_id,
        recent_drill_ids=req.recent_drill_ids,
        user_choice=req.user_choice,
        chosen_candidate=req.chosen_candidate,
        offer_category=req.offer_category,
        pref_bonus=personalization.bonus_map(req.user_id),  # v9.6 개인화
    )
    _record_offer_if_drill(req.user_id, raw)
    return RecommendResponse.model_validate(raw)


def _record_offer_if_drill(user_id: str, raw: dict) -> None:
    """v9.6: 드릴 추천일 때 개인화 노출 카운트 기록 (best-effort)."""
    try:
        drill = raw.get("drill") if isinstance(raw, dict) else None
        cat = drill.get("category") if isinstance(drill, dict) else None
        if cat:
            personalization.record_offer(user_id, cat)
    except Exception:  # noqa: BLE001
        pass
