# 출처: CLAUDE.md §4.4, §11
"""SQLite 드릴 평가 저장. 점수는 사용자에게 비공개 — 학습 데이터로만."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date as DateT
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional


# v9.4.3 §4.4: 명세서가 "KST 23:59까지 수정 가능"이라 명시했으므로 KST 기준.
KST = timezone(timedelta(hours=9))


def _kst_today() -> DateT:
    """현재 KST 날짜 (UTC가 아님)."""
    return datetime.now(KST).date()


def _kst_end_of_day(d: DateT) -> datetime:
    """그 날 KST 23:59:59을 UTC로 변환."""
    return datetime.combine(d, time(23, 59, 59), tzinfo=KST).astimezone(timezone.utc)

from app.config import REPO_ROOT
from app.infra.audit_log import hash_user_id


DB_PATH = REPO_ROOT / "ml_service" / "data" / "feedback.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_hash TEXT NOT NULL,
  drill_id INTEGER NOT NULL,   -- v9.5: ERD INT 호환
  rating TEXT NOT NULL CHECK(rating IN ('helpful','meh','unhelpful')),
  recommended_at TEXT NOT NULL,
  rated_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  UNIQUE(user_hash, drill_id, recommended_at)
);
CREATE INDEX IF NOT EXISTS idx_feedback_user_day ON feedback(user_hash, recommended_at);
"""


def _ensure_db(db_path: Path | None = None) -> Path:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def _connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = _ensure_db(db_path)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_feedback(
    *,
    user_id: str,
    drill_id: int,   # v9.5: int
    rating: str,
    recommended_at: DateT,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    rated_at: Optional[datetime] = None,
    db_path: Path | None = None,
) -> dict:
    """평가 저장 — 당일 내 수정 가능, 다음날 거부."""
    # v9.4.3 §4.4: KST 23:59까지 수정 가능. UTC가 아님.
    today_kst = _kst_today()
    if recommended_at < today_kst:
        # KST 기준 24시간 지난 평가는 거부 (§4.4)
        raise PermissionError("rating window expired (next-day edit not allowed)")
    if rating not in ("helpful", "meh", "unhelpful"):
        raise ValueError(f"invalid rating: {rating}")
    rated_at = rated_at or datetime.now(timezone.utc)
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO feedback (user_hash, drill_id, rating, recommended_at, rated_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_hash, drill_id, recommended_at) DO UPDATE SET
              rating = excluded.rating,
              rated_at = excluded.rated_at,
              started_at = COALESCE(excluded.started_at, feedback.started_at),
              completed_at = COALESCE(excluded.completed_at, feedback.completed_at)
            """,
            (
                user_hash, drill_id, rating, recommended_at.isoformat(), rated_at.isoformat(),
                started_at.isoformat() if started_at else None,
                completed_at.isoformat() if completed_at else None,
            ),
        )
    return {"accepted": True, "can_edit_until": _kst_end_of_day(today_kst).isoformat()}


def _end_of_day(d: DateT) -> datetime:
    return datetime.combine(d, time(23, 59, 59), tzinfo=timezone.utc)


def user_summary(user_id: str, *, db_path: Path | None = None) -> dict:
    """GET /feedback — 응답에 점수 노출 X. 카운트·최근 시각만."""
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total, MAX(rated_at) AS last_rated_at FROM feedback WHERE user_hash = ?",
            (user_hash,),
        ).fetchone()
        return {
            "user_id": user_id,
            "total_count": int(row["total"] or 0),
            "last_rated_at": row["last_rated_at"],
        }


def purge_older_than(days: int = 90, *, db_path: Path | None = None) -> int:
    """90일 이상 지난 데이터 삭제 (§13.6, §16.3)."""
    cutoff = (datetime.now(timezone.utc) - _days(days)).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM feedback WHERE rated_at < ?", (cutoff,))
        return cur.rowcount


def _days(n: int):
    from datetime import timedelta
    return timedelta(days=n)
