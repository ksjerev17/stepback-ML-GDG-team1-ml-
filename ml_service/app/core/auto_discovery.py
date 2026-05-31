# 출처: 명세서 §8.4
"""시스템 자동 발견 — 4 알고리즘.

1. 자주 보인 표현 top 2 — evidence_span 빈도
2. 맥락 ↔ 패턴 상관 — 수면 6h 미만 vs 7h 이상 dominant 평균 차이 >= 0.2
3. 효과적 드릴 top 1 — helpful 비율 가장 높은 드릴
4. 주간 회복/소진 패턴 — 주 전반(월~수) vs 후반(목~일) 컨디션·신호 차이 (v9.5)

표현 원칙 (§8.6 / §11.4): 인과 단정 X. 상관 관찰 톤만 사용.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def top_evidence_spans(entries: Iterable[dict[str, Any]], top_n: int = 2) -> list[dict]:
    """evidence_span 빈도 top N — 짧은 표현 우선 (3~12자)."""
    counter: Counter[str] = Counter()
    for e in entries:
        lr = e.get("label_result", {}) or {}
        span = (lr.get("evidence_span") or "").strip()
        if 3 <= len(span) <= 12:
            counter[span] += 1
    items: list[dict] = []
    for span, count in counter.most_common(top_n):
        items.append({
            "text": f"이번 주 '{span}' 표현이 {count}회 보였어요",
            "category": "cognitive",
            "source": "system",
            "count": count,
        })
    return items


def context_pattern_correlation(
    entries: Iterable[dict[str, Any]],
    pattern_name: str = "미래예측",
    *,
    threshold: float = 0.2,
) -> dict | None:
    """수면 6h 미만 vs 7h 이상에서 패턴 평균 차이 — threshold 이상 시 발견."""
    low_vals: list[float] = []
    high_vals: list[float] = []
    for e in entries:
        ctx = e.get("context", {}) or {}
        lr = e.get("label_result", {}) or {}
        patterns = lr.get("patterns", {}) or {}
        score = float(patterns.get(pattern_name, 0.0))
        sleep = ctx.get("sleep_hours")
        if sleep is None:
            continue
        try:
            sleep_f = float(sleep)
        except (TypeError, ValueError):
            continue
        if sleep_f < 6:
            low_vals.append(score)
        elif sleep_f >= 7:
            high_vals.append(score)
    if not low_vals or not high_vals:
        return None
    low_avg = sum(low_vals) / len(low_vals)
    high_avg = sum(high_vals) / len(high_vals)
    diff = abs(low_avg - high_avg)
    if diff < threshold:
        return None
    direction = "더 자주 보였어요" if low_avg > high_avg else "덜 보였어요"
    return {
        "text": f"잠 6시간 미만 날에 {pattern_name} 표현이 {direction} (평균 {low_avg:.2f} vs {high_avg:.2f})",
        "category": "context",
        "source": "system",
        "low_avg": round(low_avg, 2),
        "high_avg": round(high_avg, 2),
        "delta": round(diff, 2),
    }


def top_helpful_drill(feedback_rows: Iterable[dict[str, Any]], min_count: int = 2) -> dict | None:
    """드릴별 helpful 비율 가장 높은 것. drill_id별 helpful 카운트 / 총 카운트."""
    by_drill: dict[str, list[bool]] = {}
    for fb in feedback_rows:
        drill_id = fb.get("drill_id")
        rating = fb.get("rating")
        if not drill_id:
            continue
        helpful_flag = rating == "helpful"
        by_drill.setdefault(drill_id, []).append(helpful_flag)
    if not by_drill:
        return None
    scored = []
    for did, flags in by_drill.items():
        if len(flags) < min_count:
            continue
        ratio = sum(flags) / len(flags)
        scored.append((ratio, len(flags), did))
    if not scored:
        return None
    scored.sort(reverse=True)
    ratio, n, did = scored[0]
    return {
        "text": f"드릴 {did}이 '도움됨' 비율 {ratio:.0%} ({n}회 시도)",
        "category": "drill",
        "source": "system",
        "drill_id": did,
        "helpful_ratio": round(ratio, 2),
        "sample": n,
    }


def weekly_recovery_pattern(entries: Iterable[dict[str, Any]]) -> dict | None:
    """v9.5: 일 1회 정책에 맞춘 주간 회복/소진 패턴.

    이전 v9.4.x의 diurnal(아침/저녁) 비교는 일 1회 정책에서 의미 X.
    대신 주 전반(월~수) vs 주 후반(목~일) 컨디션·신호 차이를 본다.

    공식:
        early = entries with weekday in [월, 화, 수]
        late  = entries with weekday in [목, 금, 토, 일]
        cond_diff = avg(late.self_condition) - avg(early.self_condition)
        sig_diff  = avg(early.max_pattern) - avg(late.max_pattern)

    발견 기준 (둘 중 하나):
        - |cond_diff| >= 0.5
        - |sig_diff| >= 0.2

    표현 (§8.6 인과 단정 X — 관찰 톤):
        - cond_diff >= 0.5  → "recovery" (주 후반 회복)
        - cond_diff <= -0.5 → "fatigue"  (주 후반 소진)
        - sig_diff >= 0.2   → "early_load" (주 전반 인지 부담)
        - sig_diff <= -0.2  → "late_load"  (주 후반 인지 부담)
    """
    from datetime import datetime as _dt

    early_cond: list[int] = []
    late_cond: list[int] = []
    early_sig: list[float] = []
    late_sig: list[float] = []

    for e in entries:
        try:
            dt = _dt.fromisoformat(e["created_at"])
        except (KeyError, ValueError, TypeError):
            continue
        dow = dt.isoweekday()  # 1=월 ~ 7=일

        sc = e.get("self_condition")
        if sc is not None:
            try:
                sc_i = int(sc)
                if dow <= 3:
                    early_cond.append(sc_i)
                else:
                    late_cond.append(sc_i)
            except (TypeError, ValueError):
                pass

        lr = e.get("label_result", {}) or {}
        patterns = lr.get("patterns", {}) or {}
        if patterns:
            max_p = max(float(v) for v in patterns.values())
            if dow <= 3:
                early_sig.append(max_p)
            else:
                late_sig.append(max_p)

    if not early_cond or not late_cond:
        return None

    e_cond = sum(early_cond) / len(early_cond)
    l_cond = sum(late_cond) / len(late_cond)
    cond_diff = l_cond - e_cond

    e_sig = sum(early_sig) / len(early_sig) if early_sig else 0.0
    l_sig = sum(late_sig) / len(late_sig) if late_sig else 0.0
    sig_diff = e_sig - l_sig

    if abs(cond_diff) < 0.5 and abs(sig_diff) < 0.2:
        return None

    if cond_diff >= 0.5:
        msg = f"한 주 후반으로 갈수록 컨디션이 회복되는 패턴이에요 (전반 {e_cond:.1f} → 후반 {l_cond:.1f})"
        pattern_type = "recovery"
    elif cond_diff <= -0.5:
        msg = f"한 주 전반이 더 좋았어요 (전반 {e_cond:.1f} → 후반 {l_cond:.1f})"
        pattern_type = "fatigue"
    elif sig_diff >= 0.2:
        msg = f"주 전반에 인지 신호가 더 자주 보였어요 (평균 강도 전반 {e_sig:.2f} vs 후반 {l_sig:.2f})"
        pattern_type = "early_load"
    else:
        msg = f"주 후반에 인지 신호가 더 자주 보였어요 (평균 강도 전반 {e_sig:.2f} vs 후반 {l_sig:.2f})"
        pattern_type = "late_load"

    return {
        "text": msg,
        "category": "context",
        "source": "system",
        "pattern_type": pattern_type,
        "early_condition_avg": round(e_cond, 2),
        "late_condition_avg": round(l_cond, 2),
        "condition_delta": round(cond_diff, 2),
        "early_signal_avg": round(e_sig, 2),
        "late_signal_avg": round(l_sig, 2),
        "sample_early": len(early_cond),
        "sample_late": len(late_cond),
    }


# v9.4.x 호환 alias — 옛 이름으로 호출하는 코드 안 깨짐.
diurnal_recovery_pattern = weekly_recovery_pattern



def discover_all(
    entries: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """4 알고리즘 통합 호출 (v9.5 — 일 1회 정책 반영):
    1) top_evidence_spans          — 자주 보인 표현 top 2
    2) context_pattern_correlation — 수면 vs 패턴 상관 (top 1)
    3) top_helpful_drill           — 효과적 드릴 top 1
    4) weekly_recovery_pattern     — 주 전반(월~수) vs 후반(목~일) 회복/소진 패턴
    (옛 diurnal_recovery_pattern 은 alias 호환만 유지 — 호출 X)
    """
    results: list[dict] = []
    results.extend(top_evidence_spans(entries, top_n=2))
    for pat in ("미래예측", "자기비난", "회피미루기"):
        card = context_pattern_correlation(entries, pattern_name=pat)
        if card:
            results.append(card)
            break  # 가장 강한 상관 1개만
    fb = feedback_rows or []
    drill_card = top_helpful_drill(fb)
    if drill_card:
        results.append(drill_card)
    # v9.5: 주간 회복 패턴 (일 1회 정책)
    weekly_pat = weekly_recovery_pattern(entries)
    if weekly_pat:
        results.append(weekly_pat)
    return results
