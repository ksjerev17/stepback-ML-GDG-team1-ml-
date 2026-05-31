"""Quota 6 시나리오 — CLAUDE.md §11.2."""
from __future__ import annotations

import time

import pytest

from app.infra.quota_manager import (
    QuotaExceededError,
    QuotaManager,
    QuotaScope,
)


@pytest.mark.unit
def test_first_call_allowed() -> None:
    qm = QuotaManager()
    qm.check_and_increment("u1")


@pytest.mark.unit
def test_minute_limit_blocks_second_call() -> None:
    """v9.5: 일 1회 정책 — 두 번째 호출 즉시 거절."""
    qm = QuotaManager()
    qm.check_and_increment("u1")
    with pytest.raises(QuotaExceededError) as exc:
        qm.check_and_increment("u1")
    assert exc.value.scope == "minute"


@pytest.mark.unit
def test_different_users_isolated() -> None:
    qm = QuotaManager()
    qm.check_and_increment("u1")
    qm.check_and_increment("u2")


@pytest.mark.unit
def test_retry_after_seconds_positive() -> None:
    """v9.5: 1회 후 거절 + retry_after_seconds 양수."""
    qm = QuotaManager()
    qm.check_and_increment("u1")
    try:
        qm.check_and_increment("u1")
    except QuotaExceededError as e:
        assert e.retry_after_seconds > 0
    else:
        pytest.fail("expected QuotaExceededError")


@pytest.mark.unit
def test_hour_limit_after_three_in_hour() -> None:
    # 분 한도 우회: 1초 한도로 분 scope, 하지만 시 scope=3
    custom = (
        QuotaScope("minute", 1, 99),
        QuotaScope("hour", 3600, 3),
        QuotaScope("day", 86400, 99),
    )
    qm = QuotaManager(scopes=custom)
    qm.check_and_increment("u1")
    qm.check_and_increment("u1")
    qm.check_and_increment("u1")
    with pytest.raises(QuotaExceededError) as exc:
        qm.check_and_increment("u1")
    assert exc.value.scope == "hour"


@pytest.mark.unit
def test_usage_returns_counts() -> None:
    qm = QuotaManager()
    qm.check_and_increment("u1")
    usage = qm.usage("u1")
    assert usage["minute"] == 1
    assert usage["hour"] == 1
    assert usage["day"] == 1


@pytest.mark.unit
def test_reset_clears() -> None:
    qm = QuotaManager()
    qm.check_and_increment("u1")
    qm.reset("u1")
    qm.check_and_increment("u1")  # should not raise
