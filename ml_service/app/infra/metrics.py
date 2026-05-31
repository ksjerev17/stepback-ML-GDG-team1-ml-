# 출처: 운영 보강
"""인메모리 운영 지표 — Prometheus 형식 textfmt."""
from __future__ import annotations

import threading
from collections import Counter, defaultdict
from time import perf_counter
from typing import Iterator


class Metrics:
    """단순 카운터 + 히스토그램. 외부 라이브러리 없이 동작."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[tuple[str, str]] = Counter()
        self._latency_ms_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._latency_count: Counter[tuple[str, str]] = Counter()

    def incr(self, name: str, label: str = "") -> None:
        with self._lock:
            self._counters[(name, label)] += 1

    def observe_latency(self, name: str, label: str, value_ms: float) -> None:
        with self._lock:
            self._latency_ms_sum[(name, label)] += value_ms
            self._latency_count[(name, label)] += 1

    def render(self) -> Iterator[str]:
        with self._lock:
            for (name, label), count in self._counters.items():
                yield f'{name}{{label="{label}"}} {count}'
            for (name, label), total in self._latency_ms_sum.items():
                n = self._latency_count[(name, label)]
                avg = total / max(n, 1)
                yield f'{name}_avg_ms{{label="{label}"}} {avg:.2f}'
                yield f'{name}_count{{label="{label}"}} {n}'

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": {f"{k[0]}|{k[1]}": v for k, v in self._counters.items()},
                "latency_avg_ms": {
                    f"{k[0]}|{k[1]}": round(self._latency_ms_sum[k] / max(self._latency_count[k], 1), 2)
                    for k in self._latency_ms_sum
                },
            }


_default = Metrics()


def get_metrics() -> Metrics:
    return _default


class Timer:
    """with Timer('label', 'success') as t: ... — perf_counter 자동."""

    def __init__(self, name: str, label: str = "ok") -> None:
        self.name = name
        self.label = label
        self._start = 0.0

    def __enter__(self) -> "Timer":
        self._start = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        ms = (perf_counter() - self._start) * 1000
        get_metrics().observe_latency(self.name, self.label if exc_type is None else "error", ms)
