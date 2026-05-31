# 출처: CLAUDE.md §4 (action_tracking), §11
"""행동 실천율 계산 — 비공개 학습 데이터."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.feedback_store import DB_PATH, _connect
from app.infra.audit_log import hash_user_id


def practice_rate(user_id: str, *, since_days: int = 7, db_path: Optional[Path] = None) -> dict:
    """최근 N일 추천된 드릴 중 completed 비율."""
    user_hash = hash_user_id(user_id)
    cutoff_iso = (datetime.now(timezone.utc) - _days(since_days)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT rating, started_at, completed_at
            FROM feedback
            WHERE user_hash = ? AND rated_at >= ?
            """,
            (user_hash, cutoff_iso),
        ).fetchall()
    total = len(rows)
    practiced = sum(1 for r in rows if r["completed_at"])
    started = sum(1 for r in rows if r["started_at"])
    return {
        "total_count": total,
        "started_count": started,
        "practiced_count": practiced,
        "practice_rate": (practiced / total) if total else 0.0,
        "start_rate": (started / total) if total else 0.0,
    }


def _days(n: int):
    from datetime import timedelta
    return timedelta(days=n)
