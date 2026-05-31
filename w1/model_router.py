"""
model_router.py
===============
Gemini API의 여러 모델을 우선순위 순으로 시도해 사용 가능한 모델 찾고,
1차 라벨링용 (Primary) + 2차 정밀화용 (Light) 두 tier를 운용.

Primary: 정확도 우선 — 더 큰 모델
Light: 속도·비용 우선 — 짧은 객관식 답변용

폴백:
- 한 모델 quota 초과 → 다음 tier 시도
- 모두 실패 → RuntimeError
"""
import os
import time
import re
from typing import Optional


# ============================================================================
# 모델 점수 매기기
# ============================================================================

def score_model(model_name: str) -> int:
    """모델 이름에 점수 매김. 높을수록 우선."""
    name = model_name.lower()
    score = 0
    if "flash" in name:
        score += 1000
    elif "pro" in name:
        score += 500
    if "2.5" in name or "2-5" in name:
        score += 400
    elif "2.0" in name or "2-0" in name:
        score += 300
    elif "1.5" in name or "1-5" in name:
        score += 200
    if "lite" in name:
        score += 100
    for unstable in ["exp", "experimental", "thinking", "preview", "tts", "image", "vision", "embedding", "aqa"]:
        if unstable in name:
            score -= 500
    if "latest" in name:
        score += 50
    if "8b" in name:
        score += 50
    return score


def detect_working_model(genai, exceptions) -> str:
    """계정에서 호출 가능한 모델 점수 순으로 시도."""
    print("[모델 감지]")
    try:
        all_models = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        print(f"  계정에서 호출 가능: {len(all_models)}개")
    except Exception as e:
        raise RuntimeError(f"모델 리스트 조회 실패: {e}")

    scored = sorted([(score_model(m), m) for m in all_models], reverse=True)
    print("  점수 상위 5:")
    for s, m in scored[:5]:
        print(f"    [{s:>4}] {m}")

    failed = []
    for s, candidate in scored:
        if s < 0:
            continue
        try:
            print(f"  테스트: {candidate} ... ", end="", flush=True)
            test_model = genai.GenerativeModel(candidate)
            response = test_model.generate_content(
                "Reply 'OK'",
                generation_config={"max_output_tokens": 10, "temperature": 0}
            )
            _ = response.text
            print("✓ 작동")
            return candidate
        except exceptions.ResourceExhausted as e:
            err = str(e)
            if "limit: 0" in err:
                print("✗ 무료 한도 0")
                failed.append(f"{candidate}: limit=0")
            else:
                print("✗ 할당량")
                failed.append(f"{candidate}: quota")
        except Exception as e:
            print(f"✗ {type(e).__name__}")
            failed.append(f"{candidate}: {type(e).__name__}")

    raise RuntimeError("사용 가능한 모델 없음. 실패: " + "; ".join(failed[:5]))


# ============================================================================
# ModelRouter
# ============================================================================

class ModelRouter:
    """Primary tier + Light tier 분리 운용."""

    def __init__(self):
        self.genai = None
        self.exceptions = None
        self.current_primary: Optional[str] = None
        self.current_light: Optional[str] = None
        self._primary_model = None
        self._light_model = None

    def initialize(self) -> bool:
        """라이브러리 로드 + 모델 감지."""
        try:
            import google.generativeai as genai
            from google.api_core import exceptions
            self.genai = genai
            self.exceptions = exceptions
        except ImportError:
            print("ERROR: 'pip install google-generativeai' 필요")
            return False

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return False
        genai.configure(api_key=api_key)

        try:
            # Primary 감지
            self.current_primary = detect_working_model(genai, exceptions)
            self._primary_model = genai.GenerativeModel(self.current_primary)
            # Light tier — 같은 모델 또는 더 가벼운 거 사용
            self.current_light = self.current_primary
            self._light_model = self._primary_model
            return True
        except RuntimeError as e:
            print(f"\n[!] {e}")
            return False

    def call_primary(self, prompt: str, temperature: float = 0.1, max_output_tokens: int = 400) -> str:
        """1차 라벨링용 호출."""
        response = self._primary_model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_output_tokens}
        )
        return response.text.strip()

    def call_light(self, prompt: str, temperature: float = 0.0, max_output_tokens: int = 10) -> str:
        """2차 정밀화용 호출 (짧은 답)."""
        response = self._light_model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_output_tokens}
        )
        return response.text.strip()


if __name__ == "__main__":
    print("ModelRouter 단독 실행. GEMINI_API_KEY 필요.")
    router = ModelRouter()
    if router.initialize():
        print(f"Primary: {router.current_primary}")
        print(f"Light:   {router.current_light}")
    else:
        print("초기화 실패")
