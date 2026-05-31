# 출처: CLAUDE.md §11.5
"""감사 로그 — JSONL hash 로깅. 평문 텍스트 절대 금지."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import LOGS_DIR, get_settings


FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "text", "input_text", "user_text", "raw_text",
    "evidence_span", "prompt", "llm_request", "raw_response",
})

_log = logging.getLogger("audit")


def hash_user_id(user_id: str) -> str:
    salt = get_settings().audit_salt
    h = hashlib.sha256(f"salt:{salt}:{user_id}".encode("utf-8")).hexdigest()
    return f"sha256:{h[:16]}"


def _validate(payload: dict[str, Any]) -> None:
    found = FORBIDDEN_FIELDS & set(payload.keys())
    if found:
        raise ValueError(f"audit_log reject: forbidden plain fields {found}")
    if "user_id" in payload and not str(payload["user_id"]).startswith("sha256:"):
        raise ValueError("audit_log reject: user_id must be hashed (use hash_user_id)")


def write(
    *,
    endpoint: str,
    user_hash: str,
    text_len: int,
    extra: dict[str, Any] | None = None,
) -> None:
    """한 줄 감사 기록. 실패 시 stderr 경고만, 본 호출 흐름 영향 X."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "user_hash": user_hash,
        "text_len": int(text_len),
    }
    if extra:
        payload.update(extra)

    try:
        _validate(payload)
    except ValueError as e:
        _log.error("audit_log: %s", e)
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = LOGS_DIR / f"audit-{day}.jsonl"
    try:
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError as e:
        _log.error("audit_log write fail: %s", e)


def summarize_label(result: dict[str, Any]) -> dict[str, Any]:
    """라벨 결과 요약 — 평문 evidence_span 제외.

    v9.4.3: top_pattern/top_behavior 점수가 < 0.3 (약신호)면 null로 반환.
    카드 UI에서 잘못 안내되는 것 방지.
    """
    patterns = result.get("patterns", {}) or {}
    behaviors = result.get("behaviors", {}) or {}
    top_p = max(patterns.items(), key=lambda kv: kv[1], default=(None, 0.0))
    top_b = max(behaviors.items(), key=lambda kv: kv[1], default=(None, 0.0))
    return {
        "top_pattern": top_p[0] if top_p[1] >= 0.3 else None,
        "top_pattern_score": round(float(top_p[1]), 2),
        "top_behavior": top_b[0] if top_b[1] >= 0.3 else None,
        "top_behavior_score": round(float(top_b[1]), 2),
        "confidence": round(float(result.get("confidence", 0.0)), 2),
        "crisis": bool(result.get("crisis_detected", False)),
        "model": result.get("_model_used") or result.get("model_used", "unknown"),
    }
