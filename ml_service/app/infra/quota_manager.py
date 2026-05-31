# 출처: CLAUDE.md §11.2, §4.13
"""사용자별 호출량 제한 — 분 1 / 시 3 / 일 3."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class QuotaScope:
    name: str
    window_seconds: int
    limit: int


# v9.5: 정책 변경 — 하루 1회 입력 / 1회 LLM / 1드릴 추천.
# 깊은 자기 발견 도구로 전환. Step Back "한 발 물러서기"의 의미 강화.
SCOPES: tuple[QuotaScope, ...] = (
    QuotaScope("minute", 60, 1),
    QuotaScope("hour", 3600, 1),
    QuotaScope("day", 86400, 1),
)


class QuotaExceededError(Exception):
    def __init__(self, scope: str, limit: int, retry_after_seconds: int) -> None:
        super().__init__(f"quota exceeded ({scope}, limit={limit})")
        self.scope = scope
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds


class QuotaManager:
    """user_id별 호출 timestamp 큐 — thread-safe."""

    def __init__(self, scopes: tuple[QuotaScope, ...] = SCOPES) -> None:
        self._scopes = scopes
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _now(self) -> float:
        return time.time()

    def _purge(self, q: deque[float], now: float) -> None:
        max_window = max(s.window_seconds for s in self._scopes)
        while q and q[0] < now - max_window:
            q.popleft()

    def check_and_increment(self, user_id: str, endpoint: str = "label") -> None:
        now = self._now()
        with self._lock:
            q = self._calls[user_id]
            self._purge(q, now)
            for scope in self._scopes:
                count_in_window = sum(1 for t in q if t >= now - scope.window_seconds)
                if count_in_window >= scope.limit:
                    oldest = next((t for t in q if t >= now - scope.window_seconds), now)
                    retry_after = int(scope.window_seconds - (now - oldest)) + 1
                    raise QuotaExceededError(scope.name, scope.limit, max(retry_after, 1))
            q.append(now)

    def usage(self, user_id: str) -> dict[str, int]:
        now = self._now()
        with self._lock:
            q = self._calls.get(user_id, deque())
            return {
                s.name: sum(1 for t in q if t >= now - s.window_seconds)
                for s in self._scopes
            }

    def reset(self, user_id: str | None = None) -> None:
        with self._lock:
            if user_id is None:
                self._calls.clear()
            else:
                self._calls.pop(user_id, None)


_default_manager: QuotaManager | None = None


def get_quota_manager() -> QuotaManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = QuotaManager()
    return _default_manager
