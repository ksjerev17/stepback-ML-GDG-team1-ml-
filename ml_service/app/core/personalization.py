# 출처: 명세서 §11 (Contextual Bandit 계획) → v9.6에서 구현 완료.
"""개인화 엔진 — 사용자별 카테고리 선호 프로파일 (UCB1 스타일 적응 학습).

§11의 "향후 ML 계획 — Contextual Bandit"을 실제 구현한 모듈.
이전엔 가중합 ranking의 가중치(0.3/0.25/0.15)가 손으로 정한 magic number였고
개인화가 약했다. 이 모듈은 사용자의 *선택*(드릴 완료/도움됨/거부)을 누적해
카테고리별 보상(reward)을 추정하고, 다음 추천에 가산점으로 반영한다.

핵심 아이디어 (UCB1 — Auer 1985):
    score(cat) = mean_reward(cat) + c · sqrt(2·ln(N) / n(cat))
                 └ 활용(exploitation) ┘  └ 탐험(exploration) ┘

    - mean_reward: 그 카테고리 드릴이 실제로 도움이 된 비율 (적응)
    - exploration: 아직 덜 시도한 카테고리에 기회를 주는 항 (편향 방지)

이 점수를 그대로 쓰지 않고 작은 λ(기본 0.2)를 곱해 *가산점*으로만 쓴다.
임상 라우팅(위기/인지/행동)은 그대로 우선 — 개인화는 "같은 카테고리 안 또는
약신호 구간에서 어떤 드릴·방향을 고를지"를 부드럽게 조정하는 역할.

보상 정의 (§11.3 보상 설계):
    helpful=True            → 1.0   (도움됨)
    완료했지만 helpful 아님   → 0.5   (시도함)
    추천만 받고 미완료        → 0.0   (무반응)
    거부(reject)            → 별도 패널티 카운트 (recommender의 -2.0와 별개로 약하게)

저장: ml_service/data/preferences.db (baselines.db·insights.db와 동일 패턴).
사용자 ID는 SHA-256+salt 해시로만 보관 (§13.1 평문 0%).
"""
from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.config import REPO_ROOT
from app.infra.audit_log import hash_user_id
from app.schemas.common import CATEGORY_LABEL_KO, CategoryEn

PREFERENCES_DB = REPO_ROOT / "ml_service" / "data" / "preferences.db"

# 기본 카테고리 6종 (드릴 카테고리와 동일)
ALL_CATEGORIES: tuple[str, ...] = tuple(c.value for c in CategoryEn)

# UCB 탐험 계수 c — 작게 두어 임상 라우팅을 뒤집지 않음.
UCB_C: float = 0.6
# 추천기에 반영될 때 곱하는 λ — 가산점 크기 상한 제어.
DEFAULT_LAMBDA: float = 0.2
# 한 카테고리 가산점 절대 상한 (clamp) — 라우팅 우선순위 보호.
BONUS_CAP: float = 0.35

# Beta prior — 데이터 적을 때 과신 방지 (Laplace smoothing).
_PRIOR_REWARD = 1.0
_PRIOR_COUNT = 2.0

# v9.6 강화: 할인 UCB (discounted UCB) — 최근 선택에 더 큰 가중.
# 기록을 영구 누적하면 옛 취향이 새 취향을 덮어버린다. 갱신 때마다
# 0.5**(경과일/HALF_LIFE)로 기존 통계를 감쇠 → 지수 가중 이동평균(Sutton & Barto 2.5).
# 약 3주(21일) 반감기 → 최근 한 달의 선택이 사실상 추천을 좌우.
HALF_LIFE_DAYS: float = 21.0
# 감쇠 후 통계가 사실상 0이 되면 잡음이 커지므로 바닥값.
_DECAY_FLOOR: float = 1e-6


SCHEMA = """
CREATE TABLE IF NOT EXISTS category_stats (
  user_hash   TEXT NOT NULL,
  category    TEXT NOT NULL,
  n_offered   INTEGER NOT NULL DEFAULT 0,
  n_completed INTEGER NOT NULL DEFAULT 0,
  n_helpful   INTEGER NOT NULL DEFAULT 0,
  n_rejected  INTEGER NOT NULL DEFAULT 0,
  reward_sum  REAL    NOT NULL DEFAULT 0.0,
  updated_at  TEXT    NOT NULL,
  PRIMARY KEY (user_hash, category)
);
CREATE INDEX IF NOT EXISTS idx_prefs_user ON category_stats(user_hash);
"""


def _ensure(db_path: Path | None = None) -> Path:
    path = db_path or PREFERENCES_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return path


@contextmanager
def _connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = _ensure(db_path)
    conn = sqlite3.connect(path, timeout=5.0)
    # v9.6: 동시 쓰기 충돌 시 5초까지 대기 (멀티 워커 안전성).
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row(conn: sqlite3.Connection, user_hash: str, category: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM category_stats WHERE user_hash = ? AND category = ?",
        (user_hash, category),
    ).fetchone()


def _decay_factor(prev_iso: str | None, now: datetime) -> float:
    """이전 갱신 이후 경과 시간에 따른 감쇠 계수 (0,1]."""
    if not prev_iso:
        return 1.0
    try:
        prev = datetime.fromisoformat(prev_iso)
    except (TypeError, ValueError):
        return 1.0
    if prev.tzinfo is None:
        prev = prev.replace(tzinfo=UTC)
    elapsed_days = max(0.0, (now - prev).total_seconds() / 86400.0)
    return 0.5 ** (elapsed_days / HALF_LIFE_DAYS)


def _upsert(
    conn: sqlite3.Connection,
    user_hash: str,
    category: str,
    *,
    d_offered: float = 0.0,
    d_completed: float = 0.0,
    d_helpful: float = 0.0,
    d_rejected: float = 0.0,
    d_reward: float = 0.0,
) -> None:
    """할인 UCB: 기존 통계를 시간 감쇠 후 새 이벤트를 더한다 (read-modify-write).

    감쇠로 인해 카운트는 실수(effective count)가 된다 — UCB·보상 추정엔 더 정확.
    멀티 워커 동시성은 last-write-wins (busy_timeout로 잠금 충돌 완화).
    """
    now = datetime.now(UTC)
    row = conn.execute(
        "SELECT n_offered, n_completed, n_helpful, n_rejected, reward_sum, updated_at "
        "FROM category_stats WHERE user_hash = ? AND category = ?",
        (user_hash, category),
    ).fetchone()
    if row is None:
        n_off = n_comp = n_help = n_rej = r_sum = 0.0
    else:
        decay = _decay_factor(row["updated_at"], now)
        n_off = float(row["n_offered"]) * decay
        n_comp = float(row["n_completed"]) * decay
        n_help = float(row["n_helpful"]) * decay
        n_rej = float(row["n_rejected"]) * decay
        r_sum = float(row["reward_sum"]) * decay
        # 감쇠 후 사실상 0이면 0으로 정리 (잡음 방지)
        if n_off < _DECAY_FLOOR:
            n_off = n_comp = n_help = n_rej = r_sum = 0.0
    n_off += d_offered
    n_comp += d_completed
    n_help += d_helpful
    n_rej += d_rejected
    r_sum += d_reward
    conn.execute(
        """
        INSERT INTO category_stats
            (user_hash, category, n_offered, n_completed, n_helpful, n_rejected, reward_sum, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_hash, category) DO UPDATE SET
            n_offered   = excluded.n_offered,
            n_completed = excluded.n_completed,
            n_helpful   = excluded.n_helpful,
            n_rejected  = excluded.n_rejected,
            reward_sum  = excluded.reward_sum,
            updated_at  = excluded.updated_at
        """,
        (user_hash, category, n_off, n_comp, n_help, n_rej, r_sum, now.isoformat()),
    )


# ============================================================================
# 기록 (이벤트 수집) — API 레이어에서 호출. 추천 코어 함수는 순수 유지.
# ============================================================================

def record_offer(user_id: str, category: str, *, db_path: Path | None = None) -> None:
    """드릴이 추천(노출)되었을 때 — n_offered++ (탐험 분모 N에 사용)."""
    if not user_id or category not in ALL_CATEGORIES:
        return
    with _connect(db_path) as conn:
        _upsert(conn, hash_user_id(user_id), category, d_offered=1)


def record_outcome(
    user_id: str,
    category: str,
    *,
    completed: bool = False,
    helpful: bool | None = None,
    db_path: Path | None = None,
) -> None:
    """드릴 결과 반영 — 완료/도움됨 보상 누적.

    보상:
        helpful=True            → +1.0
        completed & helpful=None → +0.5
        completed & helpful=False→ +0.5 (시도는 했음)
        그 외                    → +0.0
    """
    if not user_id or category not in ALL_CATEGORIES:
        return
    reward = 0.0
    d_completed = 1 if completed else 0
    d_helpful = 1 if helpful else 0
    if helpful:
        reward = 1.0
    elif completed:
        reward = 0.5
    with _connect(db_path) as conn:
        _upsert(
            conn, hash_user_id(user_id), category,
            d_completed=d_completed, d_helpful=d_helpful, d_reward=reward,
        )


def record_reject(user_id: str, category: str, *, db_path: Path | None = None) -> None:
    """드릴 거부 — n_rejected++ (약한 음의 신호). 강한 차단은 recommender의 -2.0이 담당."""
    if not user_id or category not in ALL_CATEGORIES:
        return
    with _connect(db_path) as conn:
        _upsert(conn, hash_user_id(user_id), category, d_rejected=1)


# ============================================================================
# 추정 (UCB1) — 추천기에 가산점으로 반영
# ============================================================================

def category_reward_estimate(user_id: str, category: str, *, db_path: Path | None = None) -> float:
    """그 카테고리의 평활 평균 보상 (Beta prior). 데이터 없으면 prior=0.5."""
    if category not in ALL_CATEGORIES:
        return 0.0
    with _connect(db_path) as conn:
        row = _row(conn, hash_user_id(user_id), category)
    n = float(row["n_offered"]) if row else 0.0
    r = float(row["reward_sum"]) if row else 0.0
    rej = float(row["n_rejected"]) if row else 0.0
    # 거부는 보상에서 약하게 차감 (완전 차단 아님 — recommender가 별도 처리).
    r_adj = r - 0.25 * rej
    return (r_adj + _PRIOR_REWARD) / (n + _PRIOR_COUNT)


def _total_offers(conn: sqlite3.Connection, user_hash: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(n_offered), 0) AS total FROM category_stats WHERE user_hash = ?",
        (user_hash,),
    ).fetchone()
    return float(row["total"] or 0.0)


def ucb_bonus(
    user_id: str,
    category: str,
    *,
    lam: float = DEFAULT_LAMBDA,
    db_path: Path | None = None,
) -> float:
    """UCB1 가산점 = λ · (mean_reward + c·sqrt(2·ln N / n)), [0, BONUS_CAP]로 clamp.

    - 데이터 전혀 없으면 N=0 → 0.0 (개인화 미작동, 콜드 스타트 안전).
    - n=0 인 카테고리는 탐험 항이 커져 한 번쯤 시도되게 유도.
    """
    if not user_id or category not in ALL_CATEGORIES:
        return 0.0
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        total = _total_offers(conn, user_hash)
        row = _row(conn, user_hash, category)
    if total <= 0:
        return 0.0  # 콜드 스타트 — 개인화 끔
    n = float(row["n_offered"]) if row else 0.0
    mean_r = category_reward_estimate(user_id, category, db_path=db_path)
    if n <= 0:
        explore = 1.0  # 미시도 카테고리 — 탐험 최대
    else:
        explore = math.sqrt(2.0 * math.log(total + 1) / n)
    raw = mean_r + UCB_C * explore
    bonus = lam * raw
    return max(0.0, min(BONUS_CAP, round(bonus, 4)))


def bonus_map(
    user_id: str,
    *,
    lam: float = DEFAULT_LAMBDA,
    db_path: Path | None = None,
) -> dict[str, float]:
    """모든 카테고리의 가산점을 한 번에 — recommender에 주입 (DB 6회 조회 → 1회)."""
    if not user_id:
        return dict.fromkeys(ALL_CATEGORIES, 0.0)
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        total = _total_offers(conn, user_hash)
        rows = {
            r["category"]: r
            for r in conn.execute(
                "SELECT * FROM category_stats WHERE user_hash = ?", (user_hash,)
            ).fetchall()
        }
    out: dict[str, float] = {}
    for cat in ALL_CATEGORIES:
        if total <= 0:
            out[cat] = 0.0
            continue
        row = rows.get(cat)
        n = float(row["n_offered"]) if row else 0.0
        r = float(row["reward_sum"]) if row else 0.0
        rej = float(row["n_rejected"]) if row else 0.0
        mean_r = (r - 0.25 * rej + _PRIOR_REWARD) / (n + _PRIOR_COUNT)
        explore = 1.0 if n <= 0 else math.sqrt(2.0 * math.log(total + 1) / n)
        bonus = lam * (mean_r + UCB_C * explore)
        out[cat] = max(0.0, min(BONUS_CAP, round(bonus, 4)))
    return out


# ============================================================================
# 프로파일 조회 — 엔드포인트·주간 코칭 narrative 용
# ============================================================================

def get_profile(user_id: str, *, db_path: Path | None = None) -> dict:
    """사용자 개인화 프로파일 전체 — 카테고리별 통계 + 보상 추정 + 가산점."""
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        total = _total_offers(conn, user_hash)
        rows = {
            r["category"]: r
            for r in conn.execute(
                "SELECT * FROM category_stats WHERE user_hash = ?", (user_hash,)
            ).fetchall()
        }
    bonuses = bonus_map(user_id, db_path=db_path)
    categories: list[dict] = []
    for cat in ALL_CATEGORIES:
        row = rows.get(cat)
        # 할인 UCB로 카운트는 실수(effective count) — 표시는 반올림.
        n_off = round(float(row["n_offered"])) if row else 0
        n_comp = round(float(row["n_completed"])) if row else 0
        n_help = round(float(row["n_helpful"])) if row else 0
        n_rej = round(float(row["n_rejected"])) if row else 0
        categories.append({
            "category": cat,
            "label_ko": CATEGORY_LABEL_KO.get(cat, cat),
            "n_offered": n_off,
            "n_completed": n_comp,
            "n_helpful": n_help,
            "n_rejected": n_rej,
            "reward_estimate": round(category_reward_estimate(user_id, cat, db_path=db_path), 3),
            "ucb_bonus": bonuses.get(cat, 0.0),
        })
    categories.sort(key=lambda d: d["reward_estimate"], reverse=True)
    learned = total >= 3  # 누적 노출(감쇠 반영) 3회↑부터 "학습됨" 간주
    return {
        "user_id": user_id,
        "total_offers": round(total),       # 감쇠 반영 effective offers (표시용 반올림)
        "total_offers_effective": round(total, 2),  # 정밀값 (디버그/분석)
        "is_learning_active": learned,
        "categories": categories,
    }


def top_helpful_category(user_id: str, *, min_offers: int = 2, db_path: Path | None = None) -> dict | None:
    """가장 도움이 된 카테고리 1개 (n_offered>=min_offers, n_helpful>=1).

    주간 코칭의 "지난 흐름상 X가 가장 잘 맞았어요" 문구·next_week_focus 보조용.
    """
    prof = get_profile(user_id, db_path=db_path)
    best: dict | None = None
    for c in prof["categories"]:
        if c["n_offered"] >= min_offers and c["n_helpful"] >= 1:
            if best is None or c["reward_estimate"] > best["reward_estimate"]:
                best = c
    return best


def reset_user(user_id: str, *, db_path: Path | None = None) -> int:
    """사용자 개인화 데이터 삭제 (GDPR/§16.3 잊혀질 권리)."""
    user_hash = hash_user_id(user_id)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM category_stats WHERE user_hash = ?", (user_hash,))
        return cur.rowcount
