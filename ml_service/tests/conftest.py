"""테스트 공통 fixture + sys.path 설정."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_quota():
    """각 테스트가 quota 없이 시작."""
    from app.infra.quota_manager import get_quota_manager
    qm = get_quota_manager()
    qm.reset()
    yield
    qm.reset()


@pytest.fixture
def mock_llm():
    from app.infra.llm_client import LLMClient
    return LLMClient(force_mock=True)


@pytest.fixture
def base_context() -> dict:
    return {
        "self_condition": 3,
        "sleep_hours": 7.0,
        "social_today": "보통",
        "exercise_today": 0.0,
    }


@pytest.fixture
def zero_label() -> dict:
    """모든 신호 0인 라벨 결과 — 약신호 분기 테스트용."""
    from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO
    from datetime import datetime, timezone
    return {
        "patterns": {k: 0.0 for k in PATTERNS_KO},
        "behaviors": {k: 0.0 for k in BEHAVIORS_KO},
        "emotions": {k: 0.0 for k in EMOTIONS_KO} | {"중립": 0.9},
        "intensity": 0.1,
        "confidence": 0.4,
        "evidence_span": "",
        "crisis_detected": False,
        "calendar_dominant": "weak_signal_positive",
        "model_used": "mock",
        "labeled_at": datetime.now(timezone.utc).isoformat(),
    }


def make_label(
    patterns: dict | None = None,
    behaviors: dict | None = None,
    crisis: bool = False,
    evidence: str = "",
) -> dict:
    from app.schemas.common import BEHAVIORS_KO, EMOTIONS_KO, PATTERNS_KO
    from datetime import datetime, timezone
    p = {k: 0.0 for k in PATTERNS_KO}
    if patterns:
        p.update(patterns)
    b = {k: 0.0 for k in BEHAVIORS_KO}
    if behaviors:
        b.update(behaviors)
    return {
        "patterns": p,
        "behaviors": b,
        "emotions": {k: 0.0 for k in EMOTIONS_KO} | {"중립": 0.5},
        "intensity": 0.5,
        "confidence": 0.6,
        "evidence_span": evidence,
        "crisis_detected": crisis,
        "calendar_dominant": "cognitive_dominant" if patterns else "weak_signal_positive",
        "model_used": "mock",
        "labeled_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def make_label_fixture():
    return make_label
