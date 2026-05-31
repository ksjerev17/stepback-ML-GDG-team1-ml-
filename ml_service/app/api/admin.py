# 출처: 운영 보강 — 시연·디버깅용 비상 엔드포인트
"""GET /healthz/detail, GET /metrics, POST /admin/quota/reset, POST /clarify."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.core.drill_catalog import load_catalog, total_drills
from app.infra.llm_client import get_llm_client
from app.infra.metrics import get_metrics
from app.infra.quota_manager import get_quota_manager


router = APIRouter()


def _check_admin_token(token: str | None) -> None:
    """v9.4.3 보안: ADMIN_TOKEN 강제. 미설정 시 503 (admin 비활성).

    이전: 기본값 "dev-admin-token"으로 누구나 호출 가능 (보안 구멍).
    """
    expected = os.environ.get("ADMIN_TOKEN", "").strip()
    if not expected:
        # 환경변수 미설정 → admin 엔드포인트 비활성화
        raise HTTPException(
            status_code=503,
            detail={"code": "INTERNAL_ERROR",
                    "message": "admin endpoints disabled — set ADMIN_TOKEN env"},
        )
    if not token or token != expected:
        raise HTTPException(
            status_code=403,
            detail={"code": "INVALID_INPUT", "message": "admin token required"},
        )


@router.get("/healthz/detail")
def healthz_detail(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> dict:
    """v9.4.3 보안: ADMIN_TOKEN 필요. tracked_users·env 정보 누출 차단."""
    _check_admin_token(x_admin_token)
    llm = get_llm_client()
    qm = get_quota_manager()
    return {
        "status": "ok" if total_drills() > 0 else "degraded",
        "now": datetime.now(timezone.utc).isoformat(),
        "drills_loaded": total_drills(),
        "catalog_version": "v" + str(load_catalog().get("schema_version", "?")),
        "taxonomy_version": "v7",
        "spec_version": "v9.4.3",
        "primary_model": llm.primary_model,
        "is_mock": llm.is_mock,
        "sdk_kind": getattr(llm, "sdk_kind", "unknown"),
        "force_mock_env": os.environ.get("FORCE_MOCK", ""),
        "tracked_users": len(qm._calls) if hasattr(qm, "_calls") else 0,
        "endpoints_count": 24,
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_text(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> str:
    """Prometheus 호환 텍스트. v9.4.3: ADMIN_TOKEN 필요 (운영 정보 보호)."""
    _check_admin_token(x_admin_token)
    return "\n".join(get_metrics().render()) + "\n"


@router.get("/metrics/json")
def metrics_json(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> dict:
    _check_admin_token(x_admin_token)
    return get_metrics().snapshot()


@router.post("/admin/quota/reset")
def admin_quota_reset(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> dict:
    _check_admin_token(x_admin_token)
    get_quota_manager().reset(user_id)
    return {"user_id": user_id, "status": "reset"}


@router.post("/clarify")
def post_clarify(
    text: Annotated[str, Body(min_length=1, max_length=200)],
    candidate_a: Annotated[str, Body()],
    candidate_b: Annotated[str, Body()],
) -> dict:
    """경계선(0.3~0.5) 정밀화 — LLM에 두 후보 중 강한 신호를 묻기.

    Mock 환경에서는 'tie' 반환. 실 LLM 후에는 clarification_loop의 build_prompt 활용.
    """
    llm = get_llm_client()
    if llm.is_mock:
        return {"choice": "tie", "model_used": "mock"}
    prompt = (
        f'주어진 한국어 문장: "{text}"\n'
        f"A) {candidate_a}\nB) {candidate_b}\nC) 둘 다 비슷함\n"
        f"규칙: 반드시 A/B/C 중 하나만 출력."
    )
    raw = llm.clarify(prompt)
    raw_clean = (raw or "").strip().upper()
    choice = next((c for c in raw_clean if c in "ABC"), None)
    if choice == "A":
        return {"choice": candidate_a, "model_used": llm.light_model}
    if choice == "B":
        return {"choice": candidate_b, "model_used": llm.light_model}
    return {"choice": "tie", "model_used": llm.light_model}
