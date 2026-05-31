# 출처: v9.5 + P2 BE 명세 통합.
"""POST /entries — BE 호환 통합 라우트 (옵션 C).

BE가 한 번 호출로 label + recommend 받음. ML 두 번 왕복 제거.

흐름:
1. text + context 받음
2. context 매핑 (BE 형식 ↔ ML 형식 자동 변환)
3. label_text() → 라벨 결과
4. recommend() → 드릴 추천 (user_discoveries 자동 반영)
5. BE가 기대하는 응답 구조로 통합 반환
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field, field_validator

from app.core.labeler import label_text
from app.core.recommender import recommend
from app.core import personalization
from app.schemas.common import CATEGORY_LABEL_KO, CATEGORY_CALENDAR_COLOR, SocialToday


router = APIRouter()


# ============================================================================
# 요청 모델 — BE 명세서·ML 명세서 둘 다 호환
# ============================================================================

class EntriesContext(BaseModel):
    """v9.5: BE/ML 두 형식 모두 받기.

    BE 명세 (의논 전 임시): {"sleep": 6, "exercise": true, "condition": "bad", "meals": 2}
    ML 명세: {"sleep_hours": 6.0, "exercise_today": 0.0, "self_condition": 2, "social_today": "보통"}

    둘 다 Optional. 한쪽만 와도 OK.
    """
    # ML 표준 필드
    self_condition: Optional[int] = Field(None, ge=1, le=5)
    sleep_hours: Optional[float] = Field(None, ge=0.0, le=24.0)
    social_today: Optional[str] = None
    exercise_today: Optional[float] = Field(None, ge=0.0, le=12.0)
    # BE 명세 별칭 (자동 매핑)
    sleep: Optional[float] = Field(None, ge=0.0, le=24.0)
    exercise: Optional[bool] = None
    condition: Optional[str] = None      # "good" / "bad" / 한국어
    meals: Optional[int] = Field(None, ge=0, le=10)   # 무시 (ML 사용 X)


class EntriesRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)   # v9.5: LabelRequest와 통일
    user_id: str = Field(..., min_length=1, max_length=64)
    context: Optional[EntriesContext] = None
    recent_drill_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("text")
    @classmethod
    def _validate_meaningful_text(cls, v: str) -> str:
        """LabelRequest와 동일 — 공백만·이모지만·반복문자만 거절."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must contain non-whitespace characters")
        import re
        if not re.search(r"[\w가-힣]", stripped):
            raise ValueError("text must contain at least one letter, digit, or Korean character")
        if len(stripped) >= 3 and len(set(stripped.replace(" ", ""))) == 1:
            raise ValueError("text must not be a single repeated character")
        return v


# ============================================================================
# 응답 모델 — v9.5 명시
# ============================================================================

class EntriesResponse(BaseModel):
    """POST /entries 통합 응답.

    BE는 이 응답을 entries 테이블에 그대로 저장.
    """
    text: str
    context_used: dict           # 정규화 후 ML이 실제 사용한 context (BE 캐시·기본값 흔적)
    label_result: dict           # /label 결과 — patterns/behaviors/emotions/intensity/confidence/...
    recommendation: dict         # /recommend 결과 — 5 type 중 하나
    drill_category: Optional[str] = None        # cognitive_restructuring 등 — drill 응답일 때만
    drill_category_label: Optional[str] = None  # "생각 전환" 한국어 라벨
    drill_calendar_color: Optional[str] = None  # "pink_soft" 등 캘린더 색 키 (FE 매핑용)
    labeled_at: str              # ISO datetime


# ============================================================================
# context 매핑 — BE 형식 → ML 형식 (역방향 안전)
# ============================================================================

def _normalize_context(ctx: EntriesContext | None) -> dict[str, Any]:
    """BE 형식·ML 형식 모두 받아서 ML 표준 dict 반환."""
    if ctx is None:
        return {
            "self_condition": 3,
            "sleep_hours": 7.0,
            "social_today": SocialToday.NORMAL.value,
            "exercise_today": 0.0,
        }

    # self_condition
    sc = ctx.self_condition
    if sc is None and ctx.condition:
        # "good"=4, "bad"=2, 기타=3
        c = ctx.condition.lower()
        if c in ("good", "좋음", "좋아"):
            sc = 4
        elif c in ("bad", "나쁨", "안좋음"):
            sc = 2
        else:
            sc = 3
    sc = sc if sc is not None else 3

    # sleep_hours
    sh = ctx.sleep_hours if ctx.sleep_hours is not None else (
        float(ctx.sleep) if ctx.sleep is not None else 7.0
    )

    # exercise_today
    ex = ctx.exercise_today
    if ex is None:
        if ctx.exercise is True:
            ex = 0.5  # bool true → 30분 추정
        elif ctx.exercise is False:
            ex = 0.0
        else:
            ex = 0.0

    # social_today (BE 명세에 없음 — 기본 "보통")
    social = ctx.social_today or SocialToday.NORMAL.value

    return {
        "self_condition": int(sc),
        "sleep_hours": float(sh),
        "social_today": social,
        "exercise_today": float(ex),
    }


# ============================================================================
# POST /entries
# ============================================================================

@router.post("/entries", response_model=EntriesResponse)
def post_entries(req: EntriesRequest) -> EntriesResponse:
    """v9.5: BE 통합 엔드포인트.

    한 번 호출 = label + recommend 통합. BE는 이 응답을 entries 테이블에 저장.

    응답 구조:
    {
        "text": "...",
        "context_used": {...},          // 정규화 후 ML이 실제 사용한 context
        "label_result": {...},          // 라벨링 결과 (patterns/behaviors/emotions)
        "recommendation": {...},        // 드릴 추천 결과 (5타입 중 하나)
        "drill_category": "grounding",  // FE 캘린더 색 매핑용 (none 가능)
        "drill_category_label": "마음 챙김",
        "drill_calendar_color": "green_calm",
        "labeled_at": "2026-..."
    }
    """
    ctx_dict = _normalize_context(req.context)

    # 1) 라벨링
    label = label_text(text=req.text, user_id=req.user_id)

    # 2) 추천 (user_discoveries 자동 반영됨 — recommend 내부에서 조회) + v9.6 개인화 가산점
    pref_bonus = personalization.bonus_map(req.user_id)
    rec = recommend(
        label_result=label,
        context=ctx_dict,
        user_id=req.user_id,
        recent_drill_ids=req.recent_drill_ids,
        pref_bonus=pref_bonus,
    )

    # 3) drill_category 추출 (캘린더 색 매핑용)
    drill_category = None
    drill_label = None
    drill_color = None
    drill_obj = rec.get("drill") if isinstance(rec, dict) else None
    if drill_obj and isinstance(drill_obj, dict):
        drill_category = drill_obj.get("category")
        if drill_category:
            drill_label = CATEGORY_LABEL_KO.get(drill_category)
            drill_color = CATEGORY_CALENDAR_COLOR.get(drill_category)
            # v9.6: 개인화 학습 — 이 카테고리가 추천(노출)되었음을 기록.
            try:
                personalization.record_offer(req.user_id, drill_category)
            except Exception:  # noqa: BLE001 (best-effort — 추천을 막지 않음)
                pass

    return EntriesResponse(
        text=req.text,
        context_used=ctx_dict,
        label_result=label,
        recommendation=rec,
        drill_category=drill_category,
        drill_category_label=drill_label,
        drill_calendar_color=drill_color,
        labeled_at=datetime.now(timezone.utc).isoformat(),
    )
