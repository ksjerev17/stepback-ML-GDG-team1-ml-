# 출처: 실 Gemini 호출 검증 스크립트
"""Gemini API 키 발급 후 실제 호출이 동작하는지 검증.

사용:
  $env:GEMINI_API_KEY = "AIzaSy..."
  $env:FORCE_MOCK = "false"
  python -X utf8 scripts/test_gemini_live.py

검증 항목 (5):
  1. ModelRouter initialize — 사용 가능한 모델 탐지
  2. 정상 입력 라벨링 — 미래예측 신호
  3. 위기 표현 — CRISIS_DETECTED 또는 백업 감지
  4. 짧은 입력 confidence 보정 (W1 후처리)
  5. 평소(중립) 입력 → 약신호
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 환경 강제
os.environ["FORCE_MOCK"] = "false"


def main() -> int:
    # 1. 키 검증
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[FAIL] GEMINI_API_KEY 환경변수 미설정")
        print("       $env:GEMINI_API_KEY = 'AIzaSy...' 후 재실행")
        return 1
    if not api_key.startswith("AIza"):
        print(f"[WARN] API 키 형식 의심 ({api_key[:10]}...) — Google AI Studio 키는 보통 'AIza'로 시작")

    # 2. SDK import 검증
    try:
        import google.generativeai  # noqa: F401
    except ImportError:
        print("[FAIL] google-generativeai 미설치")
        print("       pip install google-generativeai")
        return 1
    print("[OK] google-generativeai 설치됨")

    # 3. LLMClient 초기화
    from app.infra.llm_client import LLMClient
    print("\n[1/5] ModelRouter 초기화 시도...")
    llm = LLMClient(force_mock=False)
    if llm.is_mock:
        print("[FAIL] Mock 폴백 발생 — 키 잘못되었거나 quota 0")
        return 1
    print(f"[OK] Primary model: {llm.primary_model}")
    print(f"     Light model:   {llm.light_model}")

    cases = [
        ("정상", "내일 발표 망할 것 같아 진짜 어떻게 하지", {"expect_pattern": "미래예측", "min_score": 0.4}),
        ("위기", "더 이상 살고 싶지 않아 사라지고 싶다", {"expect_crisis": True}),
        ("짧은 입력", "다 망함", {"max_confidence": 0.40}),
        ("중립", "오늘 카페에서 공부할 예정이야", {"expect_weak": True}),
        ("행동 회피", "과제 시작해야 하는데 자꾸 폰만 보게 돼", {"expect_behavior": "회피미루기", "min_score": 0.4}),
    ]

    print(f"\n[2/5] 라벨링 5 케이스 호출 (Gemini 호출 간격 6초 — 약 30초 소요)")
    all_pass = True
    for i, (name, text, criteria) in enumerate(cases, start=1):
        print(f"\n--- 케이스 {i}: {name} — {text!r} ---")
        if i > 1:
            time.sleep(6)  # quota 보호
        try:
            result = llm.label(text)
        except Exception as e:
            print(f"  [FAIL] 호출 예외: {type(e).__name__}: {e}")
            all_pass = False
            continue

        if "_warning" in result:
            print(f"  [WARN] {result['_warning']}")

        # 검증
        ok = True

        if "expect_crisis" in criteria:
            if not result.get("crisis_detected"):
                print(f"  [FAIL] crisis_detected=False (기대=True)")
                ok = False
            else:
                print(f"  [OK] crisis_detected=True")

        if "expect_pattern" in criteria:
            patterns = result.get("patterns", {})
            target = criteria["expect_pattern"]
            score = patterns.get(target, 0.0)
            if score < criteria["min_score"]:
                print(f"  [WARN] {target}={score:.2f} (기대 >= {criteria['min_score']})")
                # 경고만 — LLM 응답은 결정론적이지 않음
            else:
                print(f"  [OK] {target}={score:.2f}")

        if "expect_behavior" in criteria:
            behaviors = result.get("behaviors", {})
            target = criteria["expect_behavior"]
            score = behaviors.get(target, 0.0)
            if score < criteria["min_score"]:
                print(f"  [WARN] {target}={score:.2f} (기대 >= {criteria['min_score']})")
            else:
                print(f"  [OK] {target}={score:.2f}")

        if "max_confidence" in criteria:
            conf = result.get("confidence", 0.0)
            if conf > criteria["max_confidence"]:
                print(f"  [FAIL] confidence={conf:.2f} > {criteria['max_confidence']} (짧은 입력 보정 실패)")
                ok = False
            else:
                print(f"  [OK] confidence={conf:.2f} (보정 적용됨)")

        if "expect_weak" in criteria:
            patterns = result.get("patterns", {})
            behaviors = result.get("behaviors", {})
            all_scores = list(patterns.values()) + list(behaviors.values())
            top = max(all_scores) if all_scores else 0.0
            if top >= 0.3:
                print(f"  [WARN] 중립 입력인데 top={top:.2f} (>=0.3 = 약신호 아님)")
            else:
                print(f"  [OK] top={top:.2f} (약신호)")

        all_pass = all_pass and ok
        print(f"  evidence_span: {result.get('evidence_span', '(없음)')[:50]}")
        print(f"  confidence: {result.get('confidence', 0):.2f}")

    # 3. 추천 라우팅까지 통합 (정상 케이스)
    print(f"\n[3/5] 통합 — /label → /recommend 흐름")
    time.sleep(6)
    from app.core.labeler import label_text
    from app.core.recommender import recommend
    try:
        label = label_text("내일 발표 망할 것 같아", user_id="u_gemini_test", skip_quota=True)
        rec = recommend(
            label_result=label,
            context={"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0},
            user_id="u_gemini_test",
        )
        print(f"  type: {rec['type']}")
        if rec["type"] == "drill":
            print(f"  drill: {rec['drill']['id']} {rec['drill']['name']}")
            print(f"  category: {rec['drill']['category']}")
            print(f"  copy.line1: {rec['copy']['line1']}")
            print(f"  copy.line2: {rec['copy']['line2']}")
        elif rec["type"] == "crisis_card":
            print(f"  [WARN] 정상 입력이 위기로 분류됨")
        print(f"  [OK] 통합 흐름 동작")
    except Exception as e:
        print(f"  [FAIL] 통합 흐름 예외: {e}")
        all_pass = False

    # 4. quota 사용량
    print(f"\n[4/5] 비용 추정")
    print(f"  이 스크립트 = 6 호출 (라벨 5 + 통합 1)")
    print(f"  무료 tier gemini-2.0-flash-lite: 일 1,500회 / 분 30회 — 충분")
    print(f"  실제 사용량 확인: https://aistudio.google.com/")

    # 5. 결과
    print(f"\n[5/5] 결과")
    if all_pass:
        print(f"  [PASS] 실 Gemini 호출 모두 정상")
        print(f"  다음: uvicorn app.main:app --host 127.0.0.1 --port 8001")
        print(f"        /healthz의 primary_model이 {llm.primary_model}로 표시됨")
        return 0
    else:
        print(f"  [PARTIAL] 일부 케이스 WARN/FAIL — 로그 확인 권장")
        return 2


if __name__ == "__main__":
    sys.exit(main())
