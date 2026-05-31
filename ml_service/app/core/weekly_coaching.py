# 출처: v9.6 — 개인화 강화. 주간 흐름 → 상태 추론 + 경향 narrative + 다음 주 초점.
"""주간 개인화 코칭 — 한 주의 흐름을 읽어 "상태"를 추론하고,
"이러할 때 이러한 경향이 보여요" 식의 관찰 narrative와 다음 주 초점을 만든다.

설계 원칙 (§8.6 / §11.4 — 진단 X, 인과 단정 X):
- 모든 문구는 "발견·관찰" 톤. "~인 것 같아요 / ~경향이 보였어요"만 사용.
- "우울증·불안장애" 같은 진단어 절대 X (scripts/lint_copy.py가 CI에서 차단).
- 인과("때문에") 단정 X — 상관("~한 날에 ~가 더 보였어요")만.

구성:
1. state         — 이번 주를 한 단어 상태로 추론 (회복기/부담기/안정기/소진기/관찰기)
2. tendencies    — 조건부 경향 관찰 (수면·컨디션·요일 ↔ 신호)
3. next_week_focus — 다음 주 추천 초점 카테고리 (적응 — 개인화 프로파일 반영)
4. personalization_note — 지금까지 가장 잘 맞은 드릴 방향 (학습 결과 사용자 노출)

이 블록이 "시스템이 사용자와 함께 변화한다"는 서비스 핵심 가치를 사용자에게 직접 보여준다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.core import personalization
from app.schemas.common import (
    CATEGORY_LABEL_KO,
    PATTERNS_KO,
    BEHAVIORS_KO,
)

# 패턴/행동 → 추천 드릴 카테고리 매핑 (recommender 라우팅과 일치).
_SIGNAL_TO_CATEGORY: dict[str, str] = {
    # 인지 패턴 → 인지 재구성
    **dict.fromkeys(PATTERNS_KO, "cognitive_restructuring"),
    # 행동
    "회피미루기": "behavioral_activation",
    "동기저하": "habit_design",
}


def _entry_dt(e: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(e["created_at"])
    except (KeyError, ValueError, TypeError):
        return None


def _max_pattern_load(e: dict[str, Any]) -> float:
    patterns = (e.get("label_result", {}) or {}).get("patterns", {}) or {}
    if not patterns:
        return 0.0
    return max(float(v) for v in patterns.values())


def _top_neg_emotion(entries: Sequence[dict[str, Any]]) -> tuple[str, float]:
    sums: dict[str, float] = defaultdict(float)
    n = 0
    for e in entries:
        emo = (e.get("label_result", {}) or {}).get("emotions", {}) or {}
        if not emo:
            continue
        n += 1
        for k, v in emo.items():
            if k == "중립":
                continue
            sums[k] += float(v)
    if n == 0 or not sums:
        return "", 0.0
    top = max(sums.items(), key=lambda kv: kv[1])
    return top[0], round(top[1] / n, 3)


# ============================================================================
# 1. 상태 추론
# ============================================================================

def infer_state(entries: Sequence[dict[str, Any]]) -> dict:
    """한 주의 컨디션 추세 + 신호 부담 + 감정으로 상태 1개 추론.

    표본 < 4일이면 "관찰기"(데이터 부족). 인과 X — 관찰 요약만.
    """
    conds = [int(e.get("self_condition")) for e in entries if e.get("self_condition")]
    recorded_days = len({
        dt.date().isoformat() for e in entries if (dt := _entry_dt(e))
    })
    if recorded_days < 4 or len(conds) < 4:
        return {
            "key": "observing",
            "label": "관찰기",
            "summary": "아직 한 주를 읽기엔 기록이 적어요. 며칠 더 모이면 흐름이 보여요.",
            "confidence": "부족",
            "avg_condition": round(sum(conds) / len(conds), 2) if conds else None,
        }

    # 전반(월~수) vs 후반(목~일) 컨디션
    early, late = [], []
    for e in entries:
        dt = _entry_dt(e)
        sc = e.get("self_condition")
        if dt is None or sc is None:
            continue
        (early if dt.isoweekday() <= 3 else late).append(int(sc))
    e_avg = sum(early) / len(early) if early else None
    l_avg = sum(late) / len(late) if late else None
    slope = (l_avg - e_avg) if (e_avg is not None and l_avg is not None) else 0.0

    avg_cond = sum(conds) / len(conds)
    loads = [_max_pattern_load(e) for e in entries]
    avg_load = sum(loads) / len(loads) if loads else 0.0
    neg_name, neg_val = _top_neg_emotion(entries)

    # 우선순위: 추세 → 부담 → 감정 → 안정
    if slope >= 0.5:
        return {
            "key": "recovery", "label": "회복기",
            "summary": f"한 주 후반으로 갈수록 컨디션이 올라오는 흐름이에요 (전반 {e_avg:.1f} → 후반 {l_avg:.1f}).",
            "confidence": "관찰", "avg_condition": round(avg_cond, 2), "slope": round(slope, 2),
        }
    if slope <= -0.5:
        return {
            "key": "fatigue", "label": "소진기",
            "summary": f"주 전반이 더 좋았고 후반에 가라앉는 흐름이 보였어요 (전반 {e_avg:.1f} → 후반 {l_avg:.1f}).",
            "confidence": "관찰", "avg_condition": round(avg_cond, 2), "slope": round(slope, 2),
        }
    if avg_load >= 0.45 and avg_cond <= 2.7:
        return {
            "key": "loaded", "label": "부담기",
            "summary": f"생각의 무게가 한 주 내내 비교적 높게 보였어요 (평균 신호 {avg_load:.2f}).",
            "confidence": "관찰", "avg_condition": round(avg_cond, 2), "avg_load": round(avg_load, 2),
        }
    if neg_val >= 0.5:
        return {
            "key": "turbulent", "label": "흔들림",
            "summary": f"이번 주는 '{neg_name}' 감정이 자주 올라온 한 주였어요.",
            "confidence": "관찰", "avg_condition": round(avg_cond, 2),
            "dominant_emotion": neg_name,
        }
    if avg_cond >= 3.2:
        return {
            "key": "stable", "label": "안정기",
            "summary": f"전반적으로 잔잔하게 흘러간 한 주예요 (평균 컨디션 {avg_cond:.1f}).",
            "confidence": "관찰", "avg_condition": round(avg_cond, 2),
        }
    return {
        "key": "low", "label": "낮은 에너지",
        "summary": f"컨디션이 전반적으로 낮게 머문 한 주였어요 (평균 {avg_cond:.1f}).",
        "confidence": "관찰", "avg_condition": round(avg_cond, 2),
    }


# ============================================================================
# 2. 경향 narrative ("이러할 때 이러한 경향이 보여요")
# ============================================================================

def _sleep_pattern_tendency(entries: Sequence[dict[str, Any]], *, threshold: float = 0.15) -> dict | None:
    """수면 부족(<6h) vs 충분(>=7h) 날의 dominant 인지 패턴 차이."""
    low: dict[str, list[float]] = defaultdict(list)
    high: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        sleep = (e.get("context", {}) or {}).get("sleep_hours")
        patterns = (e.get("label_result", {}) or {}).get("patterns", {}) or {}
        if sleep is None or not patterns:
            continue
        try:
            sh = float(sleep)
        except (TypeError, ValueError):
            continue
        bucket = low if sh < 6 else (high if sh >= 7 else None)
        if bucket is None:
            continue
        for k in PATTERNS_KO:
            bucket[k].append(float(patterns.get(k, 0.0)))
    best = None
    for k in PATTERNS_KO:
        lo, hi = low.get(k, []), high.get(k, [])
        if len(lo) < 2 or len(hi) < 1:   # v9.6: 한쪽 버킷이 너무 얇으면 잡음 — 최소 표본 가드
            continue
        lo_a, hi_a = sum(lo) / len(lo), sum(hi) / len(hi)
        diff = lo_a - hi_a
        if abs(diff) >= threshold and (best is None or abs(diff) > abs(best["diff"])):
            best = {"pattern": k, "diff": diff, "lo": lo_a, "hi": hi_a}
    if best is None:
        return None
    more = best["diff"] > 0
    verb = "더 자주" if more else "덜"
    return {
        "kind": "sleep_pattern",
        "text": f"잠이 6시간 미만이던 날엔 '{best['pattern']}' 표현이 {verb} 보였어요.",
        "detail": f"평균 {best['lo']:.2f} vs 충분히 잔 날 {best['hi']:.2f}",
        "strength": "관찰",
        "strength_score": abs(best["diff"]),
    }


def _condition_pattern_tendency(entries: Sequence[dict[str, Any]], *, threshold: float = 0.15) -> dict | None:
    """컨디션 낮은 날(<=2) vs 좋은 날(>=4)의 dominant 패턴 차이."""
    low: dict[str, list[float]] = defaultdict(list)
    high: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        sc = e.get("self_condition")
        patterns = (e.get("label_result", {}) or {}).get("patterns", {}) or {}
        if sc is None or not patterns:
            continue
        sc_i = int(sc)
        bucket = low if sc_i <= 2 else (high if sc_i >= 4 else None)
        if bucket is None:
            continue
        for k in PATTERNS_KO:
            bucket[k].append(float(patterns.get(k, 0.0)))
    best = None
    for k in PATTERNS_KO:
        lo, hi = low.get(k, []), high.get(k, [])
        if len(lo) < 2 or len(hi) < 1:   # v9.6: 한쪽 버킷이 너무 얇으면 잡음 — 최소 표본 가드
            continue
        lo_a, hi_a = sum(lo) / len(lo), sum(hi) / len(hi)
        diff = lo_a - hi_a
        if abs(diff) >= threshold and (best is None or abs(diff) > abs(best["diff"])):
            best = {"pattern": k, "diff": diff, "lo": lo_a, "hi": hi_a}
    if best is None:
        return None
    more = best["diff"] > 0
    verb = "더 자주" if more else "덜"
    return {
        "kind": "condition_pattern",
        "text": f"컨디션이 낮았던 날엔 '{best['pattern']}' 생각이 {verb} 떠올랐던 것 같아요.",
        "detail": f"낮은 날 {best['lo']:.2f} vs 좋은 날 {best['hi']:.2f}",
        "strength": "관찰",
        "strength_score": abs(best["diff"]),
    }


def _weekday_tendency(entries: Sequence[dict[str, Any]]) -> dict | None:
    """가장 가라앉았던 요일 — 컨디션 평균 최저 요일 (관찰만)."""
    by_dow: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        dt = _entry_dt(e)
        sc = e.get("self_condition")
        if dt is None or sc is None:
            continue
        by_dow[dt.isoweekday()].append(int(sc))
    full = {d: v for d, v in by_dow.items() if v}
    if len(full) < 4:
        return None
    labels = ["월", "화", "수", "목", "금", "토", "일"]
    avgs = {d: sum(v) / len(v) for d, v in full.items()}
    low_dow = min(avgs, key=avgs.get)
    high_dow = max(avgs, key=avgs.get)
    if avgs[high_dow] - avgs[low_dow] < 0.8:
        return None
    return {
        "kind": "weekday",
        "text": f"이번 주는 {labels[low_dow - 1]}요일이 가장 무겁고, {labels[high_dow - 1]}요일이 가장 가벼웠어요.",
        "detail": f"{labels[low_dow - 1]} {avgs[low_dow]:.1f} · {labels[high_dow - 1]} {avgs[high_dow]:.1f}",
        "strength": "관찰",
        "strength_score": (avgs[high_dow] - avgs[low_dow]) / 5.0,
    }


# ============================================================================
# v9.6: 다변량 경향 — 공통 버킷 헬퍼 + 7개 추가 관계
# ============================================================================

def _emotion_avgs(entries, sel):
    """sel(e)==True 인 entries의 부정 감정 평균 dict."""
    from collections import defaultdict
    acc = defaultdict(list)
    for e in entries:
        if not sel(e):
            continue
        emo = (e.get("label_result", {}) or {}).get("emotions", {}) or {}
        for k, v in emo.items():
            if k == "중립":
                continue
            acc[k].append(float(v))
    return {k: sum(v) / len(v) for k, v in acc.items() if v}


def _condition_of(e):
    sc = e.get("self_condition")
    return int(sc) if sc is not None else None


def _sleep_of(e):
    s = (e.get("context", {}) or {}).get("sleep_hours")
    try:
        return float(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _social_of(e):
    return (e.get("context", {}) or {}).get("social_today")


def _exercise_of(e):
    x = (e.get("context", {}) or {}).get("exercise_today")
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _sleep_trend_tendency(entries, *, threshold=1.0):
    """주중 수면이 뚜렷이 감소(또는 증가)하는 추세인지 + 그 흐름에서 신호."""
    pairs = []
    for e in entries:
        dt = _entry_dt(e)
        sh = _sleep_of(e)
        if dt is None or sh is None:
            continue
        pairs.append((dt, sh))
    if len(pairs) < 4:
        return None
    pairs.sort(key=lambda p: p[0])
    half = len(pairs) // 2
    early = sum(s for _, s in pairs[:half]) / half
    late = sum(s for _, s in pairs[half:]) / (len(pairs) - half)
    diff = late - early
    if abs(diff) < threshold:
        return None
    if diff < 0:
        text = f"한 주 동안 수면이 점점 줄어드는 흐름이었어요 (초반 {early:.1f}시간 → 후반 {late:.1f}시간)."
    else:
        text = f"한 주 동안 수면이 점점 늘어나는 흐름이었어요 (초반 {early:.1f}시간 → 후반 {late:.1f}시간)."
    return {
        "kind": "sleep_trend", "text": text,
        "detail": f"초반 {early:.1f}h · 후반 {late:.1f}h",
        "strength": "관찰", "strength_score": min(abs(diff) / 3.0, 0.6),
    }


def _sleep_emotion_tendency(entries, *, threshold=0.15):
    """수면 부족(<6h) vs 충분(>=7h) 날의 부정 감정 차이."""
    lo = _emotion_avgs(entries, lambda e: (_sleep_of(e) or 99) < 6)
    hi = _emotion_avgs(entries, lambda e: (_sleep_of(e) or 0) >= 7)
    best = None
    for k in set(lo) & set(hi):
        d = lo[k] - hi[k]
        if abs(d) >= threshold and (best is None or abs(d) > abs(best[1])):
            best = (k, d, lo[k], hi[k])
    if best is None:
        return None
    k, d, l, h = best
    verb = "더 자주" if d > 0 else "덜"
    return {
        "kind": "sleep_emotion",
        "text": f"잠이 부족했던 날엔 '{k}' 감정이 {verb} 올라왔던 것 같아요.",
        "detail": f"부족한 날 {l:.2f} vs 충분한 날 {h:.2f}",
        "strength": "관찰", "strength_score": abs(d),
    }


def _condition_behavior_tendency(entries, *, threshold=0.15):
    """컨디션 낮은 날(<=2) vs 좋은 날(>=4)의 회피미루기/동기저하 차이."""
    from collections import defaultdict
    lo, hi = defaultdict(list), defaultdict(list)
    for e in entries:
        sc = _condition_of(e)
        beh = (e.get("label_result", {}) or {}).get("behaviors", {}) or {}
        if sc is None or not beh:
            continue
        bucket = lo if sc <= 2 else (hi if sc >= 4 else None)
        if bucket is None:
            continue
        for k in BEHAVIORS_KO:
            bucket[k].append(float(beh.get(k, 0.0)))
    best = None
    for k in BEHAVIORS_KO:
        a, b = lo.get(k, []), hi.get(k, [])
        if not a or not b:
            continue
        la, hb = sum(a) / len(a), sum(b) / len(b)
        d = la - hb
        if abs(d) >= threshold and (best is None or abs(d) > abs(best[1])):
            best = (k, d, la, hb)
    if best is None:
        return None
    k, d, l, h = best
    verb = "더 자주" if d > 0 else "덜"
    return {
        "kind": "condition_behavior",
        "text": f"컨디션이 낮았던 날엔 '{k}' 신호가 {verb} 보였어요.",
        "detail": f"낮은 날 {l:.2f} vs 좋은 날 {h:.2f}",
        "strength": "관찰", "strength_score": abs(d),
    }


def _social_condition_tendency(entries, *, threshold=0.7):
    """사교 갈등 날 vs 좋음 날의 컨디션 차이."""
    conf = [c for e in entries if (c := _condition_of(e)) is not None and _social_of(e) == "갈등"]
    good = [c for e in entries if (c := _condition_of(e)) is not None and _social_of(e) == "좋음"]
    if not conf or not good:
        return None
    ca, ga = sum(conf) / len(conf), sum(good) / len(good)
    if abs(ga - ca) < threshold:
        return None
    return {
        "kind": "social_condition",
        "text": f"사람과 갈등이 있던 날엔 컨디션이 더 낮았던 편이에요 (갈등 {ca:.1f} vs 좋았던 날 {ga:.1f}).",
        "detail": f"갈등 {ca:.1f} · 좋음 {ga:.1f}",
        "strength": "관찰", "strength_score": min((ga - ca) / 5.0, 0.6),
    }


def _social_emotion_tendency(entries, *, threshold=0.15):
    """사교 갈등 날 vs 그 외 날의 부정 감정 차이."""
    conf = _emotion_avgs(entries, lambda e: _social_of(e) == "갈등")
    rest = _emotion_avgs(entries, lambda e: _social_of(e) != "갈등")
    best = None
    for k in set(conf) & set(rest):
        d = conf[k] - rest[k]
        if d >= threshold and (best is None or d > best[1]):
            best = (k, d, conf[k], rest[k])
    if best is None:
        return None
    k, d, c, r = best
    return {
        "kind": "social_emotion",
        "text": f"사람과의 일로 마음이 쓰였던 날엔 '{k}' 감정이 더 자주 보였어요.",
        "detail": f"갈등 날 {c:.2f} vs 그 외 {r:.2f}",
        "strength": "관찰", "strength_score": abs(d),
    }


def _exercise_condition_tendency(entries, *, threshold=0.7):
    """운동한 날(>=0.5h) vs 안 한 날의 컨디션 차이."""
    moved = [c for e in entries if (c := _condition_of(e)) is not None and (_exercise_of(e) or 0) >= 0.5]
    still = [c for e in entries if (c := _condition_of(e)) is not None and (_exercise_of(e) or 0) < 0.5]
    if not moved or not still:
        return None
    ma, sa = sum(moved) / len(moved), sum(still) / len(still)
    if abs(ma - sa) < threshold:
        return None
    if ma > sa:
        text = f"몸을 움직인 날엔 컨디션이 더 좋았던 편이에요 (운동한 날 {ma:.1f} vs 안 한 날 {sa:.1f})."
    else:
        text = f"이번 주는 운동 여부와 컨디션이 함께 가진 않았어요 (운동한 날 {ma:.1f} vs 안 한 날 {sa:.1f})."
    return {
        "kind": "exercise_condition", "text": text,
        "detail": f"운동 {ma:.1f} · 비운동 {sa:.1f}",
        "strength": "관찰", "strength_score": min(abs(ma - sa) / 5.0, 0.55),
    }


def _context_expression_tendency(entries):
    """힘든 맥락(수면<6 또는 컨디션<=2)인 날 자주 나온 표현(evidence_span)."""
    from collections import Counter
    counter = Counter()
    for e in entries:
        hard = (_sleep_of(e) or 99) < 6 or (_condition_of(e) or 5) <= 2
        if not hard:
            continue
        span = ((e.get("label_result", {}) or {}).get("evidence_span") or "").strip()
        if 3 <= len(span) <= 12:
            counter[span] += 1
    if not counter:
        return None
    span, cnt = counter.most_common(1)[0]
    if cnt < 2:
        return None
    return {
        "kind": "context_expression",
        "text": f"수면이 부족하거나 컨디션이 낮았던 날엔 '{span}' 같은 표현이 자주 보였어요.",
        "detail": f"{cnt}회",
        "strength": "관찰", "strength_score": 0.2 + 0.05 * cnt,
    }


def build_tendencies(entries: Sequence[dict[str, Any]]) -> list[dict]:
    """조건부 경향 관찰 — 다양한 변수 관계를 강도순으로 최대 5개.

    v9.6: 단일 변수(수면↔패턴)에서 다변량 관계로 대폭 확장.
    수면·컨디션·사교·운동·요일 × 패턴·행동·감정·표현(evidence)의 상관을
    모두 살펴, 통계적으로 가장 두드러진 것부터 자연어로.
    """
    candidates: list[dict] = []
    for fn in (
        _sleep_trend_tendency,        # 수면 추세(감소/증가) ↔ 신호·표현
        _sleep_pattern_tendency,      # 수면 부족 ↔ 인지 패턴
        _sleep_emotion_tendency,      # 수면 부족 ↔ 감정
        _condition_pattern_tendency,  # 컨디션 ↔ 인지 패턴
        _condition_behavior_tendency, # 컨디션 ↔ 회피·동기
        _social_condition_tendency,   # 사교 갈등 ↔ 컨디션
        _social_emotion_tendency,     # 사교 갈등 ↔ 감정
        _exercise_condition_tendency, # 운동 ↔ 컨디션
        _context_expression_tendency, # 힘든 맥락 ↔ 자주 나온 표현
        _weekday_tendency,            # 요일별 컨디션 기복
    ):
        card = fn(entries)
        if card:
            candidates.append(card)
    # 강도(strength_score) 높은 순, 같은 kind 중복 제거
    candidates.sort(key=lambda c: c.get("strength_score", 0.0), reverse=True)
    seen: set[str] = set()
    out: list[dict] = []
    for c in candidates:
        if c["kind"] in seen:
            continue
        seen.add(c["kind"])
        # v9.6: 강도에 따른 관찰 신뢰도 라벨 (사용자에게 과신 인상 방지)
        score = c.get("strength_score", 0.0)
        if score >= 0.3:
            c["strength"] = "뚜렷한 관찰"
        elif score >= 0.15:
            c["strength"] = "관찰"
        else:
            c["strength"] = "약한 관찰"
        c.pop("strength_score", None)  # 내부 정렬용 — 응답엔 불필요
        out.append(c)
    return out[:5]


# ============================================================================
# 3. 다음 주 초점 (적응) + 4. 개인화 노트
# ============================================================================

def _dominant_signal_category(entries: Sequence[dict[str, Any]]) -> tuple[str | None, str]:
    """이번 주 가장 자주 강하게 보인 신호 → 드릴 카테고리 매핑."""
    counter: Counter[str] = Counter()
    for e in entries:
        lr = e.get("label_result", {}) or {}
        signals: dict[str, float] = {}
        signals.update(lr.get("patterns", {}) or {})
        signals.update(lr.get("behaviors", {}) or {})
        if not signals:
            continue
        top, val = max(signals.items(), key=lambda kv: kv[1])
        if val >= 0.35:
            counter[top] += 1
    if not counter:
        return None, ""
    top_signal, _ = counter.most_common(1)[0]
    return _SIGNAL_TO_CATEGORY.get(top_signal), top_signal


def build_next_week_focus(
    entries: Sequence[dict[str, Any]],
    user_id: str,
    *,
    state_key: str,
    db_path=None,
) -> dict:
    """다음 주 추천 초점 — 이번 주 dominant 신호 + 개인화 프로파일 결합.

    우선순위:
      1. 상태가 '소진기/낮은 에너지' → grounding/self_compassion 우선 (진정 먼저, CBT/ACT 표준)
      2. 이번 주 dominant 신호의 카테고리
      3. 지금까지 가장 잘 맞은 카테고리 (개인화 학습 결과)
      4. 기본: grounding
    """
    # 1. 상태 기반 안전 우선
    if state_key in ("fatigue", "low"):
        cat = "grounding"
        reason = "한 주가 무거웠던 만큼, 다음 주엔 마음을 먼저 가라앉히는 연습이 도움이 될 수 있어요."
        source = "state"
    elif state_key == "turbulent":
        cat = "self_compassion"
        reason = "감정이 자주 올라온 한 주였어요. 자신에게 너그러운 연습부터 권해드려요."
        source = "state"
    else:
        cat, top_signal = _dominant_signal_category(entries)
        if cat:
            label = CATEGORY_LABEL_KO.get(cat, cat)
            reason = f"이번 주 '{top_signal}' 신호가 가장 자주 보여서, '{label}' 방향을 이어가보면 좋겠어요."
            source = "weekly_signal"
        else:
            top_cat = personalization.top_helpful_category(user_id, db_path=db_path)
            if top_cat:
                cat = top_cat["category"]
                reason = f"지금까지 '{top_cat['label_ko']}' 드릴이 가장 잘 맞으셨어요. 다음 주에도 우선 권해드릴게요."
                source = "personalization"
            else:
                cat = "grounding"
                reason = "특별히 두드러진 신호가 없던 한 주예요. 가볍게 마음을 살피는 연습으로 시작해요."
                source = "default"
    return {
        "category": cat,
        "label_ko": CATEGORY_LABEL_KO.get(cat, cat),
        "reason": reason,
        "source": source,
    }


def build_personalization_note(user_id: str, *, db_path=None) -> dict | None:
    """지금까지 학습된 선호 — 사용자 노출용 1문장 (없으면 None)."""
    prof = personalization.get_profile(user_id, db_path=db_path)
    if not prof["is_learning_active"]:
        return None
    top = personalization.top_helpful_category(user_id, db_path=db_path)
    if not top:
        return {
            "text": "아직 어떤 드릴이 가장 잘 맞는지 데이터를 모으고 있어요.",
            "is_active": True,
            "top_category": None,
        }
    return {
        "text": f"지금까지 '{top['label_ko']}' 계열 드릴이 가장 도움이 되셨어요 "
                f"({top['n_helpful']}회 도움됨 / {top['n_offered']}회 추천).",
        "is_active": True,
        "top_category": top["category"],
        "top_category_label": top["label_ko"],
    }


# ============================================================================
# 통합
# ============================================================================

def build_weekly_coaching(
    *,
    entries: Sequence[dict[str, Any]],
    user_id: str,
    db_path=None,
) -> dict:
    """주간 개인화 코칭 블록 전체."""
    state = infer_state(entries)
    tendencies = build_tendencies(entries)
    focus = build_next_week_focus(entries, user_id, state_key=state["key"], db_path=db_path)
    note = build_personalization_note(user_id, db_path=db_path)
    insufficient = state["key"] == "observing"
    return {
        "state": state,
        "tendencies": tendencies,
        "tendencies_message": (
            "경향을 읽기엔 아직 기록이 적어요. 며칠 더 모이면 보여드릴게요."
            if (insufficient and not tendencies) else None
        ),
        "next_week_focus": focus,
        "personalization_note": note,
        "insufficient": insufficient,
    }
