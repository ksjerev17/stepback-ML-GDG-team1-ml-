"""auto_discovery 3 알고리즘 — 명세서 §8.4."""
from __future__ import annotations

import pytest

from app.core.auto_discovery import (
    context_pattern_correlation,
    discover_all,
    top_evidence_spans,
    top_helpful_drill,
)


@pytest.mark.integration
def test_top_evidence_spans() -> None:
    entries = [
        {"label_result": {"evidence_span": "망할 것 같아"}},
        {"label_result": {"evidence_span": "망할 것 같아"}},
        {"label_result": {"evidence_span": "다 내 탓"}},
        {"label_result": {"evidence_span": "다 내 탓"}},
        {"label_result": {"evidence_span": "다 내 탓"}},
        {"label_result": {"evidence_span": "이건 너무 길어서 발견 후보 아님"}},
    ]
    out = top_evidence_spans(entries, top_n=2)
    assert len(out) == 2
    assert out[0]["text"].startswith("이번 주 '다 내 탓'")
    assert out[0]["count"] == 3


@pytest.mark.integration
def test_context_pattern_correlation_detects_diff() -> None:
    entries = [
        {"context": {"sleep_hours": 4}, "label_result": {"patterns": {"미래예측": 0.7}}},
        {"context": {"sleep_hours": 5}, "label_result": {"patterns": {"미래예측": 0.6}}},
        {"context": {"sleep_hours": 8}, "label_result": {"patterns": {"미래예측": 0.1}}},
        {"context": {"sleep_hours": 8}, "label_result": {"patterns": {"미래예측": 0.2}}},
    ]
    card = context_pattern_correlation(entries, "미래예측", threshold=0.2)
    assert card is not None
    assert "잠 6시간 미만" in card["text"]
    assert card["delta"] >= 0.2


@pytest.mark.integration
def test_context_pattern_correlation_below_threshold() -> None:
    entries = [
        {"context": {"sleep_hours": 4}, "label_result": {"patterns": {"미래예측": 0.5}}},
        {"context": {"sleep_hours": 8}, "label_result": {"patterns": {"미래예측": 0.45}}},
    ]
    card = context_pattern_correlation(entries, "미래예측", threshold=0.2)
    assert card is None


@pytest.mark.integration
def test_top_helpful_drill() -> None:
    fb = [
        {"drill_id": "D01", "rating": "helpful"},
        {"drill_id": "D01", "rating": "helpful"},
        {"drill_id": "D01", "rating": "unhelpful"},
        {"drill_id": "D02", "rating": "unhelpful"},
        {"drill_id": "D02", "rating": "unhelpful"},
    ]
    card = top_helpful_drill(fb, min_count=2)
    assert card is not None
    assert card["drill_id"] == "D01"


@pytest.mark.integration
def test_discover_all_combines() -> None:
    entries = [
        {"context": {"sleep_hours": 4}, "label_result": {"patterns": {"미래예측": 0.7}, "evidence_span": "망할 것"}},
        {"context": {"sleep_hours": 4}, "label_result": {"patterns": {"미래예측": 0.6}, "evidence_span": "망할 것"}},
        {"context": {"sleep_hours": 8}, "label_result": {"patterns": {"미래예측": 0.1}, "evidence_span": "그래"}},
    ]
    fb = [{"drill_id": "D01", "rating": "helpful"}, {"drill_id": "D01", "rating": "helpful"}]
    cards = discover_all(entries, fb)
    assert len(cards) >= 2  # span + correlation 최소
