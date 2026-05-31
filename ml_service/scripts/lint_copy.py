# 출처: CLAUDE.md §2.3
"""금지 표현 검출 — pre-commit 훅용."""
from __future__ import annotations

import re
import sys
from pathlib import Path


# §2.3 표 — 정규식 그룹별
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"당신은\s*\w+\s*유형", "self_discovery: '당신은 X 유형' 금지"),
    (r"잘못된\s*생각", "self_discovery: '잘못된 생각' 금지"),
    (r"개선되었어요|좋아졌어요|성장했어요", "growth_judgment: 성장 판정 금지"),
    (r"(?<!자가\s)(?<!자가)진단(?!\s*퀴즈)|치료|환자|우울증|불안장애", "clinical: 임상 표현 금지"),
    (r"때문에|\w+로\s*인해\s+\w+", "causality: 인과 단정 표현 검토"),
    (r"꼭\s*~?\s*해야|반드시\s*해야|안\s*하면\s*안\s*돼", "pressure: 압박 표현 금지"),
    (r"맞췄어요|틀렸어요", "quiz_judgment: 맞춤·틀림 표현 금지"),
    (r"잘하고\s*있어요|파이팅|화이팅", "cheer: 응원·평가성 표현 금지"),
]

SKIP_PATHS_PARTS: tuple[str, ...] = (
    "w1",  # 읽기 전용 W1
    "tests",  # 테스트는 의도적으로 표현 사용
    "docs",  # 문서는 메타 텍스트
    "handoff",
    ".venv",
    "__pycache__",
    ".git",
)


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & set(SKIP_PATHS_PARTS))


def scan(root: Path) -> list[tuple[Path, int, str, str]]:
    """결과: (path, lineno, line, reason)."""
    findings: list[tuple[Path, int, str, str]] = []
    patterns = [(re.compile(p), msg) for p, msg in FORBIDDEN_PATTERNS]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".py", ".md", ".json", ".txt", ".html"):
            continue
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rx, msg in patterns:
                if rx.search(line):
                    findings.append((path, lineno, line.strip()[:120], msg))
    return findings


def main(argv: list[str] | None = None) -> int:
    import io
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    root_arg = (argv or sys.argv[1:])
    root = Path(root_arg[0]) if root_arg else Path.cwd()
    findings = scan(root)
    if not findings:
        print("[lint_copy] PASS - no forbidden expressions found")
        return 0
    print(f"[lint_copy] {len(findings)} hit(s)")
    for path, lineno, line, reason in findings:
        print(f"  {path}:{lineno}  {reason}\n    > {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
