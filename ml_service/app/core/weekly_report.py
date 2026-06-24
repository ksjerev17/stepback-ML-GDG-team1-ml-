# 출처: CLAUDE.md §4.8, §10.5, §9.6
"""주간 리포트 5블록 산출 + 발견·흐름·패턴 변화."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Sequence

from app.core.auto_discovery import discover_all
from app.core.baselines import compare_to_baseline
from app.core.self_check_quiz import build_quiz
from app.core.weekly_coaching import build_weekly_coaching
from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO


def _parse_week(week_str: str) -> tuple[date, date]:
    """ISO 주차 ('2026-W21') → (시작일, 종료일) 월~일."""
    year_s, w_s = week_str.split("-W")
    year, w = int(year_s), int(w_s)
    start = date.fromisocalendar(year, w, 1)
    end = date.fromisocalendar(year, w, 7)
    return start, end


def _prev_week(week_str: str) -> str:
    start, _ = _parse_week(week_str)
    prev_day = start - timedelta(days=1)
    iso = prev_day.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def condition_flow(entries: Sequence[dict[str, Any]]) -> dict:
    """월~일 7일 컨디션 평균 — §9.2."""
    by_dow: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        try:
            dt = datetime.fromisoformat(e["created_at"])
        except (KeyError, ValueError):
            continue
        sc = e.get("self_condition")
        if sc is None:
            continue
        by_dow[dt.isoweekday()].append(int(sc))
    labels = ["월", "화", "수", "목", "금", "토", "일"]
    points = []
    for dow in range(1, 8):
        vals = by_dow.get(dow, [])
        points.append({
            "dow": labels[dow - 1],
            "avg_condition": round(sum(vals) / len(vals), 2) if vals else None,
            "count": len(vals),
        })
    return {"points": points}


def emotion_pentagon(entries: Sequence[dict[str, Any]]) -> dict:
    """v9.5: 5감정 평균 — 오각형 시각화 데이터.

    일주일 7개 entries (일 1회 × 7일)의 5감정 평균을 산출.
    FE는 axes 배열을 받아 5각형 radar chart로 표시.

    공식:
        for emotion in EMOTIONS_KO:
            axes[emotion] = avg(entry.label_result.emotions[emotion] for entry in entries)

    반환:
        {
            "axes": [
                {"label": "불안", "value": 0.45},
                {"label": "우울", "value": 0.32},
                {"label": "분노", "value": 0.18},
                {"label": "죄책", "value": 0.21},
                {"label": "중립", "value": 0.55},
            ],
            "dominant": "중립",
            "entries_used": 7,
        }
    """
    sums: dict[str, float] = {k: 0.0 for k in EMOTIONS_KO}
    count = 0
    for e in entries:
        lr = e.get("label_result", {}) or {}
        emotions = lr.get("emotions", {}) or {}
        if not emotions:
            continue
        count += 1
        for k in EMOTIONS_KO:
            sums[k] += float(emotions.get(k, 0.0))

    if count == 0:
        # 빈 응답 — 0으로 채움 (5각형이 점으로 표시됨)
        axes = [{"label": k, "value": 0.0} for k in EMOTIONS_KO]
        return {"axes": axes, "dominant": EMOTIONS_KO[0], "entries_used": 0}

    avgs = {k: round(sums[k] / count, 3) for k in EMOTIONS_KO}
    axes = [{"label": k, "value": avgs[k]} for k in EMOTIONS_KO]
    dominant = max(avgs.items(), key=lambda kv: kv[1])[0]
    return {
        "axes": axes,
        "dominant": dominant,
        "entries_used": count,
    }


def pattern_distribution(entries: Sequence[dict[str, Any]]) -> dict[str, float]:
    """주차 내 각 패턴이 dominant였던 비율 (%)."""
    counter: Counter[str] = Counter()
    total = 0
    for e in entries:
        lr = e.get("label_result", {}) or {}
        patterns = lr.get("patterns", {}) or {}
        if not patterns:
            continue
        top, top_val = max(patterns.items(), key=lambda kv: kv[1])
        if top_val >= 0.05:
            counter[top] += 1
            total += 1
    if total == 0:
        return {}
    return {k: round(100.0 * v / total, 1) for k, v in counter.items()}


def pattern_diff(
    current_entries: Sequence[dict[str, Any]],
    prev_entries: Sequence[dict[str, Any]],
) -> list[dict]:
    """이번 주 vs 지난 주 패턴 비율 비교 — §9.3."""
    curr = pattern_distribution(current_entries)
    prev = pattern_distribution(prev_entries)
    rows: list[dict] = []
    all_keys = set(curr.keys()) | set(prev.keys())
    for k in PATTERNS_KO:
        if k not in all_keys:
            continue
        c = curr.get(k, 0.0)
        p = prev.get(k, 0.0)
        delta = round(c - p, 1)
        if delta > 1:
            arrow = "up"
        elif delta < -1:
            arrow = "down"
        else:
            arrow = "flat"
        rows.append({
            "pattern": k,
            "current_percent": c,
            "prev_percent": p,
            "delta_percent": delta,
            "arrow": arrow,
        })
    return rows


def build_report(
    *,
    week: str,
    user_id: str,
    entries: Sequence[dict[str, Any]],
    drills_recommended: int = 0,
    drills_practiced: int = 0,
    prev_week_avg: float | None = None,
    prev_entries: Sequence[dict[str, Any]] | None = None,
    feedback_rows: Sequence[dict[str, Any]] | None = None,
    rng: random.Random | None = None,
) -> dict:
    """5블록 리포트. entries는 BE에서 주차별 entry 모음을 전달.

    각 entry 형식:
      {
        "created_at": ISO datetime,
        "self_condition": int 1~5,
        "label_result": {patterns, behaviors, emotions, ...},
        "calendar_dominant": str
      }
    """
    rng = rng or random.Random()

    # Block 1 — overview
    recorded_days = len({datetime.fromisoformat(e["created_at"]).date().isoformat() for e in entries})
    conds = [int(e.get("self_condition", 0)) for e in entries if e.get("self_condition")]
    avg = sum(conds) / len(conds) if conds else 0.0
    delta = round(avg - prev_week_avg, 2) if prev_week_avg is not None else None

    # Block 2 — dominant pattern (인지 패턴 중 가장 자주 보인 dominant)
    pattern_counter: Counter[str] = Counter()
    for e in entries:
        lr = e.get("label_result", {})
        patterns = lr.get("patterns", {}) or {}
        if not patterns:
            continue
        top, top_val = max(patterns.items(), key=lambda kv: kv[1])
        # v9.5: 표본 7개 (일 1회 × 7일) — 임계 0.4 → 0.35 완화
        if top_val >= 0.05:
            pattern_counter[top] += 1
    total_strong = sum(pattern_counter.values())
    if total_strong > 0:
        dom_name, dom_count = pattern_counter.most_common(1)[0]
        dom_ratio = 100.0 * dom_count / total_strong
    else:
        dom_name, dom_count, dom_ratio = (PATTERNS_KO[0], 0, 0.0)

    block2 = {
        "dominant_key": dom_name,
        "ratio_percent": round(dom_ratio, 1),
        "occurrences": dom_count,
    }

    # Block 3 — drill action
    practice_rate = (drills_practiced / drills_recommended) if drills_recommended else 0.0
    block3 = {
        "recommended_count": drills_recommended,
        "practiced_count": drills_practiced,
        "practice_rate": round(practice_rate, 2),
    }

    # Block 4 — self-check quiz (v9.4.3: 정답은 server-side cache에)
    block4 = build_quiz(
        dominant_pattern=dom_name,
        actual_ratio_percent=dom_ratio,
        rng=rng,
        user_id=user_id,
        week=week,
    )

    # Block 5 — calendar dominant distribution
    cal_counter = Counter(e.get("calendar_dominant", "weak_signal_positive") for e in entries)
    block5 = {"distribution": dict(cal_counter)}

    # Block 6 — condition_flow + pattern_diff + auto discovery (§9.2, §9.3, §8.4)
    flow = condition_flow(entries)
    diff = pattern_diff(entries, prev_entries or [])
    discoveries = discover_all(list(entries), list(feedback_rows or []))

    # baseline 비교 카드 (§10.2) — 데이터 없으면 None
    cur_p_avg = {k: 0.0 for k in PATTERNS_KO}
    cur_b_avg = {k: 0.0 for k in BEHAVIORS_KO}
    if entries:
        for k in PATTERNS_KO:
            cur_p_avg[k] = round(
                sum(float((e.get("label_result", {}) or {}).get("patterns", {}).get(k, 0.0)) for e in entries) / len(entries),
                3,
            )
        for k in BEHAVIORS_KO:
            cur_b_avg[k] = round(
                sum(float((e.get("label_result", {}) or {}).get("behaviors", {}).get(k, 0.0)) for e in entries) / len(entries),
                3,
            )
    try:
        baseline_card = compare_to_baseline(
            user_id,
            current_patterns_avg=cur_p_avg,
            current_behaviors_avg=cur_b_avg,
        )
    except Exception:
        baseline_card = None

    # v9.5: 디자인 "분석을 제공하기 위한 데이터가 부족합니다" 메시지
    # 일 1회 × 7일이라 표본 < 4일이면 fallback
    insufficient = recorded_days < 4
    insufficient_message = (
        "분석을 제공하기 위한 데이터가 부족합니다"
        if insufficient else None
    )

    # v9.6: 주간 개인화 코칭 — 상태 추론 + 경향 narrative + 다음 주 초점.
    try:
        coaching = build_weekly_coaching(entries=list(entries), user_id=user_id)
    except Exception:  # noqa: BLE001 (코칭 실패해도 리포트 본체는 반환)
        coaching = None

    return {
        "week": week,
        "user_id": user_id,
        "overview": {
            "recorded_days": recorded_days,
            "avg_self_condition": round(avg, 2),
            "prev_week_avg": prev_week_avg,
            "delta_vs_prev": delta,
        },
        "dominant_pattern": block2,
        "drill_action": block3,
        "self_check_quiz": block4,
        "calendar_distribution": block5,
        "condition_flow": flow,
        "pattern_diff": diff,
        "pattern_diff_message": insufficient_message,    # v9.5
        "discoveries": discoveries,
        "discoveries_message": insufficient_message if not discoveries else None,  # v9.5
        "baseline_card": baseline_card,
        "emotion_pentagon": emotion_pentagon(entries),
        "insufficient_data": insufficient,    # v9.5: FE 부족 안내용 플래그
        "weekly_coaching": coaching,          # v9.6: 개인화 코칭 블록
    }
