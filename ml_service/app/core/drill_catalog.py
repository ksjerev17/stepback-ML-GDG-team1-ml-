# 출처: CLAUDE.md §5.3, §6
"""드릴 카탈로그 로더 — drills_seed_v6_3.json 정본 사용."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import W1_DIR


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    # v6.4: 100개 정본 우선, 없으면 v6.3(77개)로 안전 폴백.
    for fname in ("drills_seed_v6_4.json", "drills_seed_v6_3.json"):
        path = W1_DIR / fname
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError("드릴 카탈로그 파일을 찾을 수 없습니다 (v6_4/v6_3)")


@lru_cache(maxsize=1)
def get_drills() -> list[dict[str, Any]]:
    return load_catalog().get("drills", [])


def get_drill(drill_id: int | str) -> dict[str, Any] | None:
    """v9.5: int 우선. legacy_id ("D01") 도 호환 — 마이그레이션 안전."""
    for d in get_drills():
        if d.get("id") == drill_id:
            return d
        # 옛 문자열 ID 매칭 (마이그레이션 호환)
        if isinstance(drill_id, str) and d.get("legacy_id") == drill_id:
            return d
    return None


def drills_by_category(category: str) -> list[dict[str, Any]]:
    return [d for d in get_drills() if d.get("category") == category]


def total_drills() -> int:
    return len(get_drills())
