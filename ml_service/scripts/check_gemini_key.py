"""Gemini API 키 즉시 검증 — 가장 가벼운 호출 1회.

사용:
  $env:GEMINI_API_KEY = "AIzaSy..."
  python -X utf8 ml_service\scripts\check_gemini_key.py

또는 키를 인자로:
  python -X utf8 ml_service\scripts\check_gemini_key.py AIzaSy...

체크 항목:
  1. 키 형식 (AIza로 시작 + 길이 39자)
  2. 공백·줄바꿈 포함 여부 (복사 사고)
  3. SDK 설치 여부
  4. 실제 API 호출 (models.list)
  5. 사용 가능한 모델 목록
"""
from __future__ import annotations

import os
import sys


def diagnose_key_format(key: str) -> list[str]:
    """키 형식 진단. issues 리스트 반환."""
    issues = []
    if not key:
        issues.append("키가 비어있음 — GEMINI_API_KEY env 미설정")
        return issues
    if key != key.strip():
        issues.append("키에 앞뒤 공백/줄바꿈 있음 — .strip() 필요")
    if not key.startswith("AIza"):
        issues.append(f"키가 'AIza'로 시작하지 않음 — 실제 시작: {key[:6]!r}")
    if len(key) < 35 or len(key) > 45:
        issues.append(f"키 길이 비정상 ({len(key)}자, 보통 39자)")
    if " " in key or "\n" in key or "\t" in key:
        issues.append("키 내부에 공백/탭/줄바꿈 — 복사 사고 의심")
    if key.startswith('"') or key.endswith('"'):
        issues.append("키가 따옴표로 감싸짐 — env 설정 시 따옴표 빼야 함")
    return issues


def try_new_sdk(key: str) -> tuple[bool, str, list[str]]:
    """신 SDK (google-genai) 시도."""
    try:
        from google import genai
    except ImportError:
        return False, "google-genai 미설치 (신 SDK)", []
    try:
        client = genai.Client(api_key=key)
        models = list(client.models.list())
        names = [m.name.replace("models/", "") for m in models][:10]
        return True, "google-genai (신 SDK) OK", names
    except Exception as e:
        return False, f"google-genai 호출 실패: {type(e).__name__}: {str(e)[:120]}", []


def try_old_sdk(key: str) -> tuple[bool, str, list[str]]:
    """구 SDK (google-generativeai) 시도 — FutureWarning 발생."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        try:
            import google.generativeai as gen_old
        except ImportError:
            return False, "google-generativeai 미설치 (구 SDK)", []
        try:
            gen_old.configure(api_key=key)
            models = list(gen_old.list_models())
            names = [m.name.replace("models/", "") for m in models][:10]
            return True, "google-generativeai (구 SDK, deprecated) OK", names
        except Exception as e:
            return False, f"google-generativeai 호출 실패: {type(e).__name__}: {str(e)[:120]}", []


def mask_key(key: str) -> str:
    if not key:
        return "(empty)"
    if len(key) < 10:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-4:]} ({len(key)}자)"


def main() -> int:
    # 인자 우선, 그 다음 env
    key = ""
    if len(sys.argv) > 1:
        key = sys.argv[1].strip()
    else:
        key = os.environ.get("GEMINI_API_KEY", "").strip()

    print("=" * 60)
    print("Gemini API 키 검증")
    print("=" * 60)
    print(f"키 (마스킹): {mask_key(key)}")
    print()

    # 1. 형식 검증
    print("[1/3] 키 형식 검증")
    issues = diagnose_key_format(key)
    if not issues:
        print("  [OK] 형식 정상")
    else:
        print("  [WARN] 다음 의심 사항:")
        for i in issues:
            print(f"    - {i}")
    print()

    if not key:
        print("키 미입력으로 종료. 다음 중 하나로 키 제공:")
        print('  $env:GEMINI_API_KEY = "AIzaSy..."')
        print('  python check_gemini_key.py "AIzaSy..."')
        return 1

    # 2. 신 SDK 시도
    print("[2/3] 신 SDK (google-genai) 시도")
    ok_new, msg_new, models_new = try_new_sdk(key)
    print(f"  {'[OK]' if ok_new else '[FAIL]'} {msg_new}")
    if models_new:
        print(f"  사용 가능 모델 (top 10): {', '.join(models_new[:5])}{'...' if len(models_new) > 5 else ''}")
    print()

    # 3. 구 SDK 시도
    print("[3/3] 구 SDK (google-generativeai) 시도")
    ok_old, msg_old, models_old = try_old_sdk(key)
    print(f"  {'[OK]' if ok_old else '[FAIL]'} {msg_old}")
    if models_old:
        print(f"  사용 가능 모델 (top 10): {', '.join(models_old[:5])}{'...' if len(models_old) > 5 else ''}")
    print()

    # 종합 결과
    print("=" * 60)
    if ok_new or ok_old:
        print("[성공] 키 유효 — 실 Gemini 호출 가능")
        if ok_new:
            print("  권장: 신 SDK 사용 (FutureWarning 없음)")
        else:
            print("  주의: 구 SDK만 동작 — pip install google-genai 권장")
        print()
        print("다음 단계:")
        print('  $env:FORCE_MOCK = "false"')
        print('  python -X utf8 ml_service\\scripts\\test_gemini_e2e.py --cases 10 --gap 2')
        return 0
    else:
        print("[실패] 키 거절됨 — 가능한 원인:")
        print("  1. 키 자체 무효 (오타·잘못된 프로젝트)")
        print("     → https://aistudio.google.com/apikey 에서 새로 발급")
        print("  2. SDK 미설치")
        print("     → pip install google-genai  (또는 google-generativeai)")
        print("  3. 네트워크 차단 (학교 방화벽)")
        print("     → 핸드폰 핫스팟에서 재시도")
        print("  4. 키 복사 시 따옴표·공백 포함")
        print('     → 따옴표 빼고 정확히 입력: $env:GEMINI_API_KEY = "AIzaSy..."')
        return 2


if __name__ == "__main__":
    sys.exit(main())
