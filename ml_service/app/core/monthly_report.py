# 출처: v9.5 정책 — 일 1회 입력에 따른 월간 리포트 신규.
"""월간 리포트 — 약 30일 entries 기반 통계.

주간 리포트(7개)는 단기 추세, 월간 리포트(30개)는 장기 패턴 발견.
v9.5: 일 1회 입력 정책으로 월간 표본이 정확히 "한 달치 분석"이 됨.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any, Sequence

from app.schemas.common import EMOTIONS_KO, PATTERNS_KO, BEHAVIORS_KO


def _parse_month(month_str: str) -> tuple[date, date]:
    """\"2026-05\" → (2026-05-01, 2026-05-31)."""
    year_s, mo_s = month_str.split("-")
    year, mo = int(year_s), int(mo_s)
    start = date(year, mo, 1)
    # 다음 달 1일 - 1
    if mo == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mo + 1, 1)
    from datetime import timedelta as _td
    end = end - _td(days=1)
    return start, end


def monthly_overview(entries: Sequence[dict[str, Any]]) -> dict:
    """월 컨디션 평균 + 기록 일수."""
    conds = [int(e.get("self_condition", 0)) for e in entries if e.get("self_condition")]
    recorded_days = len({datetime.fromisoformat(e["created_at"]).date().isoformat() for e in entries})
    return {
        "recorded_days": recorded_days,
        "total_entries": len(entries),
        "avg_self_condition": round(sum(conds) / len(conds), 2) if conds else 0.0,
    }


def monthly_dominant_pattern(entries: Sequence[dict[str, Any]]) -> dict:
    """월간 dominant 패턴 — 표본 30개라 임계 0.4 그대로 (주간보다 엄격)."""
    counter: Counter[str] = Counter()
    for e in entries:
        patterns = (e.get("label_result", {}) or {}).get("patterns", {}) or {}
        if not patterns:
            continue
        top, top_val = max(patterns.items(), key=lambda kv: kv[1])
        if top_val >= 0.4:
            counter[top] += 1
    total = sum(counter.values())
    if total == 0:
        return {"dominant_key": PATTERNS_KO[0], "ratio_percent": 0.0, "occurrences": 0, "total_strong": 0}
    name, count = counter.most_common(1)[0]
    return {
        "dominant_key": name,
        "ratio_percent": round(100.0 * count / total, 1),
        "occurrences": count,
        "total_strong": total,
    }


def monthly_calendar_distribution(entries: Sequence[dict[str, Any]]) -> dict:
    """월간 8색 dominant 분포."""
    counter = Counter(e.get("calendar_dominant", "weak_signal_positive") for e in entries)
    return {"distribution": dict(counter)}


def monthly_emotion_pentagon(entries: Sequence[dict[str, Any]]) -> dict:
    """월간 5감정 평균 — 5각형 radar chart 데이터."""
    sums = {k: 0.0 for k in EMOTIONS_KO}
    n = 0
    for e in entries:
        emotions = (e.get("label_result", {}) or {}).get("emotions", {}) or {}
        if not emotions:
            continue
        n += 1
        for k in EMOTIONS_KO:
            sums[k] += float(emotions.get(k, 0.0))
    if n == 0:
        axes = [{"label": k, "value": 0.0} for k in EMOTIONS_KO]
        return {"axes": axes, "dominant": EMOTIONS_KO[0], "entries_used": 0}
    avgs = {k: round(sums[k] / n, 3) for k in EMOTIONS_KO}
    axes = [{"label": k, "value": avgs[k]} for k in EMOTIONS_KO]
    dominant = max(avgs.items(), key=lambda kv: kv[1])[0]
    return {"axes": axes, "dominant": dominant, "entries_used": n}


def monthly_condition_trend(entries: Sequence[dict[str, Any]]) -> dict:
    """4주차별 컨디션 평균 — 월 단위 추세."""
    by_week: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        try:
            dt = datetime.fromisoformat(e["created_at"])
        except (KeyError, ValueError):
            continue
        sc = e.get("self_condition")
        if sc is None:
            continue
        # 월 내 N주차 (1~5)
        week_in_month = (dt.day - 1) // 7 + 1
        by_week[week_in_month].append(int(sc))

    weeks = []
    for w in range(1, 6):
        vals = by_week.get(w, [])
        weeks.append({
            "week_in_month": w,
            "avg_condition": round(sum(vals) / len(vals), 2) if vals else None,
            "count": len(vals),
        })
    return {"weeks": weeks}


def monthly_drill_action(
    drills_recommended: int,
    drills_practiced: int,
) -> dict:
    """월간 드릴 실천율."""
    rate = (drills_practiced / drills_recommended) if drills_recommended else 0.0
    return {
        "recommended_count": drills_recommended,
        "practiced_count": drills_practiced,
        "practice_rate": round(rate, 2),
    }


def build_monthly_report(
    *,
    month: str,
    user_id: str,
    entries: Sequence[dict[str, Any]],
    drills_recommended: int = 0,
    drills_practiced: int = 0,
) -> dict:
    """월간 리포트 빌더 — 약 30 entries 기반.

    Args:
        month: \"YYYY-MM\" 형식.
        entries: 월 안의 모든 entries (일 1회 × ~30일 = 약 30개).
        drills_recommended/practiced: 월간 누적.

    Returns:
        overview / dominant_pattern / calendar_distribution /
        emotion_pentagon / condition_trend / drill_action 6 블록.
        v9.6: monthly_coaching (장기 상태·경향·다음 달 초점) 추가.
    """
    try:
        from app.core.weekly_coaching import build_weekly_coaching
        coaching = build_weekly_coaching(entries=list(entries), user_id=user_id)
    except Exception:  # noqa: BLE001
        coaching = None
    return {
        "month": month,
        "user_id": user_id,
        "overview": monthly_overview(entries),
        "dominant_pattern": monthly_dominant_pattern(entries),
        "calendar_distribution": monthly_calendar_distribution(entries),
        "emotion_pentagon": monthly_emotion_pentagon(entries),
        "condition_trend": monthly_condition_trend(entries),
        "drill_action": monthly_drill_action(drills_recommended, drills_practiced),
        "monthly_coaching": coaching,   # v9.6 (additive — FE optional)
    }
