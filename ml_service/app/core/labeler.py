# 출처: CLAUDE.md §11.4
"""라벨링 코어 — mask → quota → LLM → postprocess → clarification → audit."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import W1_DIR
from app.infra.audit_log import hash_user_id, summarize_label, write as audit_write
from app.infra.llm_client import LLMClient, get_llm_client
from app.infra.pii_masker import mask_pii
from app.infra.quota_manager import QuotaManager, get_quota_manager
from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO


_w1 = str(W1_DIR.resolve())
if _w1 not in sys.path:
    sys.path.insert(0, _w1)

from label_postprocess import postprocess  # type: ignore  # noqa: E402
from clarification_loop import clarify_if_ambiguous  # type: ignore  # noqa: E402


def _pattern_definitions() -> dict[str, dict[str, str]]:
    """taxonomy_v7.json에서 user_facing_definition만 추출 (clarification용)."""
    path = W1_DIR / "taxonomy_v7.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    dims = data.get("llm_labeled_dimensions", {})
    for entry in dims.get("cognitive_patterns", {}).get("list", {}).values():
        name = entry.get("llm_key") or entry.get("name_ko")
        if name:
            out[name] = {
                "user_facing_definition": entry.get("user_facing_definition", ""),
                "definition": entry.get("definition", ""),
            }
    for entry in dims.get("behavior_signals", {}).get("list", {}).values():
        name = entry.get("llm_key") or entry.get("name_ko")
        if name:
            out[name] = {
                "user_facing_definition": entry.get("user_facing_definition", ""),
                "definition": entry.get("definition", ""),
            }
    return out


_PATTERN_DEFS = _pattern_definitions()


# v9.4.3 §4.2: 맥락변수 일 1회 입력.
# (user_id, YYYY-MM-DD KST) → {sleep_hours, social_today, exercise_today}
# self_condition은 매번 입력 — 캐시 제외.
import threading as _threading
from datetime import datetime as _datetime, timezone as _timezone, timedelta as _timedelta

_KST = _timezone(_timedelta(hours=9))
_context_cache: dict[tuple[str, str], dict[str, Any]] = {}
_context_cache_lock = _threading.Lock()

CACHEABLE_CONTEXT_KEYS = ("sleep_hours", "social_today", "exercise_today")


def _kst_day_str() -> str:
    """KST 기준 오늘 (YYYY-MM-DD)."""
    return _datetime.now(_KST).strftime("%Y-%m-%d")


def cache_context(user_id: str, day: str, ctx: dict[str, Any]) -> None:
    """v9.4.3: 하루 첫 입력 시 호출. self_condition 제외 3개 캐싱."""
    with _context_cache_lock:
        _context_cache[(user_id, day)] = {
            k: ctx[k] for k in CACHEABLE_CONTEXT_KEYS if k in ctx
        }


def get_cached_context(user_id: str, day: str) -> dict[str, Any] | None:
    with _context_cache_lock:
        cached = _context_cache.get((user_id, day))
        return dict(cached) if cached else None


def clear_context_cache(user_id: str | None = None) -> None:
    """테스트용. user_id 지정 시 그 사용자만, None이면 전체."""
    with _context_cache_lock:
        if user_id is None:
            _context_cache.clear()
        else:
            keys_to_del = [k for k in _context_cache if k[0] == user_id]
            for k in keys_to_del:
                del _context_cache[k]


def apply_context_cache(user_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """v9.4.3 §4.2: BE가 같은 날 두 번째·세 번째 입력에 사용.

    - 같은 user_id + 같은 KST 날짜의 sleep/social/exercise 값을 캐시에서 채움.
    - 사용자가 새 값 명시했으면 그대로 사용 + 캐시 갱신.
    - 캐시 miss + 사용자도 명시 안 함 → 기본값 (sleep 7h / social 보통 / exercise 0h).
    """
    day = _kst_day_str()
    cached = get_cached_context(user_id, day) or {}
    out = dict(ctx)
    # 명시되지 않은 캐시 가능 키만 캐시에서 채움
    for k in CACHEABLE_CONTEXT_KEYS:
        if k not in out and k in cached:
            out[k] = cached[k]
    # 캐시 갱신 (이번 호출에 명시된 키)
    new_cache_data = {k: out[k] for k in CACHEABLE_CONTEXT_KEYS if k in out}
    if new_cache_data:
        with _context_cache_lock:
            existing = _context_cache.get((user_id, day), {})
            existing.update(new_cache_data)
            _context_cache[(user_id, day)] = existing
    return out


def _ensure_complete_scores(result: dict[str, Any]) -> dict[str, Any]:
    """LLM/Mock 응답에 키 누락 시 0.0 채움."""
    p = result.get("patterns", {}) or {}
    for k in PATTERNS_KO:
        p.setdefault(k, 0.0)
    result["patterns"] = p
    b = result.get("behaviors", {}) or {}
    for k in BEHAVIORS_KO:
        b.setdefault(k, 0.0)
    result["behaviors"] = b
    e = result.get("emotions", {}) or {}
    for k in EMOTIONS_KO:
        e.setdefault(k, 0.0)
    if e["중립"] == 0.0:
        non_neutral = max(e[k] for k in EMOTIONS_KO if k != "중립")
        if non_neutral < 0.3:
            e["중립"] = round(1.0 - non_neutral, 2)
    result["emotions"] = e
    return result


def _calendar_dominant(result: dict[str, Any]) -> str:
    """부록 C 매핑."""
    if result.get("crisis_detected"):
        return "crisis"
    patterns = result.get("patterns", {})
    behaviors = result.get("behaviors", {})
    emotions = result.get("emotions", {})
    p_max = max(patterns.values()) if patterns else 0.0
    b_max = max(behaviors.values()) if behaviors else 0.0
    e_anx = emotions.get("불안", 0.0)
    e_dep = emotions.get("우울", 0.0)
    e_ang = emotions.get("분노", 0.0)
    e_guilt = emotions.get("죄책", 0.0)
    others = {"anxiety": e_anx, "depression": e_dep, "anger": e_ang, "guilt": e_guilt}

    def _emo_dominant(target: str) -> bool:
        val = others[target]
        if val < 0.5:
            return False
        others_below = all(v < 0.4 for k, v in others.items() if k != target)
        return others_below and p_max < 0.4 and b_max < 0.4

    if _emo_dominant("anger"):
        return "emotion_anger"
    if _emo_dominant("anxiety"):
        return "emotion_anxiety"
    if _emo_dominant("depression"):
        return "emotion_depression"
    if _emo_dominant("guilt"):
        return "emotion_guilt"
    if b_max >= 0.5:
        return "behavior_dominant"
    if p_max >= 0.5 and b_max < 0.5:
        return "cognitive_dominant"
    return "weak_signal_positive"


def label_text(
    text: str,
    user_id: str,
    *,
    llm: LLMClient | None = None,
    quota: QuotaManager | None = None,
    skip_quota: bool = False,
) -> dict[str, Any]:
    """W1 후처리·정밀화까지 포함한 라벨링 전체 파이프라인."""
    llm = llm or get_llm_client()
    quota = quota or get_quota_manager()

    if not skip_quota:
        quota.check_and_increment(user_id, "label")

    masked = mask_pii(text)
    raw_result = llm.label(masked)
    raw_result = _ensure_complete_scores(raw_result)

    result = postprocess(raw_result, text)
    result = _ensure_complete_scores(result)

    if not result.get("crisis_detected"):
        result = clarify_if_ambiguous(result, text, llm.clarify, _PATTERN_DEFS)

    result["calendar_dominant"] = _calendar_dominant(result)
    result["model_used"] = result.pop("_model_used", llm.primary_model)
    result["labeled_at"] = datetime.now(timezone.utc).isoformat()

    audit_write(
        endpoint="label",
        user_hash=hash_user_id(user_id),
        text_len=len(text),
        extra=summarize_label(result),
    )
    return result
