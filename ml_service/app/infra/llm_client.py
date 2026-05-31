# 출처: CLAUDE.md §11.3
"""LLM 호출 클라이언트.

API 키 보유 시: Gemini Primary/Light tier (W1 model_router 활용).
키 미보유 또는 FORCE_MOCK 시: 어휘 단서(taxonomy linguistic_cues) 기반 Mock.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from app.config import W1_DIR, should_force_mock
from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO


# v9.4.3: 위기 패턴 확장 — 한국어 + 영어 + 은유 + 띄어쓰기 우회.
CRISIS_PATTERNS_KO: tuple[str, ...] = (
    "죽고 싶", "사라지고 싶", "끝내고 싶", "자해", "목숨",
    "더 이상 살", "살고 싶지 않", "자살",
    # 은유 추가
    "사라지면", "없어지면", "끝내버리", "이 세상에서 사라",
    "다 끝내", "포기하고 싶", "더는 못", "그만하고 싶",
)
CRISIS_PATTERNS_EN: tuple[str, ...] = (
    # 어근 정규화 — "kill", "killing", "killed" 모두 잡음
    "kill myself", "killing myself", "killed myself",
    "want to die", "wanna die", "wish i was dead",
    "end it all", "end my life", "end this life",
    "suicide", "suicidal",
    "self-harm", "self harm", "selfharm", "hurt myself", "hurting myself",
    "disappear forever", "want to disappear", "wanna disappear",
    "don't want to live", "dont want to live", "do not want to live",
    "no reason to live", "no point living", "no point in living",
    "thinking about dying", "think about dying",
)
# 띄어쓰기 우회 감지 — 모든 공백 제거 후 매칭
CRISIS_PATTERNS_COMPACT: tuple[str, ...] = tuple(
    p.replace(" ", "") for p in CRISIS_PATTERNS_KO
)

CRISIS_PATTERNS: tuple[str, ...] = CRISIS_PATTERNS_KO  # 호환


def _load_taxonomy() -> dict:
    path = W1_DIR / "taxonomy_v7.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_cue_map(taxonomy: dict) -> dict[str, dict[str, list[str]]]:
    """taxonomy → {dim: {name_ko: [cues]}} 평탄화."""
    dims = taxonomy.get("llm_labeled_dimensions", {})
    out: dict[str, dict[str, list[str]]] = {
        "patterns": {},
        "behaviors": {},
        "emotions": {},
    }
    for entry in dims.get("cognitive_patterns", {}).get("list", {}).values():
        name = entry.get("name_ko") or entry.get("llm_key")
        cues = entry.get("linguistic_cues", [])
        if name:
            out["patterns"][name] = cues
    for entry in dims.get("behavior_signals", {}).get("list", {}).values():
        name = entry.get("llm_key") or entry.get("name_ko")
        cues = entry.get("linguistic_cues", [])
        if name:
            out["behaviors"][name] = cues
    for entry in dims.get("emotions", {}).get("list", {}).values():
        name = entry.get("name_ko")
        cues = entry.get("linguistic_cues", [])
        if name and name != "중립":
            out["emotions"][name] = cues
    return out


_TAXONOMY = _load_taxonomy()
_CUES = _extract_cue_map(_TAXONOMY) if _TAXONOMY else {"patterns": {}, "behaviors": {}, "emotions": {}}


def _zero_scores() -> dict:
    return {
        "patterns": {k: 0.0 for k in PATTERNS_KO},
        "behaviors": {k: 0.0 for k in BEHAVIORS_KO},
        "emotions": {k: 0.0 for k in EMOTIONS_KO},
    }


# v9.5: 욕설 감지 — intensity 가산용 (anger 분류와는 별개)
PROFANITY_PATTERNS = (
    "씨발", "시발", "ㅅㅂ", "ㅆㅂ",
    "좆같", "좆같다", "조까", "조낸",
    "개같", "개새끼", "개놈",
    "씹새", "씹할", "꺼져",
    "지랄", "ㅈㄹ", "병신", "ㅂㅅ",
    "엿같", "ㅈㄴ", "존나",
    "fuck", "shit", "wtf", "damn",
)


def _has_profanity(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(p in lower for p in PROFANITY_PATTERNS)


def _detect_crisis(text: str) -> bool:
    """v9.4.3: 한국어 + 영어 + 띄어쓰기 우회 감지."""
    if not text:
        return False
    # 한국어 직접
    if any(p in text for p in CRISIS_PATTERNS_KO):
        return True
    # 영어 (소문자 비교)
    lower = text.lower()
    if any(p in lower for p in CRISIS_PATTERNS_EN):
        return True
    # 띄어쓰기 우회 ("죽 고 싶 어" → "죽고싶어")
    compact = "".join(text.split())
    if any(p in compact for p in CRISIS_PATTERNS_COMPACT):
        return True
    return False


def _score_by_cues(text: str, cues_for_dim: dict[str, list[str]]) -> dict[str, float]:
    """어휘 단서 매칭 — v9.7 정밀화.

    개선점:
    - 부정 가드: 단서 바로 앞에 부정어('안','않','아니','없')가 붙으면 무효
      (예: "안 망할 것 같아"는 미래예측으로 치지 않음).
    - 체감 증가: 서로 다른 단서 1개 +0.35, 2개 +0.2, 3개 +0.1 (반복 과대평가 방지).
    - 상한 0.7 유지 (Mock의 한계를 정직하게; 실 Gemini는 자체 confidence 사용).
    """
    _NEG = ("안", "않", "아니", "없")
    result: dict[str, float] = {name: 0.0 for name in cues_for_dim}
    for name, cues in cues_for_dim.items():
        hits = 0
        seen_idx: set[int] = set()
        for cue in cues:
            cue_core = cue.replace("~", "").strip()
            if not cue_core:
                continue
            idx = text.find(cue_core)
            if idx < 0 or idx in seen_idx:
                continue
            pre = text[max(0, idx - 4):idx]
            if any(neg in pre for neg in _NEG):
                continue
            seen_idx.add(idx)
            hits += 1
        score = 0.0
        for i in range(hits):
            score += (0.35, 0.20, 0.10)[i] if i < 3 else 0.05
        result[name] = round(min(score, 0.7), 2)
    return result


def _find_evidence_span(text: str, scores: dict) -> str:
    """가장 높은 신호의 cue가 텍스트 안에 어디 있는지 — 깔끔한 구절 추출.

    v9.7: 어절(공백) 경계에 맞춰 잘라 중간이 잘리지 않게.
    인용으로 보여줄 것이므로 4~16자 자연스러운 구절을 우선.
    """
    pool: list[tuple[float, str, str]] = []
    for dim_name, dim_scores in scores.items():
        if dim_name not in ("patterns", "behaviors"):
            continue
        for name, score in dim_scores.items():
            if score > 0:
                pool.append((score, dim_name, name))
    pool.sort(reverse=True)
    for _, dim_name, name in pool:
        for cue in _CUES.get(dim_name, {}).get(name, []):
            cue_core = cue.replace("~", "").strip()
            if not cue_core or cue_core not in text:
                continue
            idx = text.find(cue_core)
            # 단서를 포함하는 구절을, 어절 경계로 확장 (앞뒤로 최대 1어절)
            start = idx
            # 앞으로: 직전 공백까지
            sp = text.rfind(" ", 0, idx)
            if sp >= 0 and idx - sp <= 8:
                start = sp + 1
            end = idx + len(cue_core)
            # 뒤로: 다음 공백까지 (한 어절만)
            nx = text.find(" ", end)
            if nx >= 0 and nx - end <= 8:
                end = nx
            snippet = text[start:end].strip()
            # 너무 길면 단서 중심으로 컷
            if len(snippet) > 16:
                snippet = text[idx:idx + 12].strip()
            return snippet or cue_core
    return ""


def _load_system_prompt() -> str:
    """W1의 labeling_prompt_v3.md에서 시스템 프롬프트 추출 (4-backtick 블록)."""
    path = W1_DIR / "labeling_prompt_v3.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    start = text.find("````")
    if start < 0:
        return ""
    end = text.find("````", start + 4)
    if end < 0:
        return ""
    return text[start + 4:end].strip()


_SYSTEM_PROMPT = _load_system_prompt()


def _parse_llm_json(raw: str) -> dict:
    """LLM 응답을 JSON으로 파싱. CRISIS_DETECTED 토큰 우선 검사."""
    if not raw:
        return {"_error": "empty_response"}
    s = raw.strip()
    if "CRISIS_DETECTED" in s.upper():
        result = _zero_scores()
        result["crisis_detected"] = True
        result["evidence_span"] = "위기 신호 감지"
        result["intensity"] = 0.0
        result["confidence"] = 0.0
        return result
    # 코드 펜스 제거
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl > 0:
            s = s[first_nl + 1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 응답 안의 JSON만 추출 시도
        i = s.find("{")
        j = s.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except json.JSONDecodeError:
                pass
        return {"_error": "parse_failed", "_raw": s[:200]}


# 신·구 SDK 모델 선호도 (높을수록 먼저 시도)
# v9.6 갱신: Gemini 2.0 세대는 2026-02-19 폐기(deprecated)됨.
#   현재 무료 tier 안정 모델 = 2.5 Flash-Lite / 2.5 Flash (+ 3 Flash Preview).
#   2.5 Flash-Lite: 가장 너그러운 무료 한도 + 빠르고 저렴 → 베타/데모 1순위.
#   2.5 Flash: 더 정확 (무료 10 RPM / 250k TPM) → 2순위.
#   (2.0 계열은 혹시 계정에 아직 보이면 쓰도록 폴백으로만 남김. _pick_best_model이
#    실제 사용 가능한 모델 목록에서만 고르므로 폐기 모델은 자동으로 건너뜀.)
_MODEL_PREFERENCE = (
    "gemini-2.5-flash-lite",     # 1순위 — 무료 한도 너그럽고 빠름·저렴
    "gemini-2.5-flash",          # 2순위 — 더 정확 (10 RPM / 250k TPM)
    "gemini-flash-latest",       # 3순위 — 최신 flash 별칭(있으면)
    "gemini-2.0-flash-lite",     # 폴백 — 2.0 (deprecated, 혹시 남아있으면)
    "gemini-2.0-flash",          # 폴백
    "gemini-1.5-flash",          # 최후 폴백
)


def _pick_best_model(available: list[str]) -> str | None:
    """사용 가능 모델 중 선호도 높은 것."""
    norm = {m.replace("models/", "").lower(): m.replace("models/", "") for m in available}
    for pref in _MODEL_PREFERENCE:
        for name_lower, name in norm.items():
            if pref in name_lower and "exp" not in name_lower and "thinking" not in name_lower:
                return name
    # fallback: 첫 번째 flash 계열
    for name_lower, name in norm.items():
        if "flash" in name_lower and "exp" not in name_lower:
            return name
    return next(iter(norm.values()), None)


class LLMClient:
    """Primary/Light 두 tier. Mock은 어휘 매칭으로 합리적 라벨 생성.

    SDK 선호도: google-genai (신, FutureWarning 없음) > google-generativeai (구, deprecated).
    """

    def __init__(self, force_mock: Optional[bool] = None) -> None:
        self._force_mock = should_force_mock() if force_mock is None else force_mock
        self._primary_model_name = "mock"
        self._light_model_name = "mock"
        self._gemini = None
        self._sdk_kind = "mock"  # "new" / "old" / "mock"
        self._client = None  # 신 SDK Client 또는 구 SDK genai 모듈
        if not self._force_mock:
            self.initialize()

    @property
    def primary_model(self) -> str:
        return self._primary_model_name

    @property
    def light_model(self) -> str:
        return self._light_model_name

    @property
    def is_mock(self) -> bool:
        return self._force_mock or self._gemini is None

    @property
    def sdk_kind(self) -> str:
        return self._sdk_kind

    def initialize(self) -> bool:
        """Gemini 시도. 신 SDK > 구 SDK 순. 실패 시 Mock 폴백."""
        if self._force_mock:
            return False
        import os
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return False

        # 1. 신 SDK 시도 (google-genai)
        if self._init_new_sdk(api_key):
            self._sdk_kind = "new"
            return True

        # 2. 구 SDK 폴백 (google-generativeai)
        if self._init_old_sdk(api_key):
            self._sdk_kind = "old"
            return True

        return False

    def _init_new_sdk(self, api_key: str) -> bool:
        try:
            from google import genai
        except ImportError:
            return False
        try:
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
            names = [m.name for m in models]
            picked = _pick_best_model(names)
            if not picked:
                return False
            # 검증 호출 (가장 가벼운 1회)
            client.models.generate_content(
                model=picked,
                contents="OK",
                config={"max_output_tokens": 5, "temperature": 0},
            )
            self._client = client
            self._gemini = client
            self._primary_model_name = picked
            self._light_model_name = picked
            return True
        except Exception:  # noqa: BLE001 (graceful fallback)
            return False

    def _init_old_sdk(self, api_key: str) -> bool:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            try:
                import google.generativeai as genai_old  # type: ignore
            except ImportError:
                return False
            try:
                genai_old.configure(api_key=api_key)
                models = list(genai_old.list_models())
                names = [m.name for m in models if "generateContent" in m.supported_generation_methods]
                picked = _pick_best_model(names)
                if not picked:
                    return False
                model = genai_old.GenerativeModel(picked)
                # 검증 호출
                model.generate_content(
                    "OK",
                    generation_config={"max_output_tokens": 5, "temperature": 0},
                )
                self._client = genai_old
                self._gemini = genai_old
                self._primary_model_name = picked
                self._light_model_name = picked
                return True
            except Exception:  # noqa: BLE001
                return False

    def _generate(self, prompt: str, max_tokens: int = 400, temperature: float = 0.1) -> str:
        """SDK 종류에 무관한 통합 호출.

        v9.6: 일시 오류(레이트리밋·타임아웃·네트워크)에 지수 백오프 재시도.
        settings.llm_retry_max 회까지. 모두 실패하면 예외를 올려 label()이 Mock 폴백.
        """
        import time
        from app.config import get_settings
        s = get_settings()
        attempts = max(1, int(getattr(s, "llm_retry_max", 2)) + 1)
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                return self._generate_once(prompt, max_tokens, temperature)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if i < attempts - 1:
                    time.sleep(min(0.5 * (2 ** i), 4.0))  # 0.5s,1s,2s… 상한 4s
        raise last_exc if last_exc else RuntimeError("llm_generate_failed")

    def _generate_once(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """SDK 종류에 무관한 단일 호출 (재시도 없음)."""
        if self._sdk_kind == "new":
            resp = self._client.models.generate_content(
                model=self._primary_model_name,
                contents=prompt,
                config={"max_output_tokens": max_tokens, "temperature": temperature},
            )
            return (resp.text or "").strip()
        # old
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            model = self._client.GenerativeModel(self._primary_model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
            )
            return (resp.text or "").strip()

    def label(self, text: str) -> dict:
        """라벨링 호출. Mock 또는 실제 Gemini.

        v9.6 (안전 강화): 위기 신호는 **LLM 호출 전** 차단.
        실 Gemini 경로에서도 위기 텍스트가 외부(Google)로 전송되지 않도록,
        is_mock 여부와 무관하게 맨 앞에서 _detect_crisis 검사 → 즉시 위기 결과 반환.
        (이전엔 실 LLM 경로에서 호출 *후* 위기 표시 → 평문 외부 전송 위험)
        """
        # ── 위기 사전 차단 (모든 경로 공통, LLM 호출 전) ──
        if _detect_crisis(text):
            result = _zero_scores()
            result.update({
                "intensity": 0.0,
                "confidence": 0.0,
                "evidence_span": "위기 신호 감지",
                "crisis_detected": True,
                "_model_used": "crisis_preblock",
            })
            return result

        if self.is_mock:
            return self._mock_label(text)
        try:
            prompt = f"{_SYSTEM_PROMPT}\n\n입력: \"{text}\"\n출력:"
            raw = self._generate(prompt, max_tokens=400, temperature=0.1)
            result = _parse_llm_json(raw)
            if "_error" in result:
                fallback = self._mock_label(text)
                fallback["_warning"] = f"llm_parse_failed: {result.get('_error')}"
                return fallback
            # 백업: LLM 응답 토큰에 위기 신호가 있으면 표시 (이중 안전)
            if _detect_crisis(text):
                result["crisis_detected"] = True
            # v9.5: 욕설 감지 가산 — 실 LLM 경로에도 적용 (Mock과 정합)
            if not result.get("crisis_detected") and _has_profanity(text):
                cur_int = float(result.get("intensity", 0.0))
                cur_conf = float(result.get("confidence", 0.0))
                result["intensity"] = round(min(cur_int + 0.3, 0.95), 2)
                result["confidence"] = round(min(cur_conf + 0.1, 0.95), 2)
                result["_profanity_detected"] = True
            result["_model_used"] = self._primary_model_name
            return result
        except Exception as e:  # noqa: BLE001 (best-effort fallback)
            fallback = self._mock_label(text)
            fallback["_warning"] = f"llm_error: {type(e).__name__}: {str(e)[:80]}"
            return fallback

    def clarify(self, prompt: str) -> str:
        """객관식 정밀화 — Mock 다양화.

        v9.4.3: Mock에서도 prompt 내용에 따라 A/B/C 결정 (deterministic):
        - prompt 길이 hash 기반 분기 (재현 가능)
        - 60% A, 30% B, 10% C
        """
        if self.is_mock:
            import hashlib
            h = int(hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8], 16)
            pick = h % 10
            if pick < 6:
                return "A"
            if pick < 9:
                return "B"
            return "C"
        try:
            raw = self._generate(prompt, max_tokens=10, temperature=0.0)
            return (raw or "").strip().upper()[:1] or "C"
        except Exception:  # noqa: BLE001
            return "C"

    def _mock_label(self, text: str) -> dict:
        if _detect_crisis(text):
            result = _zero_scores()
            result.update({
                "intensity": 0.0,
                "confidence": 0.0,
                "evidence_span": "위기 신호 감지",
                "crisis_detected": True,
                "_model_used": "mock",
            })
            return result

        result = _zero_scores()
        result["patterns"] = _score_by_cues(text, _CUES.get("patterns", {})) or result["patterns"]
        for k in PATTERNS_KO:
            result["patterns"].setdefault(k, 0.0)
        result["behaviors"] = _score_by_cues(text, _CUES.get("behaviors", {})) or result["behaviors"]
        for k in BEHAVIORS_KO:
            result["behaviors"].setdefault(k, 0.0)
        emo_raw = _score_by_cues(text, _CUES.get("emotions", {}))
        for k in EMOTIONS_KO:
            if k == "중립":
                continue
            result["emotions"][k] = emo_raw.get(k, 0.0)

        non_neutral = max(result["emotions"][k] for k in EMOTIONS_KO if k != "중립")
        result["emotions"]["중립"] = max(0.0, 1.0 - non_neutral) if non_neutral < 0.3 else 0.0

        all_signals = [
            *result["patterns"].values(),
            *result["behaviors"].values(),
            *[result["emotions"][k] for k in EMOTIONS_KO if k != "중립"],
        ]
        top = max(all_signals) if all_signals else 0.0

        # v9.5: 욕설 감지 시 intensity 강제 가산 (강한 정서 표현)
        has_prof = _has_profanity(text)
        intensity_val = top + (0.3 if has_prof else 0.0)
        result["intensity"] = round(min(intensity_val, 0.95), 2)
        # confidence도 욕설이면 명확한 감정 신호이므로 약간 상향
        conf_base = 0.4 + 0.2 * top if top > 0 else 0.30
        result["confidence"] = round(min(conf_base + (0.1 if has_prof else 0.0), 0.95), 2)
        if has_prof:
            result["_profanity_detected"] = True
        result["evidence_span"] = _find_evidence_span(text, result) or text[:20]
        result["crisis_detected"] = False
        result["_model_used"] = "mock"
        return result


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
