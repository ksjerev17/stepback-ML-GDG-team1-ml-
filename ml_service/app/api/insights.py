# 출처: 명세서 §8.4, §8.5
"""POST /insights, GET /insights, POST /reject, /export, /delete."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Query

from app.core import feedback_store, insights_store
from app.schemas.insight import (
    InsightCategory,
    InsightCreate,
    InsightItem,
    InsightList,
    InsightSource,
)


router = APIRouter()


@router.post("/insights", response_model=InsightItem)
def post_insight(req: InsightCreate) -> InsightItem:
    raw = insights_store.add_insight(
        user_id=req.user_id,
        text=req.text,
        source=InsightSource.USER.value,
        category=req.category.value,
        week_of=req.week_of,
        report_id=req.report_id,
    )
    return InsightItem.model_validate(raw)


@router.get("/insights", response_model=InsightList)
def get_insights(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    category: Optional[InsightCategory] = None,
    source: Optional[InsightSource] = None,
    week_of: Optional[str] = None,
    limit: int = 50,
) -> InsightList:
    items = insights_store.list_insights(
        user_id=user_id,
        category=category.value if category else None,
        source=source.value if source else None,
        week_of=week_of,
        limit=limit,
    )
    return InsightList(user_id=user_id, items=[InsightItem.model_validate(i) for i in items])


@router.post("/insights/user_discovery")
def post_user_discovery(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    week_of: Annotated[str, Body(pattern=r"^\d{4}-W\d{2}$")],
    discoveries: Annotated[list[str], Body(min_length=1, max_length=5)],
) -> dict:
    """v9.5: \"나의 발견\" 입력 — 사용자가 주간 리포트에서 직접 적은 발견 저장.

    저장 위치: insights 테이블 (source='user', category='context').
    다음 추천 시 GET /insights/user_discovery로 조회해 추천 맥락에 반영.
    """
    return insights_store.save_user_discoveries(
        user_id=user_id,
        week_of=week_of,
        discoveries=discoveries,
    )


@router.get("/insights/user_discovery")
def get_user_discoveries(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> dict:
    """v9.5: 최근 \"나의 발견\" 조회 — 추천기가 맥락 참조용."""
    items = insights_store.get_recent_user_discoveries(user_id, limit=limit)
    return {"user_id": user_id, "discoveries": items, "count": len(items)}


@router.post("/reject")
def post_reject_drill(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    drill_id: Annotated[int, Body(ge=1, le=9999)],   # v9.5: int
) -> dict:
    """드릴 카드의 '아닌 것 같아요' 버튼 — 학습 신호로 누적."""
    result = insights_store.reject_drill(user_id=user_id, drill_id=drill_id)
    # v9.6: 개인화 학습 — 거부된 드릴 카테고리에 약한 음의 신호 반영.
    try:
        from app.core import drill_catalog, personalization
        drill = drill_catalog.get_drill(drill_id)
        cat = drill.get("category") if drill else None
        if cat:
            personalization.record_reject(user_id, cat)
    except Exception:  # noqa: BLE001 (best-effort)
        pass
    return result


@router.get("/export")
def export_user_data(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict:
    """사용자 본인 데이터 JSON export (§11.3)."""
    feedback = feedback_store.user_summary(user_id)
    insight_items = insights_store.list_insights(user_id=user_id, limit=10000)
    rejected = insights_store.rejected_drill_ids(user_id)
    return {
        "user_id": user_id,
        "feedback_summary": feedback,
        "insights": insight_items,
        "rejected_drills": rejected,
        "export_format": "json",
        "note": "ML 측 보관 데이터만 포함. 입력 텍스트는 BE DB에서 별도 export 필요.",
    }


@router.delete("/users/{user_id}/data")
def delete_user_data(user_id: str) -> dict:
    """회원 탈퇴 시 ML 측 데이터 일괄 삭제 (§16.3)."""
    import sqlite3

    from app.config import REPO_ROOT
    from app.core.feedback_store import DB_PATH as FEEDBACK_DB
    from app.core.insights_store import INSIGHTS_DB
    from app.core.baselines import BASELINES_DB
    from app.infra.audit_log import hash_user_id

    user_hash = hash_user_id(user_id)
    deleted = {"feedback": 0, "insights": 0, "reports": 0, "rejected_drills": 0, "quiz_answers": 0, "baselines": 0}

    for db, tables in [
        (FEEDBACK_DB, [("feedback", "user_hash")]),
        (INSIGHTS_DB, [
            ("insights", "user_hash"),
            ("reports", "user_hash"),
            ("rejected_drills", "user_hash"),
            ("quiz_answers", "user_hash"),
        ]),
        (BASELINES_DB, [("baselines", "user_hash")]),
    ]:
        if not db.exists():
            continue
        with sqlite3.connect(db) as conn:
            for table, col in tables:
                try:
                    cur = conn.execute(f"DELETE FROM {table} WHERE {col} = ?", (user_hash,))
                    deleted[table] = deleted.get(table, 0) + cur.rowcount
                except sqlite3.OperationalError:
                    pass
            conn.commit()
    return {
        "user_id": user_id,
        "deleted": deleted,
        "note": "BE DB의 users / entries 삭제는 별도 처리 필요 (P2 영역).",
    }
