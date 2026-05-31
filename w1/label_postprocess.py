"""
label_postprocess.py
====================
LLM 라벨링 출력의 시스템 측 후처리.

목적:
- LLM의 confidence 과신을 길이 기반으로 강제 보정
- evidence_span의 미세 환각을 fuzzy matching으로 허용
- 모든 보정은 원본 값을 별도 필드에 보존 (감사 가능)

사용:
    from label_postprocess import postprocess
    result = postprocess(result, text=user_input_text)
"""
import re
from typing import Optional


def adjust_confidence_by_length(result: dict, text: str) -> dict:
    """
    길이 기반 confidence 보정.
    - < 15자: 최대 0.40
    - 15~29자: 최대 0.55
    - 30~80자: 원본 유지
    - > 80자: 원본 + 0.05 (상한 0.95)
    """
    if "confidence" not in result:
        return result

    text_len = len(text)
    original = result["confidence"]

    if text_len < 15:
        adjusted = min(original, 0.40)
    elif text_len < 30:
        adjusted = min(original, 0.55)
    elif text_len > 80:
        adjusted = min(original + 0.05, 0.95)
    else:
        adjusted = original

    if abs(adjusted - original) > 0.001:
        result["confidence_raw"] = original
        result["confidence"] = round(adjusted, 2)
        result["confidence_adjusted_by"] = "length"

    return result


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _longest_common_substring_ratio(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    n_norm = _normalize(needle)
    h_norm = _normalize(haystack)
    if n_norm in h_norm:
        return 1.0
    best_match_len = 0
    n_len = len(n_norm)
    for start in range(n_len):
        for end in range(n_len, start, -1):
            sub = n_norm[start:end]
            if len(sub) > best_match_len and sub in h_norm:
                best_match_len = len(sub)
                break
    return best_match_len / n_len if n_len > 0 else 0.0


def fix_evidence_span(result: dict, text: str, threshold: float = 0.7) -> dict:
    """evidence_span fuzzy 매칭."""
    span = result.get("evidence_span", "")
    if not span:
        return result
    if span in text:
        return result

    ratio = _longest_common_substring_ratio(span, text)

    if ratio >= threshold:
        span_norm = _normalize(span)
        best_match = ""
        for start in range(len(span_norm)):
            for end in range(len(span_norm), start, -1):
                sub = span_norm[start:end]
                if sub in text and len(sub) > len(best_match):
                    best_match = sub
                    break
        if best_match:
            result["evidence_span_raw"] = span
            result["evidence_span"] = best_match
            result["evidence_span_adjusted"] = f"fuzzy_match (ratio={ratio:.2f})"
    else:
        result["evidence_span_warning"] = f"원문에 부분 일치 {ratio:.2f}만"

    return result


def postprocess(result: dict, text: str) -> dict:
    """
    LLM 라벨링 결과 종합 후처리.
    
    Args:
        result: LLM 출력 (JSON 파싱된 dict)
        text: 원본 사용자 입력
    
    Returns:
        보정된 result
    """
    if "_error" in result or result.get("_crisis"):
        return result

    result = adjust_confidence_by_length(result, text)
    result = fix_evidence_span(result, text, threshold=0.7)
    return result


# ============================================================================
# 자기 테스트
# ============================================================================

if __name__ == "__main__":
    # Test 1: confidence 과신
    r1 = {"confidence": 0.85, "patterns": {}, "emotions": {}}
    r1 = postprocess(r1, "내일 발표 망할 것 같아 진짜 어떻게 하지")
    assert r1["confidence"] == 0.55, f"Expected 0.55, got {r1['confidence']}"
    assert r1["confidence_raw"] == 0.85
    print("[PASS] 짧은 입력 0.85 → 0.55")

    # Test 2: 매우 짧음
    r2 = {"confidence": 0.70, "patterns": {}, "emotions": {}}
    r2 = postprocess(r2, "다 내 탓 같다")
    assert r2["confidence"] == 0.40
    print("[PASS] 매우 짧음 0.70 → 0.40")

    # Test 3: evidence_span 환각
    r3 = {"confidence": 0.8, "evidence_span": "완전 망했다 더 이상 회복할 수 없어", "patterns": {}, "emotions": {}}
    text3 = "이번 학기는 완전 망했다 더 이상 회복할 수 있는 방법이 없어 보여"
    r3 = postprocess(r3, text3)
    assert r3["evidence_span"] in text3
    print(f"[PASS] evidence_span 보정: '{r3.get('evidence_span_raw', 'N/A')}' → '{r3['evidence_span']}'")

    # Test 4: 정상 범위
    r4 = {"confidence": 0.75, "evidence_span": "망할 것 같아", "patterns": {}, "emotions": {}}
    text4 = "내일 면접 망할 것 같아서 잠이 안 와 정말 큰일인 것 같다"
    r4 = postprocess(r4, text4)
    assert "confidence_raw" not in r4
    print(f"[PASS] 정상 범위 ({len(text4)}자) — 보정 없음")

    # Test 5: 긴 입력 상향
    r5 = {"confidence": 0.75, "patterns": {}, "emotions": {}}
    long_text = "오늘 면접 결과 발표인데 분명 떨어졌을 거고 부모님 실망시킬 거고 다시 처음부터 준비할 자신도 없고 어떻게 살아가야 할지 정말 모르겠어 너무 무서워"
    r5 = postprocess(r5, long_text)
    assert r5["confidence"] == 0.80
    print(f"[PASS] 긴 입력 ({len(long_text)}자) 0.75 → 0.80")

    print("\n모든 테스트 통과.")
