"""감사 로그 — 평문 거부 + JSONL 기록."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import LOGS_DIR
from app.infra import audit_log


@pytest.mark.unit
def test_hash_user_id_format() -> None:
    h = audit_log.hash_user_id("u_demo")
    assert h.startswith("sha256:")
    assert len(h) >= 8


@pytest.mark.unit
def test_hash_is_deterministic() -> None:
    a = audit_log.hash_user_id("u_demo")
    b = audit_log.hash_user_id("u_demo")
    assert a == b


@pytest.mark.unit
def test_hash_differs_per_user() -> None:
    a = audit_log.hash_user_id("u_a")
    b = audit_log.hash_user_id("u_b")
    assert a != b


@pytest.mark.unit
def test_forbidden_field_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_log, "LOGS_DIR", tmp_path)
    audit_log.write(
        endpoint="label",
        user_hash=audit_log.hash_user_id("u_a"),
        text_len=10,
        extra={"text": "이것은 평문"},  # 거부 대상
    )
    files = list(tmp_path.glob("audit-*.jsonl"))
    assert files == [], "평문 필드 포함 시 기록되지 않아야 함"


@pytest.mark.unit
def test_normal_write_jsonl(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit_log, "LOGS_DIR", tmp_path)
    audit_log.write(
        endpoint="label",
        user_hash=audit_log.hash_user_id("u_a"),
        text_len=24,
        extra={"top_pattern": "미래예측", "top_pattern_score": 0.7},
    )
    files = list(tmp_path.glob("audit-*.jsonl"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["endpoint"] == "label"
    assert payload["text_len"] == 24
    assert payload["top_pattern"] == "미래예측"


@pytest.mark.unit
def test_summarize_label_no_evidence_span() -> None:
    summary = audit_log.summarize_label(
        {
            "patterns": {"미래예측": 0.7},
            "behaviors": {"회피미루기": 0.2},
            "confidence": 0.55,
            "crisis_detected": False,
            "evidence_span": "평문 들어가면 안 됨",
        }
    )
    assert "evidence_span" not in summary
    assert summary["top_pattern"] == "미래예측"
