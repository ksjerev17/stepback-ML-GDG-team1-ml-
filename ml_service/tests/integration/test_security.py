"""v9.4.3 보안 회귀 방지 테스트.

P0·P1·P2에서 잡은 보안 결함이 다시 들어오지 않도록 보호.

검증 영역:
- 위기 신호 우회 (영어/한국어/은유/띄어쓰기 우회)
- 빈 입력·이모지·반복문자 거절
- Context 4 필수
- 자가진단 정답 비노출
- ADMIN_TOKEN 강제
- /metrics·/healthz/detail 인증
- recent_drill_ids 크기 제한
- PII 마스킹 후 audit log에 평문 없음
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================================
# 위기 신호 우회 — P0
# ============================================================================

class TestCrisisBypass:
    """위기 신호 우회 시도가 모두 감지되는지 — 회귀 방지."""

    @pytest.mark.integration
    @pytest.mark.parametrize("text,should_detect", [
        # 한국어 직접
        ("더 이상 살고 싶지 않아", True),
        ("죽고 싶어", True),
        ("자해 생각이 자꾸 들어", True),
        # 영어
        ("I want to die", True),
        ("I think about killing myself", True),
        ("I wish I was dead", True),
        ("There is no point living", True),
        # 띄어쓰기 우회
        ("죽 고 싶 어", True),
        ("사 라 지 고 싶 어", True),
        # 은유
        ("사라지면 좋겠다는 생각이 자꾸 든다", True),
        ("다 끝내고 싶어", True),
        ("포기하고 싶어", True),
        # 위기 아님 (false positive 없는지)
        ("내일 발표 망할 것 같아", False),
        ("오늘 시험 망쳤어", False),
        ("좀 우울하지만 괜찮아", False),
    ])
    def test_crisis_detection(self, text: str, should_detect: bool) -> None:
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/label", json={"text": text, "user_id": "u_crisis_test"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["crisis_detected"] == should_detect, (
            f"text='{text}' expected crisis={should_detect}, got {body['crisis_detected']}"
        )


# ============================================================================
# 입력 검증 — P0
# ============================================================================

class TestInputValidation:
    """공백·이모지·반복문자 등 의미없는 입력 거절."""

    @pytest.mark.integration
    @pytest.mark.parametrize("text", [
        "    ",
        "\t\n\t  ",
        "😭😭😭😭😭",
        "...@#$%^&*",
        "ㅋ" * 50,
        "aaaaaaaa",
    ])
    def test_meaningless_input_rejected(self, text: str) -> None:
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/label", json={"text": text, "user_id": "u_input_test"})
        assert resp.status_code == 422, f"text={text!r} should be 422 but got {resp.status_code}"

    @pytest.mark.integration
    @pytest.mark.parametrize("text", [
        "내일 발표 망할 것 같아",
        "😭 너무 우울해",  # 이모지 + 텍스트는 OK
        "ㅠ ㅠ 시험 망쳤다",  # 반복문자 + 텍스트는 OK
    ])
    def test_meaningful_input_passes(self, text: str) -> None:
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/label", json={"text": text, "user_id": "u_input_pass"})
        assert resp.status_code == 200


# ============================================================================
# Context 4 필수 — P0
# ============================================================================

class TestContextRequired:
    @pytest.mark.integration
    def test_empty_context_rejected(self, base_context, zero_label) -> None:
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/recommend", json={
            "label_result": zero_label,
            "context": {},
            "user_id": "u_ctx",
        })
        assert resp.status_code == 422

    @pytest.mark.integration
    @pytest.mark.parametrize("ctx", [
        {"self_condition": 3},
        {"self_condition": 3, "sleep_hours": 7},
        {"self_condition": 3, "sleep_hours": 7, "social_today": "보통"},
    ])
    def test_partial_context_rejected(self, ctx, zero_label) -> None:
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/recommend", json={
            "label_result": zero_label,
            "context": ctx,
            "user_id": "u_ctx_partial",
        })
        assert resp.status_code == 422


# ============================================================================
# 자가진단 정답 비노출 — P0
# ============================================================================

class TestQuizAnswerHidden:
    @pytest.mark.integration
    def test_correct_value_not_in_response(self) -> None:
        resp = client.get("/weekly", params={"user_id": "u_quiz", "week": "2026-W21"})
        assert resp.status_code == 200
        quiz = resp.json().get("self_check_quiz", {})
        assert "correct_value" not in quiz
        assert "actual_ratio_percent" not in quiz
        # 응답 전체 문자열에도 노출 X
        body_text = resp.text
        # quiz options에 정답이 후보로 들어있는 건 OK — 하지만 별도 필드는 X
        assert '"correct_value"' not in body_text
        assert '"actual_ratio_percent"' not in body_text


# ============================================================================
# ADMIN 보안 — P1
# ============================================================================

class TestAdminSecurity:
    @pytest.mark.integration
    def test_metrics_without_token_blocked(self) -> None:
        resp = client.get("/metrics")
        assert resp.status_code in (403, 503), (
            f"/metrics must require ADMIN_TOKEN, got {resp.status_code}"
        )

    @pytest.mark.integration
    def test_healthz_detail_without_token_blocked(self) -> None:
        resp = client.get("/healthz/detail")
        assert resp.status_code in (403, 503)

    @pytest.mark.integration
    def test_admin_quota_reset_without_token_blocked(self) -> None:
        resp = client.post("/admin/quota/reset", json="u_x")
        assert resp.status_code in (403, 503)


# ============================================================================
# DoS 보호 — P1
# ============================================================================

class TestDosProtection:
    @pytest.mark.integration
    def test_huge_recent_drill_ids_rejected(self, base_context, zero_label) -> None:
        """recent_drill_ids 최대 20개. 50개 보내면 거절."""
        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()
        resp = client.post("/recommend", json={
            "label_result": zero_label,
            "context": base_context,
            "user_id": "u_dos",
            "recent_drill_ids": [f"d{i}" for i in range(50)],
        })
        assert resp.status_code == 422


# ============================================================================
# Audit log 평문 누출 X — P0 (기존)
# ============================================================================

class TestAuditLogNoPlaintext:
    @pytest.mark.integration
    def test_audit_log_does_not_contain_user_text(self, tmp_path, monkeypatch) -> None:
        """audit log에 평문 텍스트가 들어가지 않는지."""
        from app.config import LOGS_DIR
        # 새 로그 디렉토리로 격리
        new_logs = tmp_path / "logs"
        monkeypatch.setattr("app.infra.audit_log.LOGS_DIR", new_logs)

        from app.infra.quota_manager import get_quota_manager
        get_quota_manager().reset()

        unique_text = "고유한_텍스트_조각_xyz123"
        client.post("/label", json={"text": f"{unique_text} 어쩌고", "user_id": "u_audit"})

        # 로그 파일이 생성됐는지 + 그 안에 평문 없는지
        log_files = list(new_logs.glob("audit-*.jsonl"))
        if log_files:
            content = log_files[0].read_text(encoding="utf-8")
            assert unique_text not in content, (
                f"audit log contains plaintext: {unique_text}"
            )


# ============================================================================
# Mock 정직성 — P0
# ============================================================================

class TestMockHonesty:
    @pytest.mark.integration
    def test_healthz_exposes_mock_notice(self) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert "is_mock" in body
        if body["is_mock"]:
            assert body.get("mock_notice") is not None
            assert "Mock" in body["mock_notice"]
