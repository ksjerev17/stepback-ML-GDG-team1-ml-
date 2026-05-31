"""
clarification_loop.py
=====================
1차 LLM 라벨링이 모호할 때 2차 객관식 호출로 정밀화.

모호 조건:
- confidence < 0.6
- 또는 top-1과 top-2 차이 < 0.15 (tie)

작동:
- 인지 + 행동 통합 풀에서 top-1·top-2 추출
- 객관식 (A/B/C) 프롬프트 자동 생성
- LLM에게 두 패턴 중 어느 게 더 강한지 묻기
- 답에 따라 1차 결과 정밀화

사용:
    from clarification_loop import clarify_if_ambiguous
    refined = clarify_if_ambiguous(result, text, llm_call_fn, pattern_definitions)
"""
from typing import Optional


def is_ambiguous(result: dict, threshold_conf: float = 0.6, threshold_tie: float = 0.15) -> tuple:
    """1차 결과가 모호한가."""
    if "_error" in result or result.get("_crisis"):
        return False, "오류 또는 위기 — 정밀화 불가"

    conf = result.get("confidence", 0)
    if conf < threshold_conf:
        return True, f"low_confidence (={conf})"

    # 인지 + 행동 통합 풀
    pool = {}
    pool.update(result.get("patterns", {}))
    pool.update(result.get("behaviors", {}))
    if not pool:
        return False, "패턴·행동 데이터 없음"

    sorted_pool = sorted(pool.items(), key=lambda x: -x[1])
    if len(sorted_pool) < 2:
        return False, "신호 1개 이하"

    top1_val = sorted_pool[0][1]
    top2_val = sorted_pool[1][1]

    if top1_val < 0.3:
        return False, "모든 신호 약함 — 정밀화 무의미"

    diff = top1_val - top2_val
    if diff < threshold_tie:
        return True, f"top_tie (diff={diff:.2f}, {sorted_pool[0][0]}={top1_val} vs {sorted_pool[1][0]}={top2_val})"

    return False, "명확한 dominant"


def build_clarification_prompt(text: str, pattern_a: str, pattern_b: str, pattern_definitions: dict) -> str:
    """모호한 두 패턴 중 어느 게 강한지 묻는 객관식 프롬프트."""
    meta_a = pattern_definitions.get(pattern_a, {})
    meta_b = pattern_definitions.get(pattern_b, {})

    def_a = meta_a.get("user_facing_definition") or meta_a.get("definition", pattern_a)
    def_b = meta_b.get("user_facing_definition") or meta_b.get("definition", pattern_b)

    return f'''주어진 한국어 한 줄 문장에서, 두 가지 신호 중 어느 것이 더 강하게 드러나는지 판단하세요.
(신호는 사고 패턴일 수도, 행동 상태(회피·미루기·무기력)일 수도 있습니다.)

문장: "{text}"

A) {pattern_a}: {def_a}
B) {pattern_b}: {def_b}
C) 둘 다 비슷하게 강함 (변별 어려움)

규칙:
- 반드시 A, B, C 중 하나만 출력. 다른 텍스트 일체 금지.
- 미세한 차이라도 더 강한 신호 1개를 고를 수 있으면 A 또는 B.
- 정말로 둘 다 동등하면 C.

출력:'''


def parse_clarification_response(raw: str) -> Optional[str]:
    """LLM 답에서 A/B/C 추출."""
    raw = raw.strip().upper()
    for char in raw:
        if char in ("A", "B", "C"):
            return char
    return None


def apply_clarification(result: dict, cand_a: str, cand_b: str, choice: str, boost: float = 0.10) -> dict:
    """2차 답에 따라 1차 결과 정밀화."""
    patterns = result.get("patterns", {})
    behaviors = result.get("behaviors", {})

    def _bump(name: str, delta: float):
        if name in patterns:
            patterns[name] = min(1.0, max(0.0, patterns[name] + delta))
        elif name in behaviors:
            behaviors[name] = min(1.0, max(0.0, behaviors[name] + delta))

    if choice == "A":
        _bump(cand_a, +boost)
        _bump(cand_b, -boost)
        result["clarified_winner"] = cand_a
    elif choice == "B":
        _bump(cand_a, -boost)
        _bump(cand_b, +boost)
        result["clarified_winner"] = cand_b
    elif choice == "C":
        result["confidence"] = min(0.95, result.get("confidence", 0.5) + 0.05)
        result["clarified_winner"] = "tie_confirmed"

    result["clarification_applied"] = {"candidates": [cand_a, cand_b], "choice": choice, "boost": boost}
    return result


def clarify_if_ambiguous(result: dict, text: str, llm_call_fn, pattern_definitions: dict) -> dict:
    """1차 결과 모호 시 2차 호출."""
    ambiguous, reason = is_ambiguous(result)
    if not ambiguous:
        result["clarification_skipped"] = reason
        return result

    pool = {}
    pool.update(result.get("patterns", {}))
    pool.update(result.get("behaviors", {}))
    sorted_pool = sorted(pool.items(), key=lambda x: -x[1])
    cand_a = sorted_pool[0][0]
    cand_b = sorted_pool[1][0]

    prompt = build_clarification_prompt(text, cand_a, cand_b, pattern_definitions)

    try:
        raw = llm_call_fn(prompt)
    except Exception as e:
        result["clarification_error"] = str(e)
        return result

    choice = parse_clarification_response(raw)
    if choice is None:
        result["clarification_error"] = f"파싱 실패: '{raw[:50]}'"
        return result

    result = apply_clarification(result, cand_a, cand_b, choice)
    result["clarification_reason"] = reason
    return result


# ============================================================================
# 자기 테스트
# ============================================================================

if __name__ == "__main__":
    pattern_defs = {
        "당위진술": {"user_facing_definition": "'반드시 ~해야 한다'로 자신을 압박하는 습관"},
        "자기비난": {"user_facing_definition": "외부 사건을 자기 탓으로 돌리는 습관"},
        "회피미루기": {"user_facing_definition": "해야 할 일을 미루거나 시작 자체를 피하는 상태"},
        "미래예측": {"user_facing_definition": "안 좋게 미리 정해두는 습관"}
    }

    # Test 1: tie
    result_tie = {
        "patterns": {"당위진술": 0.5, "자기비난": 0.5, "미래예측": 0.0, "독심술": 0.0, "이분법": 0.0, "과잉일반화": 0.0},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {}, "confidence": 0.7, "evidence_span": "test"
    }
    amb, reason = is_ambiguous(result_tie)
    assert amb is True
    print(f"[PASS] tie 감지: {reason}")

    # Test 2: low confidence
    result_low = {
        "patterns": {"미래예측": 0.6, "독심술": 0.0, "자기비난": 0.0, "이분법": 0.0, "당위진술": 0.0, "과잉일반화": 0.0},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {}, "confidence": 0.4, "evidence_span": "test"
    }
    amb, reason = is_ambiguous(result_low)
    assert amb is True
    print(f"[PASS] low conf 감지: {reason}")

    # Test 3: 명확
    result_clear = {
        "patterns": {"미래예측": 0.8, "독심술": 0.1, "자기비난": 0.0, "이분법": 0.0, "당위진술": 0.0, "과잉일반화": 0.0},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {}, "confidence": 0.75, "evidence_span": "test"
    }
    amb, reason = is_ambiguous(result_clear)
    assert amb is False
    print(f"[PASS] 명확 통과: {reason}")

    # Test 4: 2차 적용
    def mock_a(prompt): return "A"
    refined = clarify_if_ambiguous(result_tie, "test", mock_a, pattern_defs)
    assert refined["clarified_winner"] == "당위진술"
    print(f"[PASS] choice A 적용: winner={refined['clarified_winner']}")

    # Test 5: tie 확인 (C)
    def mock_c(prompt): return "C"
    result_tie2 = {
        "patterns": {"당위진술": 0.5, "자기비난": 0.5, "미래예측": 0.0, "독심술": 0.0, "이분법": 0.0, "과잉일반화": 0.0},
        "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
        "emotions": {}, "confidence": 0.7, "evidence_span": "test"
    }
    refined2 = clarify_if_ambiguous(result_tie2, "test", mock_c, pattern_defs)
    assert refined2["clarified_winner"] == "tie_confirmed"
    print(f"[PASS] choice C: confidence {result_tie2['confidence']} (보존)")

    print("\n모든 테스트 통과.")
