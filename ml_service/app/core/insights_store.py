# 출처: 명세서 §8.4, §8.5, §11.1
"""SQLite 기반 user_insights + reports + rejected_drills 통합 저장.

스키마는 명세서 §11.1 그대로:
- insights(insight_id, user_id, text, source, category, week_of, report_id, created_at)
- reports(report_id, user_id, pattern_analysis JSONB, emotion_distribution JSONB, created_at, read_at)
- quiz_answers(answer_id, user_id, week, predicted, correct, gap, answered_at)
- rejected_drills(id, user_id, drill_id, rejected_at)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from app.config import REPO_ROOT
from app.infra.audit_log import hash_user_id


INSIGHTS_DB = REPO_ROOT / "ml_service" / "data" / "insights.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS insights (
  insight_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_hash TEXT NOT NULL,
  text TEXT NOT NULL,
  source TEXT NOT NULL CHECK(source IN ('system','user')),
  category TEXT NOT NULL CHECK(category IN ('cognitive','behavior','emotion','context','drill')),
  week_of TEXT NOT NULL,
  report_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insights_user_week ON insights(user_hash, week_of);

CREATE TABLE IF NOT EXISTS reports (
  report_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_hash TEXT NOT NULL,
  week_of TEXT NOT NULL,
  pattern_analysis TEXT NOT NULL,
  emotion_distribution TEXT NOT NULL,
  created_at TEXT NOT NULL,
  read_at TEXT,
  UNIQUE(user_hash, week_of)
);
CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_hash);

CREATE TABLE IF NOT EXISTS quiz_answers (
  answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_hash TEXT NOT NULL,
  week_of TEXT NOT NULL,
  predicted TEXT NOT NULL,
  correct TEXT NOT NULL,
  gap INTEGER NOT NULL,
  answered_at TEXT NOT NULL,
  UNIQUE(user_hash, week_of)
);

CREATE TABLE IF NOT EXISTS rejected_drills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_hash TEXT NOT NULL,
  drill_id INTEGER NOT NULL,   -- v9.5: ERD INT 호환
  rejected_at TEXT NOT NULL,
  UNIQUE(user_hash, drill_id)
);
CREATE INDEX IF NOT EXISTS idx_rejected_user ON rejected_drills(user_hash);
"""


def _ensure_db(db_path: Path | None = None) -> Path:
    path = db_path or INSIGHTS_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def _connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = _ensure_db(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# insights
# ============================================================================

def add_insight(
    *,
    user_id: str,
    text: str,
    source: str,
    category: str,
    week_of: str,
    report_id: Optional[int] = None,
    db_path: Path | None = None,
) -> dict:
    user_hash = hash_user_id(user_id)
    created = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO insights (user_hash, text, source, category, week_of, report_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_hash, text, source, category, week_of, report_id, created),
        )
        return {
            "insight_id": cur.lastrowid,
            "user_id": user_id,
            "text": text,
            "source": source,
            "category": category,
            "week_of": week_of,
            "report_id": report_id,
            "created_at": created,
        }


def list_insights(
    *,
    user_id: str,
    category: Optional[str] = None,
    source: Optional[str] = None,
    week_of: Optional[str] = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict]:
    user_hash = hash_user_id(user_id)
    query = "SELECT * FROM insights WHERE user_hash = ?"
    params: list[Any] = [user_hash]
    if category:
        query += " AND category = ?"
        params.append(category)
    if source:
        query += " AND source = ?"
        params.append(source)
    if week_of:
        query += " AND week_of = ?"
        params.append(week_of)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "insight_id": r["insight_id"],
            "user_id": user_id,
            "text": r["text"],
            "source": r["source"],
            "category": r["category"],
            "week_of": r["week_of"],
            "report_id": r["report_id"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ============================================================================
# reports
# ============================================================================

def upsert_report(
    *,
    user_id: str,
    week_of: str,
    pattern_analysis: dict,
    emotion_distribution: dict,
    db_path: Path | None = None,
) -> dict:
    user_hash = hash_user_id(user_id)
    created = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO reports (user_hash, week_of, pattern_analysis, emotion_distribution, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_hash, week_of) DO UPDATE SET
                 pattern_analysis = excluded.pattern_analysis,
                 emotion_distribution = excluded.emotion_distribution""",
            (
                user_hash,
                week_of,
                json.dumps(pattern_analysis, ensure_ascii=False),
                json.dumps(emotion_distribution, ensure_ascii=False),
                created,
            ),
        )
        row = conn.execute(
            "SELECT report_id, read_at FROM reports WHERE user_hash = ? AND week_of = ?",
            (user_hash, week_of),
        ).fetchone()
    return {
        "report_id": row["report_id"],
        "user_id": user_id,
        "week_of": week_of,
        "status": "read" if row["read_at"] else "pending",
        "created_at": created,
    }


def pending_reports(user_id: str, *, db_path: Path | None = None) -> list[dict]:
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE user_hash = ? AND read_at IS NULL ORDER BY created_at DESC",
            (user_hash,),
        ).fetchall()
    return [
        {
            "report_id": r["report_id"],
            "user_id": user_id,
            "week_of": r["week_of"],
            "status": "pending",
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def mark_report_read(*, user_id: str, report_id: int, db_path: Path | None = None) -> bool:
    user_hash = hash_user_id(user_id)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE reports SET read_at = ? WHERE report_id = ? AND user_hash = ? AND read_at IS NULL",
            (now, report_id, user_hash),
        )
        return cur.rowcount > 0


# ============================================================================
# quiz answers (메타인지 격차)
# ============================================================================

def save_quiz_answer(
    *,
    user_id: str,
    week_of: str,
    predicted: str,
    correct: str,
    actual_ratio_percent: float,
    db_path: Path | None = None,
) -> dict:
    """예측 vs 실제 비교. gap = 패턴 비율의 차이(절댓값)."""
    user_hash = hash_user_id(user_id)
    now = datetime.now(timezone.utc).isoformat()
    gap = 0 if predicted == correct else 100
    if predicted == "모르겠다":
        gap = -1  # 모름 신호
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO quiz_answers (user_hash, week_of, predicted, correct, gap, answered_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_hash, week_of) DO UPDATE SET
                 predicted = excluded.predicted,
                 correct = excluded.correct,
                 gap = excluded.gap,
                 answered_at = excluded.answered_at""",
            (user_hash, week_of, predicted, correct, gap, now),
        )
    return {
        "user_id": user_id,
        "week_of": week_of,
        "predicted": predicted,
        "correct": correct,
        "match": predicted == correct,
        "is_dont_know": predicted == "모르겠다",
        "actual_ratio_percent": actual_ratio_percent,
    }


# ============================================================================
# rejected drills
# ============================================================================

def reject_drill(*, user_id: str, drill_id: int, db_path: Path | None = None) -> dict:
    user_hash = hash_user_id(user_id)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO rejected_drills (user_hash, drill_id, rejected_at) VALUES (?, ?, ?)",
            (user_hash, drill_id, now),
        )
    return {"user_id": user_id, "drill_id": drill_id, "rejected_at": now}


def rejected_drill_ids(user_id: str, *, db_path: Path | None = None) -> list[int]:
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT drill_id FROM rejected_drills WHERE user_hash = ? ORDER BY rejected_at DESC",
            (user_hash,),
        ).fetchall()
    return [r["drill_id"] for r in rows]


# ============================================================================
# v9.5: "나의 발견" — 사용자 직접 입력 인사이트 저장 + 다음 추천 시 참조.
# ============================================================================

def save_user_discoveries(
    *,
    user_id: str,
    week_of: str,
    discoveries: list[str],
    db_path: Path | None = None,
) -> dict:
    """주간 리포트 화면 \"나의 발견\"에서 사용자가 입력한 문장들을 저장.

    Args:
        user_id: 사용자 ID (해시 처리됨)
        week_of: \"2026-W21\" 형식 — 어느 주의 리포트에서 입력했는지
        discoveries: 사용자가 적은 발견 문장 리스트 (1~5개)

    저장 위치: insights 테이블, source='user', category='context'.

    Returns: {saved_count, user_id, week_of}
    """
    user_hash = hash_user_id(user_id)
    now = datetime.now(timezone.utc).isoformat()
    cleaned = [d.strip() for d in discoveries if d and d.strip()]
    # 길이 제한 (1자 ~ 200자 사이)
    cleaned = [d for d in cleaned if 1 <= len(d) <= 200][:5]

    if not cleaned:
        return {"saved_count": 0, "user_id": user_id, "week_of": week_of}

    with _connect(db_path) as conn:
        for text in cleaned:
            conn.execute(
                """INSERT INTO insights
                   (user_hash, text, source, category, week_of, report_id, created_at)
                   VALUES (?, ?, 'user', 'context', ?, NULL, ?)""",
                (user_hash, text, week_of, now),
            )
    return {"saved_count": len(cleaned), "user_id": user_id, "week_of": week_of}


def get_recent_user_discoveries(
    user_id: str,
    *,
    limit: int = 5,
    db_path: Path | None = None,
) -> list[str]:
    """최근 \"나의 발견\" 텍스트 N개 (다음 추천 시 맥락 참조용).

    추천기에서 affinity 점수 가산이나 카피 톤 조정에 활용 가능.
    """
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT text FROM insights
               WHERE user_hash = ? AND source = 'user'
               ORDER BY created_at DESC LIMIT ?""",
            (user_hash, int(limit)),
        ).fetchall()
    return [r["text"] for r in rows]
