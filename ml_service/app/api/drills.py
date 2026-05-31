# 출처: 명세서 §7.1
"""GET /drills/{id} 드릴 instruction 상세 + GET /categories 6 카테고리."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException

from app.core.drill_catalog import get_drill, get_drills
from app.schemas.common import CATEGORY_CALENDAR_COLOR, CATEGORY_LABEL_KO


router = APIRouter()


@router.get("/drills/{drill_id}")
def get_drill_detail(drill_id: int) -> dict:   # v9.5: int
    drill = get_drill(drill_id)
    if not drill:
        raise HTTPException(status_code=404, detail={"code": "INVALID_INPUT", "message": f"drill not found: {drill_id}"})
    return {
        "id": drill.get("id"),
        "title": drill.get("title"),
        "category": drill.get("category"),
        "duration_min": drill.get("duration_min"),
        "instruction": drill.get("instruction"),
        "source_short": drill.get("source_short"),
        "source_primary": drill.get("source_primary"),
        "evidence_level": drill.get("evidence_level"),
        "contraindications": drill.get("contraindications", []),
    }


@router.get("/drills")
def list_drills(category: str | None = None) -> dict:
    drills = get_drills()
    if category:
        drills = [d for d in drills if d.get("category") == category]
    return {
        "total": len(drills),
        "drills": [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "category": d.get("category"),
                "duration_min": d.get("duration_min"),
                "source_short": d.get("source_short"),
            }
            for d in drills
        ],
    }


@router.get("/categories")
def list_categories() -> dict:
    """6 카테고리 카탈로그 — BE/FE가 정적 import 대신 호출.

    응답: key / label_ko / calendar_color / drill_count.
    drill_count는 drills_seed_v6_3.json에서 동적 집계 — 드릴 추가/삭제 시 자동 반영.
    """
    counts = Counter(d.get("category") for d in get_drills() if d.get("category"))
    items = [
        {
            "key": key,
            "label_ko": CATEGORY_LABEL_KO[key],
            "calendar_color": CATEGORY_CALENDAR_COLOR[key],
            "drill_count": counts.get(key, 0),
        }
        for key in CATEGORY_LABEL_KO
    ]
    return {"total": len(items), "categories": items}
