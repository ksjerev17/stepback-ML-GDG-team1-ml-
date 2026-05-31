# 출처: CLAUDE.md §17.1
"""시연 직전 자가 점검 5항목."""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import LOGS_DIR, REPO_ROOT, should_force_mock  # noqa: E402
from app.core.drill_catalog import total_drills  # noqa: E402
from app.infra.quota_manager import get_quota_manager  # noqa: E402


def check_force_mock_state() -> tuple[bool, str]:
    mock = should_force_mock()
    if mock:
        return True, "FORCE_MOCK=true (Mock 응답) — 시연은 가능. 실 LLM 미사용 안내 권장."
    return True, "FORCE_MOCK=false — 실 LLM 호출 가능"


def check_drills_loaded() -> tuple[bool, str]:
    n = total_drills()
    return (n == 77, f"드릴 로드: {n}개 (기대 77)")


def check_quota_room() -> tuple[bool, str]:
    qm = get_quota_manager()
    usage = qm.usage("u_demo")
    return (True, f"u_demo 현재 사용량: minute={usage['minute']} hour={usage['hour']} day={usage['day']}")


def check_logs_dir_writable() -> tuple[bool, str]:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    test = LOGS_DIR / "_writable_test.tmp"
    try:
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return True, f"logs/ 쓰기 가능 ({LOGS_DIR})"
    except OSError as e:
        return False, f"logs/ 쓰기 실패: {e}"


def check_env_not_leaked() -> tuple[bool, str]:
    env = REPO_ROOT / ".env"
    if not env.exists():
        return True, ".env 미생성 (Mock 폴백)"
    # .env가 .gitignore에 명시되어야 함
    gi = REPO_ROOT / ".gitignore"
    if gi.exists() and ".env" in gi.read_text(encoding="utf-8"):
        return True, ".env 존재 + .gitignore 포함"
    return False, ".env 존재 — .gitignore에 추가 필요"


CHECKS = [
    ("1. FORCE_MOCK 상태", check_force_mock_state),
    ("2. 드릴 카탈로그", check_drills_loaded),
    ("3. Quota 여유", check_quota_room),
    ("4. logs/ 쓰기 권한", check_logs_dir_writable),
    ("5. .env 누출 여부", check_env_not_leaked),
]


def main() -> int:
    fails = 0
    print("[pre_demo_check]")
    for name, fn in CHECKS:
        ok, msg = fn()
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {msg}")
        if not ok:
            fails += 1
    print()
    if fails == 0:
        print("[pre_demo_check] 5/5 PASS - ready to demo")
        return 0
    print(f"[pre_demo_check] {fails} FAIL - fix before demo")
    return 1


if __name__ == "__main__":
    sys.exit(main())
