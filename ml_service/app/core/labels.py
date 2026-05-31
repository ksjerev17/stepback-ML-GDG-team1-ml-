# 출처: taxonomy_v7.json (단일 진실 공급원) — 사용자 친화 라벨/설명.
"""패턴·행동·감정의 사용자 친화 표현 매핑.

화면에 임상용어("미래예측")만 노출하면 딱지 느낌·이해도 저하가 생긴다.
taxonomy의 user_facing_label / user_facing_definition / user_facing_question을
끌어와, 응답에 임상용어와 일상어를 함께 담는다. (화면 표기 선택은 FE 몫)
"""
from __future__ import annotations

from functools import lru_cache

from app.config import W1_DIR

# 감정은 taxonomy에 user_facing_label이 비어 있어 여기서 보강 (일상어).
_EMOTION_FALLBACK: dict[str, dict[str, str]] = {
    "불안": {"label": "불안한 마음", "why": "걱정·긴장이 자주 묻어나는 표현이라서"},
    "우울": {"label": "가라앉은 기분", "why": "기운이 빠지고 가라앉은 느낌이 담겨서"},
    "분노": {"label": "화난 마음", "why": "치밀어 오르는 감정이 드러나서"},
    "죄책": {"label": "미안한 마음", "why": "자신을 탓하거나 미안해하는 결이 보여서"},
    "중립": {"label": "잔잔한 상태", "why": ""},
}


@lru_cache(maxsize=1)
def _label_map() -> dict[str, dict[str, str]]:
    """taxonomy에서 llm_key → {label, definition, question} 추출."""
    import json
    out: dict[str, dict[str, str]] = {}
    path = W1_DIR / "taxonomy_v7.json"
    if not path.exists():
        return out
    try:
        tax = json.loads(path.read_text(encoding="utf-8"))
        dims = tax.get("llm_labeled_dimensions", {})
        for grp in ("cognitive_patterns", "behavior_signals", "emotions"):
            for _k, v in dims.get(grp, {}).get("list", {}).items():
                key = v.get("llm_key") or _k
                out[key] = {
                    "label": v.get("user_facing_label") or "",
                    "definition": v.get("user_facing_definition") or "",
                    "question": v.get("user_facing_question") or "",
                }
    except (ValueError, OSError):
        return out
    return out


def friendly_label(clinical_key: str) -> str:
    """임상용어 → 일상어 라벨. (예: '미래예측' → '미리 결론 내리기')"""
    m = _label_map().get(clinical_key)
    if m and m.get("label"):
        return m["label"]
    if clinical_key in _EMOTION_FALLBACK:
        return _EMOTION_FALLBACK[clinical_key]["label"]
    return clinical_key


def why_evidence(clinical_key: str, kind: str) -> str:
    """이 단서가 '왜 그 패턴/감정의 근거인지' 한 줄 (사용자 납득용).

    인지/행동: taxonomy의 user_facing_definition을 근거 문장으로.
    감정: fallback의 why.
    """
    m = _label_map().get(clinical_key)
    if kind == "emotion":
        e = _EMOTION_FALLBACK.get(clinical_key)
        return e["why"] if e else ""
    if m and m.get("definition"):
        # 정의를 '~라서' 근거 어미로
        d = m["definition"].rstrip(".")
        return f"{d} 결이 보여서"
    return ""


def label_pair(clinical_key: str, kind: str = "pattern") -> dict[str, str]:
    """응답에 담을 (임상용어 + 일상어 + 근거) 묶음."""
    return {
        "clinical": clinical_key,
        "friendly": friendly_label(clinical_key),
        "why": why_evidence(clinical_key, kind),
    }
