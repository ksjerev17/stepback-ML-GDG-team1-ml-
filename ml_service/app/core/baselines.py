# 출처: 명세서 §10.2, §11.1
"""baselines — 사용자 30일 누적 평균. 학습 전용, 사용자 비노출."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from app.config import REPO_ROOT
from app.infra.audit_log import hash_user_id
from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO


BASELINES_DB = REPO_ROOT / "ml_service" / "data" / "baselines.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS baselines (
  user_hash TEXT PRIMARY KEY,
  patterns_avg TEXT NOT NULL,
  behaviors_avg TEXT NOT NULL,
  emotions_avg TEXT NOT NULL,
  rejected_drills TEXT NOT NULL,
  sample_count INTEGER NOT NULL,
  window_days INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def _ensure(db_path: Path | None = None) -> Path:
    path = db_path or BASELINES_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def _connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = _ensure(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _avg_dim(entries: Iterable[dict[str, Any]], dim: str, keys: tuple[str, ...]) -> dict[str, float]:
    sums = {k: 0.0 for k in keys}
    n = 0
    for e in entries:
        lr = e.get("label_result", {}) or {}
        scores = lr.get(dim, {}) or {}
        n += 1
        for k in keys:
            sums[k] += float(scores.get(k, 0.0))
    if n == 0:
        return {k: 0.0 for k in keys}
    return {k: round(sums[k] / n, 3) for k in keys}


def recompute_baseline(
    *,
    user_id: str,
    entries: list[dict[str, Any]],
    rejected_drills: list[str] | None = None,
    window_days: int = 30,
    db_path: Path | None = None,
) -> dict:
    """entries는 BE가 30일치 보내줌. ML은 평균·rejected만 계산·저장."""
    now = datetime.now(timezone.utc).isoformat()
    user_hash = hash_user_id(user_id)
    patterns_avg = _avg_dim(entries, "patterns", PATTERNS_KO)
    behaviors_avg = _avg_dim(entries, "behaviors", BEHAVIORS_KO)
    emotions_avg = _avg_dim(entries, "emotions", EMOTIONS_KO)
    rejected = list(rejected_drills or [])

    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM baselines WHERE user_hash = ?", (user_hash,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """INSERT INTO baselines (user_hash, patterns_avg, behaviors_avg, emotions_avg, rejected_drills, sample_count, window_days, updated_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_hash) DO UPDATE SET
                 patterns_avg = excluded.patterns_avg,
                 behaviors_avg = excluded.behaviors_avg,
                 emotions_avg = excluded.emotions_avg,
                 rejected_drills = excluded.rejected_drills,
                 sample_count = excluded.sample_count,
                 window_days = excluded.window_days,
                 updated_at = excluded.updated_at""",
            (
                user_hash,
                json.dumps(patterns_avg, ensure_ascii=False),
                json.dumps(behaviors_avg, ensure_ascii=False),
                json.dumps(emotions_avg, ensure_ascii=False),
                json.dumps(rejected, ensure_ascii=False),
                len(entries),
                window_days,
                now,
                created_at,
            ),
        )
    return {
        "user_id": user_id,
        "patterns_avg": patterns_avg,
        "behaviors_avg": behaviors_avg,
        "emotions_avg": emotions_avg,
        "rejected_drills": rejected,
        "sample_count": len(entries),
        "window_days": window_days,
        "updated_at": now,
    }


def get_baseline(user_id: str, *, db_path: Path | None = None) -> dict | None:
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM baselines WHERE user_hash = ?", (user_hash,)).fetchone()
    if not row:
        return None
    return {
        "user_id": user_id,
        "patterns_avg": json.loads(row["patterns_avg"]),
        "behaviors_avg": json.loads(row["behaviors_avg"]),
        "emotions_avg": json.loads(row["emotions_avg"]),
        "rejected_drills": json.loads(row["rejected_drills"]),
        "sample_count": row["sample_count"],
        "window_days": row["window_days"],
        "updated_at": row["updated_at"],
    }


def compare_to_baseline(
    user_id: str,
    *,
    current_patterns_avg: dict[str, float],
    current_behaviors_avg: dict[str, float],
    db_path: Path | None = None,
) -> dict | None:
    """이번 주 패턴 평균 vs baseline 비교 — "평소보다 X 패턴 30% 높음" 카드 생성."""
    base = get_baseline(user_id, db_path=db_path)
    if not base:
        return None
    deltas: dict[str, float] = {}
    for k, v in current_patterns_avg.items():
        base_v = base["patterns_avg"].get(k, 0.0)
        deltas[k] = round(v - base_v, 3)
    for k, v in current_behaviors_avg.items():
        base_v = base["behaviors_avg"].get(k, 0.0)
        deltas[k] = round(v - base_v, 3)

    top_name, top_delta = max(deltas.items(), key=lambda kv: kv[1])
    top_increase = None
    if top_delta >= 0.10:  # 10%p 이상 차이
        pct = int(round(top_delta * 100))
        top_increase = {
            "name": top_name,
            "delta": top_delta,
            "card": f"평소보다 {top_name} 표현이 {pct}%p 더 보였어요",
        }
    return {
        "user_id": user_id,
        "week": "",
        "deltas": deltas,
        "top_increase": top_increase,
    }
