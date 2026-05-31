# 출처: CLAUDE.md §6, §4.3
"""라우팅 5단계 + 약신호 분기.

S005 ("공부해야 하는데 일어나지 못함") = 당위진술(인지) + 회피미루기(행동) 동시.
회피 라우팅이 인지보다 우선 — v7 설계 핵심 원칙.
"""
from __future__ import annotations

import random
from typing import Any

from app.core import drill_catalog
from app.core.ask_user import build_ask_drill_offer, build_ask_user, build_skip
from app.core.crisis_card import build_crisis_card
from app.core.positive_card import build_positive_card
from app.schemas.common import (
    BEHAVIORS_KO,
    CategoryEn,
    EMOTIONS_KO,
    PATTERNS_KO,
    RecommendType,
    SocialToday,
)


# ============================================================================
# 점수 계산 보조
# ============================================================================

def _max_score(scores: dict[str, float]) -> tuple[str, float]:
    if not scores:
        return "", 0.0
    name, val = max(scores.items(), key=lambda kv: kv[1])
    return name, float(val)


def _context_affinity_keys(context: dict[str, Any]) -> set[str]:
    """현재 맥락이 활성화하는 affinity 키들 (드릴 가산점 매칭용).

    v9.7: 이진 임계 → 단계적(severity band) + 운동·긍정사교 신호 추가.
    드릴의 context_affinity 키와 교집합으로 매칭되므로, 기존 키
    (self_condition_low / sleep_short / social_stressful)는 유지하고
    세분 키를 '추가'만 한다 (기존 드릴 호환).
    """
    keys: set[str] = set()
    sc = context.get("self_condition", 3)
    sc = int(sc) if sc is not None else 3
    if sc <= 2:
        keys.add("self_condition_low")
    if sc <= 1:
        keys.add("self_condition_very_low")   # 매우 낮음 — 더 부드러운 드릴 우선
    if sc >= 4:
        keys.add("self_condition_high")        # 양호 — 유지/도전형 가능

    sh = context.get("sleep_hours")
    if sh is not None:
        sh = float(sh)
        if sh < 6:
            keys.add("sleep_short")
        if sh < 4.5:
            keys.add("sleep_very_short")        # 심한 수면부족
    soc = context.get("social_today")
    if soc in (SocialToday.CONFLICT.value, "갈등"):
        keys.add("social_stressful")
    if soc in ("좋음", "good"):
        keys.add("social_positive")

    ex = context.get("exercise_today")
    if ex is not None:
        try:
            if float(ex) >= 0.5:
                keys.add("exercised")           # 운동함 — 활성화 흐름
            else:
                keys.add("sedentary")
        except (TypeError, ValueError):
            pass
    return keys


# v9.5: "나의 발견" 키워드 → 카테고리 affinity 매핑.
# 사용자가 적은 발견에 자주 등장하는 키워드로 다음 추천 가중치 조정.
_DISCOVERY_KEYWORD_AFFINITY: dict[str, set[str]] = {
    # 수면 관련 키워드 → sleep_circadian 가산
    "sleep_circadian": {"잠", "수면", "잠들", "수면이", "잠이"},
    # 운동·활동 키워드 → behavioral_activation 가산
    "behavioral_activation": {"산책", "움직", "운동", "걷", "활동"},
    # 자기 자비 키워드 → self_compassion 가산
    "self_compassion": {"감사", "고마", "긍정", "괜찮", "위로", "다행"},
    # 그라운딩 키워드 → grounding 가산
    "grounding": {"호흡", "숨", "느낌", "감각", "몸"},
    # 인지 재구성 키워드 → cognitive_restructuring 가산
    "cognitive_restructuring": {"생각", "관점", "다르게", "사실은", "증거"},
    # 습관 키워드 → habit_design 가산
    "habit_design": {"습관", "루틴", "매일", "꾸준", "작은"},
}


def _user_discovery_affinity_keys(user_discoveries: list[str] | None) -> set[str]:
    """v9.5: 사용자가 적은 "나의 발견" 텍스트에서 키워드 추출 → 카테고리 affinity 키 생성.

    예시:
        발견 1: "잠을 충분히 잔 날은 마음이 가벼워요"
        발견 2: "감사한 일 한 가지 적는 게 도움이 돼요"
        → returns {"category_sleep_circadian", "category_self_compassion"}

    추천기 _bonus()에서 이 키들로 드릴 가산점 매칭.
    """
    if not user_discoveries:
        return set()
    joined = " ".join(user_discoveries).lower()
    keys: set[str] = set()
    for category, keywords in _DISCOVERY_KEYWORD_AFFINITY.items():
        if any(kw in joined for kw in keywords):
            keys.add(f"category_{category}")
    return keys


# ============================================================================
# 드릴 선택 — 카테고리·trigger·context_affinity 가중치
# ============================================================================

def _bonus(drill: dict[str, Any], context: dict[str, Any]) -> float:
    """맥락별 보너스 — 명세서 §6.1 + v9.7 단계적 강화.

    이진 임계 대신 수면·컨디션을 단계(severity band)로 평가해 더 적합한
    드릴을 고른다. 운동 여부와 사교(긍정/갈등)도 약하게 반영.
    상한을 둬 임상 라우팅(카테고리 결정)을 뒤집지 않고 '같은 카테고리 내
    미세 조정 + 약신호 fallback'에서만 영향.
    """
    bonus = 0.0
    cat = drill.get("category")
    duration = int(drill.get("duration_min", 5))
    sleep_h = context.get("sleep_hours")
    self_cond = context.get("self_condition", 3)
    self_cond = int(self_cond) if self_cond is not None else 3
    social = context.get("social_today")
    exercise = context.get("exercise_today")

    # 수면 — 단계적 가산 (심할수록 강하게)
    if cat == "sleep_circadian" and sleep_h is not None:
        sh = float(sleep_h)
        if sh < 4.5:
            bonus += 0.35
        elif sh < 5:
            bonus += 0.30
        elif sh < 6:
            bonus += 0.18
        elif sh < 7:
            bonus += 0.08

    # 컨디션 — grounding/self_compassion 단계적
    if cat == "grounding":
        if self_cond <= 1:
            bonus += 0.28
        elif self_cond <= 2:
            bonus += 0.20
        elif self_cond == 3:
            bonus += 0.06
    if cat == "self_compassion" and self_cond <= 2:
        bonus += 0.12

    # 짧은 행동 드릴 — 컨디션 낮을수록 진입장벽 보정 가산
    if cat in ("behavioral_activation", "habit_design") and duration <= 3:
        bonus += 0.10
        if self_cond <= 2 and duration <= 2:
            bonus += 0.06   # 매우 짧은 드릴 추가 가산

    # 사교 갈등 → 자기자비/그라운딩
    if social in (SocialToday.CONFLICT.value, "갈등"):
        if cat == "self_compassion":
            bonus += 0.20
        elif cat == "grounding":
            bonus += 0.08

    # 운동 안 함 + 무기력(우울행동) → behavioral_activation 약가산
    if cat == "behavioral_activation" and exercise is not None:
        try:
            if float(exercise) < 0.5:
                bonus += 0.06
        except (TypeError, ValueError):
            pass

    # 상한 — 임상 라우팅 보호 (카테고리 선택을 뒤집지 않도록)
    return min(bonus, 0.45)


def _score_drill(
    drill: dict[str, Any],
    *,
    patterns: dict[str, float],
    behaviors: dict[str, float],
    emotions: dict[str, float],
    affinity_keys: set[str],
    recent_drill_ids: list[int | str],
    rejected_drill_ids: list[int | str] | None = None,
    context: dict[str, Any] | None = None,
    pref_bonus: dict[str, float] | None = None,
) -> float:
    """드릴 1개 점수. 같은 카테고리 내 보조 선택용. §6.1 + bonus.

    v9.6: pref_bonus — 개인화 엔진(UCB1)이 산출한 카테고리별 가산점.
    임상 라우팅이 카테고리를 정한 뒤이므로, 이 항은 "같은 카테고리 안에서
    어떤 드릴을 고를지" + 약신호 fallback 시 카테고리 선택을 부드럽게 조정.
    """
    score = 0.0
    drill_patterns = drill.get("patterns", {}) or {}
    for name, meta in drill_patterns.items():
        weight = meta.get("weight", 0.0) if isinstance(meta, dict) else float(meta)
        score += 0.35 * weight * patterns.get(name, 0.0)
    drill_behaviors = drill.get("behaviors", {}) or {}
    for name, meta in drill_behaviors.items():
        weight = meta.get("weight", 0.0) if isinstance(meta, dict) else float(meta)
        score += 0.40 * weight * behaviors.get(name, 0.0)
    drill_emotions = drill.get("emotions", {}) or {}
    for name, weight in drill_emotions.items():
        score += 0.10 * float(weight) * emotions.get(name, 0.0)
    affinity = drill.get("context_affinity", {}) or {}
    matched_keys = set(affinity.keys()) & affinity_keys
    if matched_keys:
        avg = sum(
            (affinity[k].get("weight", 0.0) if isinstance(affinity[k], dict) else 0.0)
            for k in matched_keys
        ) / max(len(matched_keys), 1)
        score += 0.25 * avg

    # v9.5: "나의 발견" 키워드 매칭 — 같은 카테고리 드릴에 가산 (맞춤형 컨셉).
    drill_cat = drill.get("category", "")
    if f"category_{drill_cat}" in affinity_keys:
        score += 0.15  # 사용자 발견과 일치 카테고리 가산

    if context is not None:
        score += _bonus(drill, context)

    # v9.6: 개인화 가산점 (UCB1) — 카테고리별 학습된 선호.
    if pref_bonus:
        score += float(pref_bonus.get(drill_cat, 0.0))

    if drill.get("id") in recent_drill_ids:
        score -= 1.0
    if rejected_drill_ids and drill.get("id") in rejected_drill_ids:
        score -= 2.0
    return score


def _pick_drill(
    category: str,
    *,
    patterns: dict[str, float],
    behaviors: dict[str, float],
    emotions: dict[str, float],
    affinity_keys: set[str],
    recent_drill_ids: list[str],
    rng: random.Random,
    rejected_drill_ids: list[str] | None = None,
    context: dict[str, Any] | None = None,
    pref_bonus: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    candidates = drill_catalog.drills_by_category(category)
    if not candidates:
        return None
    # 최근 + rejected 둘 다 제외
    blocked = set(recent_drill_ids) | set(rejected_drill_ids or [])
    fresh = [d for d in candidates if d.get("id") not in blocked]
    pool = fresh or candidates  # 전부 막힌 경우 fallback
    scored = [
        (
            _score_drill(
                d,
                patterns=patterns,
                behaviors=behaviors,
                emotions=emotions,
                affinity_keys=affinity_keys,
                recent_drill_ids=recent_drill_ids,
                rejected_drill_ids=rejected_drill_ids,
                context=context,
                pref_bonus=pref_bonus,
            ),
            d,
        )
        for d in pool
    ]
    scored.sort(key=lambda kv: kv[0], reverse=True)
    if not scored:
        return None
    top_score = scored[0][0]
    ties = [d for s, d in scored if abs(s - top_score) < 1e-6]
    return rng.choice(ties)


# ============================================================================
# 카피 빌더
# ============================================================================

def _duration_phrase(duration_min: int) -> str:
    if duration_min <= 1:
        return "1분이면 충분해요."
    if duration_min <= 3:
        return f"{duration_min}분이면 돼요."
    return f"{duration_min}분 정도 걸려요."


def _build_copy(
    drill: dict[str, Any],
    evidence_span: str | None,
    confidence: float = 1.0,
    tone: str = "neutral",
) -> dict[str, str | None]:
    """v9.5: confidence 톤 조정 + 짧은 입력(1~3자) 카피 자연스럽게.

    - confidence < 0.5 시 단정형 → 추측형
    - evidence_span이 1~3자 (예: "ㅠ", "다 망함") 시 인용 X — 자연스러운 문장
    - v9.6: tone="positive" (안정적인 날) → 축하·유지 톤 카피
    """
    # v9.6: 안정적인 날의 긍정 유지형 카피
    if tone == "positive":
        return {
            "line1": "오늘은 신호가 잔잔한 하루네요.",
            "line2": f"좋은 흐름을 이어가실 〈{drill.get('title')}〉 어떠세요?",
            "line3": _duration_phrase(int(drill.get("duration_min", 5))),
        }

    # v9.5: evidence_span 인용 규칙
    # - 1~3자: 너무 짧음 → 인용 X, 마음 알아주는 카피
    # - 4~12자: 적정 → 인용
    # - 13자 이상: 너무 김 → 인용 X, 일반 카피
    ev = (evidence_span or "").strip()
    ev_len = len(ev)
    is_short = 0 < ev_len <= 3
    is_quotable = 4 <= ev_len <= 12

    if is_quotable:
        if confidence < 0.5:
            line1 = f"방금 쓰신 글에서 \'{ev}\' 같은 표현이 있는 듯하네요."
        else:
            line1 = f"방금 쓰신 글에서 \'{ev}\'가 보이네요."
    elif is_short or ev_len > 12:
        # 짧거나 너무 긴 evidence — 인용 X
        if confidence < 0.5:
            line1 = "지금 마음이 잔잔하지만은 않으신 것 같아요."
        else:
            line1 = "지금 마음에 무언가 있으신 것 같아요."
    else:
        # evidence_span 없음
        line1 = None

    if confidence < 0.5:
        line2 = f"잘 맞을지는 모르지만, 〈{drill.get('title')}〉도 한 번 보실래요?"
    else:
        line2 = f"이런 때는 〈{drill.get('title')}〉이 어떠세요?"
    line3 = _duration_phrase(int(drill.get("duration_min", 5)))
    return {"line1": line1, "line2": line2, "line3": line3}


def _reason_text(step: str, max_pattern: tuple[str, float], max_behavior: tuple[str, float]) -> str:
    if step.startswith("step1"):
        return "위기 신호 감지 — 일반 드릴 차단"
    if step.startswith("step2"):
        return f"인지 {max_pattern[0]} 강함 ({max_pattern[1]:.2f})"
    if step.startswith("step3"):
        return f"행동 회피미루기 강함 ({max_behavior[1]:.2f})"
    if step.startswith("step4"):
        return f"행동 동기저하 강함 ({max_behavior[1]:.2f})"
    if step.startswith("step5"):
        return "신호 약함 — 맥락 기반 보조 추천"
    return "fallback — 점수 공식 기반"


# ============================================================================
# v9.6: "왜 이 드릴인지" 설명 엔진 (설명가능 추천 — GPT 단독 대비 차별점)
# ============================================================================

def _context_factor(context: dict[str, Any] | None) -> dict | None:
    """현재 맥락에서 가장 두드러진 요인 1개 → 사용자 노출용 구절."""
    if not context:
        return None
    sc = int(context.get("self_condition", 3))
    sleep_h = context.get("sleep_hours")
    social = context.get("social_today")
    # 심각도 순 (가장 강한 요인 1개만)
    if sleep_h is not None and float(sleep_h) < 5:
        return {"kind": "context", "label": "수면 부족",
                "detail": f"{float(sleep_h):.0f}시간", "phrase": "어젯밤 잠이 부족해서"}
    if sc <= 2:
        return {"kind": "context", "label": "낮은 컨디션",
                "detail": f"{sc}단계", "phrase": "오늘 컨디션이 낮은 편이라"}
    if social in ("갈등",):
        return {"kind": "context", "label": "사교 갈등",
                "detail": "갈등", "phrase": "사람과의 일로 마음이 좀 쓰여서"}
    if sleep_h is not None and float(sleep_h) < 6:
        return {"kind": "context", "label": "수면 약간 부족",
                "detail": f"{float(sleep_h):.0f}시간", "phrase": "잠이 살짝 부족해서"}
    return None


def _intensity_word(v: float) -> str:
    """0~1 점수를 사용자용 자연어 강도로. (사용자는 '0.75'를 이해 못 함)"""
    if v >= 0.7:
        return "자주"
    if v >= 0.5:
        return "여러 번"
    if v >= 0.3:
        return "조금"
    return "약간"


def _signal_factor(
    patterns: dict[str, float],
    behaviors: dict[str, float],
    emotions: dict[str, float],
) -> dict | None:
    """가장 강한 신호 1개 → 사용자 노출용 구절.

    v9.7: detail을 원점수(0.75) 대신 사용자가 이해할 자연어 강도로.
    """
    cands: list[tuple[float, str, str]] = []
    for name, v in patterns.items():
        cands.append((float(v), name, "pattern"))
    for name, v in behaviors.items():
        cands.append((float(v), name, "behavior"))
    neg = {k: v for k, v in emotions.items() if k != "중립"}
    for name, v in neg.items():
        cands.append((float(v), name, "emotion"))
    if not cands:
        return None
    val, name, kind = max(cands, key=lambda t: t[0])
    if val < 0.3:
        return None
    word = _intensity_word(val)
    from app.core.labels import friendly_label
    friendly = friendly_label(name)
    if kind == "emotion":
        phrase = f"'{name}' 감정이 {word} 올라와서"
    elif kind == "behavior":
        phrase = f"'{name}' 신호가 {word} 보여서"
    else:
        phrase = f"'{name}' 생각이 {word} 보여서"
    # detail: 사용자 표시는 자연어, 원점수는 score_raw로 분리 (디버그/분석용)
    return {"kind": kind, "label": name, "friendly": friendly, "detail": word,
            "score_raw": round(val, 2), "phrase": phrase}


# v9.7: 카테고리별 "이 드릴이 당신에게 줄 것"(효용성) + "근거 한 줄"(신뢰성/차별성).
# 사용자가 받는 화면에 '왜 골랐는지' 뿐 아니라 '하면 뭐가 좋아지는지'를 보여줘
# 납득도를 높인다. 모두 학술 근거에 기반한 보수적 표현(효과 보장 아님).
_CATEGORY_BENEFIT: dict[str, str] = {
    "cognitive_restructuring": "꼬리를 무는 생각에서 한 걸음 떨어져 보는 데 도움이 돼요.",
    "behavioral_activation": "아주 작은 행동 하나로 무거운 마음에 물꼬를 트는 연습이에요.",
    "habit_design": "부담을 최소로 줄여, 시작 자체가 쉬워지도록 설계된 연습이에요.",
    "grounding": "지금 이 순간으로 주의를 데려와 마음을 가라앉히는 데 도움이 돼요.",
    "self_compassion": "자신을 몰아세우는 대신, 잠시 다정하게 대해보는 연습이에요.",
    "sleep_circadian": "수면 리듬을 다시 잡는 데 도움이 되는 작은 습관이에요.",
}
_CATEGORY_MECHANISM: dict[str, str] = {
    "cognitive_restructuring": "인지행동치료(CBT)의 생각 재구성 기법에 기반해요.",
    "behavioral_activation": "우울 개입에서 효과가 검증된 행동활성화(BA) 원리예요.",
    "habit_design": "행동설계(Tiny Habits)·실행의도 연구에 기반해요.",
    "grounding": "불안·각성을 낮추는 그라운딩/호흡 기법에 기반해요.",
    "self_compassion": "자기자비(self-compassion) 연구에 기반해요.",
    "sleep_circadian": "불면 인지행동치료(CBT-I) 원리에 기반해요.",
}


def _build_why(
    *,
    patterns: dict[str, float],
    behaviors: dict[str, float],
    emotions: dict[str, float],
    context: dict[str, Any] | None,
    evidence_span: str | None,
    tone: str = "neutral",
    category: str | None = None,
) -> dict[str, Any]:
    """추천 이유를 사용자 친화 자연어 한 줄 + 근거 factor 목록으로.

    예: "어젯밤 잠이 부족했고, '미래예측' 생각이 자주 보여서 이 드릴을 골랐어요."
    factors는 FE가 칩/아이콘으로 보여줄 수 있게 구조화해 함께 반환.
    v9.7: expected_benefit(효용성) + mechanism(신뢰성/차별성) 추가 반환.
    """
    factors: list[dict] = []
    ctx_f = _context_factor(context)
    sig_f = _signal_factor(patterns, behaviors, emotions)
    ev = (evidence_span or "").strip()
    ev_quotable = 4 <= len(ev) <= 12

    if ctx_f:
        factors.append(ctx_f)
    if sig_f:
        factors.append(sig_f)
    benefit = _CATEGORY_BENEFIT.get(category or "", "")
    mechanism = _CATEGORY_MECHANISM.get(category or "", "")

    # v9.7: evidence_span을 "원문 인용 + 왜 이게 근거인지"로 강화.
    # 가장 강한 신호(sig_f)와 엮어, 인용문이 어떤 마음의 단서인지 설명.
    if ev_quotable:
        from app.core.labels import friendly_label
        ev_why = ""
        if sig_f:
            fr = sig_f.get("friendly") or friendly_label(sig_f["label"])
            if sig_f["kind"] == "emotion":
                ev_why = f"'{fr}'이 묻어나는 말이라서"
            else:
                ev_why = f"'{fr}'의 단서가 보이는 말이라서"
        factors.append({
            "kind": "evidence", "label": ev, "detail": None,
            "quote": ev,                       # 원문 인용 (화면에 그대로)
            "why_evidence": ev_why,            # 왜 이게 근거인지 (납득용)
            "phrase": f"방금 쓰신 '{ev}' 표현도 함께 보여서",
        })

    if tone == "positive":
        text = "오늘은 신호가 잔잔한 편이라, 좋은 흐름을 이어가실 가벼운 연습으로 골랐어요."
        return {"text": text, "factors": factors, "tone": "positive",
                "expected_benefit": benefit, "mechanism": mechanism}

    phrases = [f["phrase"] for f in factors if f.get("phrase")]
    if not phrases:
        text = "지금 마음 상태에 맞춰 이 드릴을 골랐어요."
    elif len(phrases) == 1:
        text = f"{phrases[0]} 이 드릴을 골랐어요."
    else:
        text = f"{', '.join(phrases[:-1])}, {phrases[-1]} 이 드릴을 골랐어요."
    return {"text": text, "factors": factors, "tone": tone,
            "expected_benefit": benefit, "mechanism": mechanism}


def _build_drill_response(
    drill: dict[str, Any],
    *,
    evidence_span: str | None,
    reason: str,
    confidence: float = 1.0,
    patterns: dict[str, float] | None = None,
    behaviors: dict[str, float] | None = None,
    emotions: dict[str, float] | None = None,
    context: dict[str, Any] | None = None,
    tone: str = "neutral",
) -> dict[str, Any]:
    """v9.4.3: confidence 전달 → 카피 톤 자동 조정.

    v9.6: why(설명가능 추천) + tone + drill.id 를 함께 반환.
    - why.text: 사용자에게 보여줄 "왜 이 드릴" 한 줄.
    - why.factors: FE가 칩/아이콘으로 쓸 구조화 근거.
    - tone: "neutral" | "positive" (안정적인 날의 유지형 드릴).
    """
    why = _build_why(
        patterns=patterns or {},
        behaviors=behaviors or {},
        emotions=emotions or {},
        context=context,
        evidence_span=evidence_span,
        tone=tone,
        category=drill.get("category"),
    )
    return {
        "type": RecommendType.DRILL.value,
        "tone": tone,
        "drill": {
            "id": drill.get("id"),
            "name": drill.get("title"),
            "category": drill.get("category"),
            "duration_min": int(drill.get("duration_min", 5)),
            "instruction": drill.get("instruction", ""),
            "citation": drill.get("source_short") or drill.get("source_primary", ""),
        },
        "copy": _build_copy(drill, evidence_span, confidence=confidence, tone=tone),
        "why": why,            # v9.6: 설명가능 추천
        "reason": reason,      # 내부/디버그용 (짧은 사유)
    }


# ============================================================================
# 라우팅 본체 — 5단계 + 약신호 분기
# ============================================================================

def recommend(
    *,
    label_result: dict[str, Any],
    context: dict[str, Any],
    user_id: str,
    recent_drill_ids: list[int | str] | None = None,
    rejected_drill_ids: list[int | str] | None = None,
    user_discoveries: list[str] | None = None,
    pref_bonus: dict[str, float] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """5단계 라우팅 — §6 정확히. rejected는 누적 학습 신호.

    v9.5: user_discoveries 추가 — 사용자가 적은 "나의 발견" 텍스트로
    카테고리 affinity 가산 (맞춤형 추천 컨셉).
    전달 안 되면 자동으로 insights_store에서 최근 5개 조회.

    v9.6: pref_bonus 추가 — 개인화 엔진(UCB1) 카테고리별 가산점.
    API 레이어가 personalization.bonus_map(user_id)로 채워 전달 (코어는 순수 유지).
    """
    rng = rng or random.Random()
    recent = recent_drill_ids or []
    rejected = rejected_drill_ids or []

    # rejected 자동 조회 (전달받지 못한 경우)
    if not rejected and user_id:
        try:
            from app.core.insights_store import rejected_drill_ids as _rd
            rejected = _rd(user_id)
        except Exception:  # noqa: BLE001 (best-effort)
            rejected = []

    # v9.5: user_discoveries 자동 조회 (전달받지 못한 경우)
    user_disc = user_discoveries
    if user_disc is None and user_id:
        try:
            from app.core.insights_store import get_recent_user_discoveries as _gd
            user_disc = _gd(user_id, limit=5)
        except Exception:  # noqa: BLE001 (best-effort)
            user_disc = []
    user_disc = user_disc or []

    # Step 1. 위기
    if label_result.get("crisis_detected"):
        return build_crisis_card()

    patterns = {k: float(label_result.get("patterns", {}).get(k, 0.0)) for k in PATTERNS_KO}
    behaviors = {k: float(label_result.get("behaviors", {}).get(k, 0.0)) for k in BEHAVIORS_KO}
    emotions = {k: float(label_result.get("emotions", {}).get(k, 0.0)) for k in EMOTIONS_KO}
    evidence_span = label_result.get("evidence_span") or None
    confidence = float(label_result.get("confidence", 0.5))

    max_pattern = _max_score(patterns)
    max_behavior = _max_score(behaviors)
    affinity_keys = _context_affinity_keys(context)
    # v9.5: 사용자 발견 기반 affinity 병합
    affinity_keys = affinity_keys | _user_discovery_affinity_keys(user_disc)

    # Step 2. 인지 max >= 0.4 AND 행동 max < 0.5
    if max_pattern[1] >= 0.4 and max_behavior[1] < 0.5:
        drill = _pick_drill(
            CategoryEn.COGNITIVE_RESTRUCTURING.value,
            patterns=patterns,
            behaviors=behaviors,
            emotions=emotions,
            affinity_keys=affinity_keys,
            recent_drill_ids=recent,
            rng=rng, pref_bonus=pref_bonus,
            context=context,
            rejected_drill_ids=rejected,
        )
        if drill:
            return _build_drill_response(
                drill,
                evidence_span=evidence_span,
                confidence=confidence,
                patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                reason=_reason_text("step2", max_pattern, max_behavior),
            )

    # Step 3. 회피미루기 >= 0.5 (S005 우선순위)
    if behaviors.get("회피미루기", 0.0) >= 0.5:
        drill = _pick_drill(
            CategoryEn.BEHAVIORAL_ACTIVATION.value,
            patterns=patterns,
            behaviors=behaviors,
            emotions=emotions,
            affinity_keys=affinity_keys,
            recent_drill_ids=recent,
            rng=rng, pref_bonus=pref_bonus,
            context=context,
            rejected_drill_ids=rejected,
        )
        if drill:
            return _build_drill_response(
                drill,
                evidence_span=evidence_span,
                confidence=confidence,
                patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                reason=_reason_text("step3", max_pattern, ("회피미루기", behaviors["회피미루기"])),
            )

    # Step 4. 동기저하 >= 0.5
    if behaviors.get("동기저하", 0.0) >= 0.5:
        drill = _pick_drill(
            CategoryEn.HABIT_DESIGN.value,
            patterns=patterns,
            behaviors=behaviors,
            emotions=emotions,
            affinity_keys=affinity_keys,
            recent_drill_ids=recent,
            rng=rng, pref_bonus=pref_bonus,
            context=context,
            rejected_drill_ids=rejected,
        )
        if drill:
            return _build_drill_response(
                drill,
                evidence_span=evidence_span,
                confidence=confidence,
                patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                reason=_reason_text("step4", max_pattern, ("동기저하", behaviors["동기저하"])),
            )

    # Step 4.5 (v9.6 변경). 모든 신호 0.3~0.5 경계선.
    #   이전(v9.4.x): 사용자에게 객관식으로 물어봄(ask_user).
    #   변경: 항상 드릴 추천 정책 — 더 강한 후보의 카테고리로 바로 추천 (묻지 않음).
    all_signals = list(patterns.values()) + list(behaviors.values())
    top_signal = max(all_signals) if all_signals else 0.0
    if 0.3 <= top_signal < 0.5:
        if max_pattern[1] < 0.4 and max_behavior[1] < 0.5:
            ranked: list[tuple[float, str, str]] = []
            for name, score in patterns.items():
                if score >= 0.3:
                    ranked.append((score, name, "pattern"))
            for name, score in behaviors.items():
                if score >= 0.3:
                    ranked.append((score, name, "behavior"))
            ranked.sort(reverse=True)
            if ranked:
                _sc, top_name, kind = ranked[0]
                if kind == "pattern":
                    category = CategoryEn.COGNITIVE_RESTRUCTURING.value
                elif top_name == "회피미루기":
                    category = CategoryEn.BEHAVIORAL_ACTIVATION.value
                else:
                    category = CategoryEn.HABIT_DESIGN.value
                drill = _pick_drill(
                    category,
                    patterns=patterns, behaviors=behaviors, emotions=emotions,
                    affinity_keys=affinity_keys, recent_drill_ids=recent,
                    rng=rng, pref_bonus=pref_bonus, context=context,
                    rejected_drill_ids=rejected,
                )
                if drill:
                    return _build_drill_response(
                        drill,
                        evidence_span=evidence_span, confidence=confidence,
                        patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                        reason=f"경계선 신호 — 가장 강한 '{top_name}' 기준 추천",
                    )

    # Step 4.7 (v9.5 신규). 인지/행동은 약신호 (< 0.3) 인데 감정이 강할 때 (≥ 0.5).
    #
    # 배경: 분노/불안/우울이 0.6 인데 patterns 모두 0.0인 경우 — Step 5 약신호 분기에서
    # "받으실래요?" 묻는 게 어색함. CBT/ACT 표준: 강한 감정 → 그라운딩으로 진정 → 인지 작업.
    # 따라서 감정 강도 ≥ 0.5 시 grounding 카테고리 드릴 즉시 추천 (묻지 X).
    if all_signals and max(all_signals) < 0.3:
        # 부정 감정만 본다 (중립 제외)
        neg_emotions = {k: v for k, v in emotions.items() if k != "중립"}
        max_neg_emotion = max(neg_emotions.values()) if neg_emotions else 0.0
        if max_neg_emotion >= 0.5:
            dom_emotion = max(neg_emotions.items(), key=lambda kv: kv[1])[0]
            drill = _pick_drill(
                CategoryEn.GROUNDING.value,
                patterns=patterns, behaviors=behaviors, emotions=emotions,
                affinity_keys=affinity_keys, recent_drill_ids=recent,
                rejected_drill_ids=rejected, rng=rng, pref_bonus=pref_bonus, context=context,
            )
            if drill:
                return _build_drill_response(
                    drill,
                    evidence_span=evidence_span,
                    confidence=confidence,
                    patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                    reason=f"강한 감정 ({dom_emotion} {max_neg_emotion:.2f}) — grounding 진정",
                )

    # Step 5 (v9.6 변경). 모든 신호 < 0.3 — 약신호.
    #   이전(v9.4.4): "받으실래요?"(ask_drill_offer) 먼저 묻고, 양호하면 positive_card.
    #   변경: 항상 드릴 추천 정책.
    #     - 맥락이 안 좋으면(컨디션 낮음/수면 부족/갈등) → 그에 맞는 진정·돌봄 드릴 바로 추천.
    #     - 모두 양호하면 → tone="positive" 유지형 드릴(자기자비 계열) 추천 (positive_card 대체).
    #   crisis_card만 별도 type 유지. ask_user/positive_card/skip는 정상 흐름에서 더 이상 반환 X.
    if all_signals and max(all_signals) < 0.3:
        sc = int(context.get("self_condition", 3))
        sleep_h = context.get("sleep_hours")
        social = context.get("social_today")

        # 다중 매칭 후보 + 심각도 (높을수록 심함) → 가장 심한 맥락에 맞는 카테고리
        offers: list[tuple[float, str]] = []
        if sc <= 2:
            offers.append((1.0 if sc <= 1 else 0.5, CategoryEn.GROUNDING.value))
        if sleep_h is not None and float(sleep_h) < 5:
            sh = float(sleep_h)
            offers.append((1.0 if sh <= 3 else (0.6 if sh < 4 else 0.4), CategoryEn.SLEEP_CIRCADIAN.value))
        if social in (SocialToday.CONFLICT.value, "갈등"):
            offers.append((0.6, CategoryEn.SELF_COMPASSION.value))

        if offers:
            offers.sort(reverse=True)
            _sev, category = offers[0]
            drill = _pick_drill(
                category,
                patterns=patterns, behaviors=behaviors, emotions=emotions,
                affinity_keys=affinity_keys, recent_drill_ids=recent,
                rng=rng, pref_bonus=pref_bonus, context=context,
                rejected_drill_ids=rejected,
            )
            if drill:
                return _build_drill_response(
                    drill,
                    evidence_span=evidence_span, confidence=confidence,
                    patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                    reason=f"약신호 + 맥락({category}) 기반 돌봄 드릴",
                )

        # 모두 양호 → tone="positive" 유지형 드릴 (자기자비 → 없으면 가벼운 습관).
        for cat in (CategoryEn.SELF_COMPASSION.value, CategoryEn.HABIT_DESIGN.value,
                    CategoryEn.GROUNDING.value):
            drill = _pick_drill(
                cat,
                patterns=patterns, behaviors=behaviors, emotions=emotions,
                affinity_keys=affinity_keys, recent_drill_ids=recent,
                rng=rng, pref_bonus=pref_bonus, context=context,
                rejected_drill_ids=rejected,
            )
            if drill:
                return _build_drill_response(
                    drill,
                    evidence_span=evidence_span, confidence=confidence,
                    patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                    tone="positive",
                    reason=f"신호 약함 + 컨디션 양호 ({sc}) — 유지형 드릴",
                )

    # Step 6. fallback — 가장 높은 점수 카테고리 (이론상 드묾)
    candidate_categories = [c.value for c in CategoryEn]
    best = None
    best_score = -1.0
    for cat in candidate_categories:
        d = _pick_drill(
            cat,
            patterns=patterns,
            behaviors=behaviors,
            emotions=emotions,
            affinity_keys=affinity_keys,
            recent_drill_ids=recent,
            rng=rng, pref_bonus=pref_bonus,
            context=context,
            rejected_drill_ids=rejected,
        )
        if d is None:
            continue
        s = _score_drill(
            d,
            patterns=patterns,
            behaviors=behaviors,
            emotions=emotions,
            affinity_keys=affinity_keys,
            recent_drill_ids=recent,
            rejected_drill_ids=rejected,
            context=context,
        )
        if s > best_score:
            best_score = s
            best = d
    if best:
        return _build_drill_response(
            best,
            evidence_span=evidence_span,
            confidence=confidence,
            patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
            reason=_reason_text("fallback", max_pattern, max_behavior),
        )

    # v9.6 always-drill 보장: 위 모두 실패(거의 불가능 — 전 카테고리 차단 등)해도
    # 카탈로그에서 아무 드릴이나 반환. ask_user/skip로 빠지지 않음.
    any_drills = drill_catalog.get_drills()
    if any_drills:
        return _build_drill_response(
            rng.choice(any_drills),
            evidence_span=evidence_span,
            confidence=confidence,
            patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
            tone="positive",
            reason="fallback — 카탈로그 기본 드릴",
        )
    # 카탈로그 자체가 비었을 때만 (배포 사고) skip — 사용자에겐 부드러운 메시지.
    return build_skip("지금은 추천할 연습을 불러오지 못했어요. 오늘 기록은 잘 저장됐어요.")



# ============================================================================
# v9.4.3 §4.3 ask_user 후속 흐름
# ============================================================================

def recommend_after_ask_user(
    *,
    label_result: dict[str, Any],
    context: dict[str, Any],
    user_id: str,
    recent_drill_ids: list[int | str] | None = None,
    user_choice: str,
    chosen_candidate: str | None = None,
    offer_category: str | None = None,
    pref_bonus: dict[str, float] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """v9.4.3/4 §4.3: ask_user 응답 처리.

    user_choice 분기:
    - "no" / "skip" → skip 응답 (기록만 남김, 드릴 X)
    - "yes" + offer_category (v9.4.4 신규) → 약속한 카테고리로 바로 드릴 추천
    - "yes" + offer_category 없음 → 기존: 상태값 기반 보조 드릴 (positive_card 우회)
    - "tie" + chosen_candidate → 사용자가 선택한 신호 카테고리로 추천
    """
    rng = rng or random.Random()
    recent = recent_drill_ids or []

    if user_choice in ("no", "skip"):
        return build_skip("기록만 남겨두었어요. 오늘도 충분해요.")

    patterns = {k: float(label_result.get("patterns", {}).get(k, 0.0)) for k in PATTERNS_KO}
    behaviors = {k: float(label_result.get("behaviors", {}).get(k, 0.0)) for k in BEHAVIORS_KO}
    emotions = {k: float(label_result.get("emotions", {}).get(k, 0.0)) for k in EMOTIONS_KO}
    evidence_span = label_result.get("evidence_span") or None
    confidence = float(label_result.get("confidence", 0.5))

    # v9.5: user_discoveries 자동 조회 (after_ask 흐름에도 동일 적용)
    user_disc: list[str] = []
    if user_id:
        try:
            from app.core.insights_store import get_recent_user_discoveries as _gd
            user_disc = _gd(user_id, limit=5)
        except Exception:  # noqa: BLE001
            user_disc = []

    affinity_keys = _context_affinity_keys(context) | _user_discovery_affinity_keys(user_disc)

    if user_choice == "tie" and chosen_candidate:
        # 사용자가 선택한 후보가 인지/행동 어느 쪽인지 판별 → 해당 카테고리 추천
        if chosen_candidate in PATTERNS_KO:
            category = CategoryEn.COGNITIVE_RESTRUCTURING.value
        elif chosen_candidate in BEHAVIORS_KO:
            if chosen_candidate == "회피미루기":
                category = CategoryEn.BEHAVIORAL_ACTIVATION.value
            else:
                category = CategoryEn.HABIT_DESIGN.value
        else:
            category = CategoryEn.GROUNDING.value
        drill = _pick_drill(
            category,
            patterns=patterns, behaviors=behaviors, emotions=emotions,
            affinity_keys=affinity_keys, recent_drill_ids=recent, rng=rng, pref_bonus=pref_bonus,
            context=context,
        )
        if drill:
            return _build_drill_response(
                drill,
                evidence_span=evidence_span,
                confidence=confidence,
                patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                reason=f"사용자 선택: {chosen_candidate}",
            )

    # v9.4.4: offer_category 명시되면 약속한 카테고리로 바로 추천 (ask-first 정책)
    if user_choice == "yes" and offer_category:
        drill = _pick_drill(
            offer_category,
            patterns=patterns, behaviors=behaviors, emotions=emotions,
            affinity_keys=affinity_keys, recent_drill_ids=recent, rng=rng, pref_bonus=pref_bonus,
            context=context,
        )
        if drill:
            return _build_drill_response(
                drill,
                evidence_span=evidence_span,
                confidence=confidence,
                patterns=patterns, behaviors=behaviors, emotions=emotions, context=context,
                reason=f"사용자 동의 후 맥락 기반 추천 ({offer_category})",
            )
        # offer_category로 드릴 없으면 → 상태값 기반 fallback (아래)

    # user_choice == "yes" (offer_category 없거나 매칭 실패) — 상태값 기반 보조 드릴
    sc = int(context.get("self_condition", 3))
    sleep_h = context.get("sleep_hours")
    social = context.get("social_today")

    # 우선순위: 가장 약점이 큰 영역 먼저
    if sc <= 2:
        cat = CategoryEn.GROUNDING.value
        reason = f"컨디션 낮음 ({sc}) — grounding 보조"
    elif sleep_h is not None and float(sleep_h) < 6:
        cat = CategoryEn.SLEEP_CIRCADIAN.value
        reason = f"수면 부족 ({sleep_h}h) — sleep_circadian 보조"
    elif social in ("갈등",):
        cat = CategoryEn.SELF_COMPASSION.value
        reason = "사교 갈등 — self_compassion 보조"
    else:
        # 모두 양호 — 가장 가벼운 카테고리 (habit_design 2분 룰)
        cat = CategoryEn.HABIT_DESIGN.value
        reason = "오늘 양호 — 작은 습관으로 시작"

    drill = _pick_drill(
        cat,
        patterns=patterns, behaviors=behaviors, emotions=emotions,
        affinity_keys=affinity_keys, recent_drill_ids=recent, rng=rng, pref_bonus=pref_bonus,
        context=context,
    )
    if drill:
        return _build_drill_response(
            drill, evidence_span=evidence_span, confidence=confidence, reason=reason,
        )

    return build_skip("추천 드릴이 없어요. 오늘은 기록만 남겨두었어요.")
