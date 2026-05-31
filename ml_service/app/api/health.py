# 출처: CLAUDE.md §9.1
"""GET /healthz."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.drill_catalog import total_drills
from app.infra.llm_client import get_llm_client


router = APIRouter()


def _check_db() -> bool:
    """SQLite feedback DB 접근 가능한지."""
    try:
        from app.core.feedback_store import _ensure_db
        _ensure_db()
        return True
    except Exception:
        return False


def _check_w1_data() -> bool:
    """w1 분류·카탈로그 로드 가능한지."""
    try:
        from app.config import W1_DIR
        return (
            (W1_DIR / "taxonomy_v7.json").exists()
            and ((W1_DIR / "drills_seed_v6_4.json").exists() or (W1_DIR / "drills_seed_v6_3.json").exists())
        )
    except Exception:
        return False


@router.get("/healthz")
def healthz() -> dict:
    """v9.4.3: DB ping + w1 데이터 + Mock 명시."""
    llm = get_llm_client()
    db_ok = _check_db()
    w1_ok = _check_w1_data()
    drills_ok = total_drills() > 0
    status = "ok" if (drills_ok and db_ok and w1_ok) else "degraded"
    return {
        "status": status,
        "version": "v7",
        "catalog_version": "v" + str(__import__("app.core.drill_catalog", fromlist=["load_catalog"]).load_catalog().get("schema_version", "?")),
        "spec_version": "v9.4.3",
        "primary_model": llm.primary_model,
        "drills_loaded": total_drills(),
        "db_accessible": db_ok,
        "w1_data_loaded": w1_ok,
        "ml_available": True,
        "is_mock": llm.is_mock,
        "mock_notice": (
            "Mock LLM 사용 중 — 실제 Gemini API 호출 없이 키워드 매칭으로 라벨링."
            if llm.is_mock else None
        ),
    }
