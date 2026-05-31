"""운영 보강 — /healthz/detail, /metrics, /admin/quota/reset, /clarify, request_id, CORS."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.integration
def test_request_id_added_to_response_header() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")
    assert len(resp.headers["X-Request-ID"]) >= 8


@pytest.mark.integration
def test_request_id_echoed_when_provided() -> None:
    rid = "test-rid-12345678"
    resp = client.get("/healthz", headers={"X-Request-ID": rid})
    assert resp.headers["X-Request-ID"] == rid


@pytest.mark.integration
def test_healthz_detail() -> None:
    """v9.4.3: /healthz/detail은 ADMIN_TOKEN 필요."""
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        pytest.skip("ADMIN_TOKEN not set in env")
    resp = client.get("/healthz/detail", headers={"X-Admin-Token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["drills_loaded"] == 100
    assert body["catalog_version"] == "v6.4"
    assert body["spec_version"] == "v9.4.3"
    assert "primary_model" in body


@pytest.mark.integration
def test_healthz_detail_blocks_without_token() -> None:
    """v9.4.3: 토큰 없으면 403."""
    resp = client.get("/healthz/detail")
    assert resp.status_code in (403, 503)


@pytest.mark.integration
def test_metrics_text_endpoint() -> None:
    """v9.4.3: /metrics는 ADMIN_TOKEN 필요."""
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        pytest.skip("ADMIN_TOKEN not set in env")
    client.post("/label", json={"text": "내일 발표 망할 것 같아", "user_id": "u_metrics"})
    resp = client.get("/metrics", headers={"X-Admin-Token": token})
    assert resp.status_code == 200
    text = resp.text
    assert "label_request" in text


@pytest.mark.integration
def test_metrics_blocks_without_token() -> None:
    resp = client.get("/metrics")
    assert resp.status_code in (403, 503)


@pytest.mark.integration
def test_metrics_json_endpoint() -> None:
    """v9.4.3: /metrics/json도 ADMIN_TOKEN 필요."""
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        pytest.skip("ADMIN_TOKEN not set in env")
    resp = client.get("/metrics/json", headers={"X-Admin-Token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert "counters" in body


@pytest.mark.integration
def test_admin_quota_reset_requires_token() -> None:
    resp = client.post("/admin/quota/reset", json="u_x")
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["code"] == "INVALID_INPUT"


@pytest.mark.integration
def test_admin_quota_reset_with_token() -> None:
    """v9.4.3: ADMIN_TOKEN env 변수 사용."""
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        pytest.skip("ADMIN_TOKEN not set in env")
    resp = client.post(
        "/admin/quota/reset",
        json="u_reset",
        headers={"X-Admin-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"


@pytest.mark.integration
def test_clarify_mock_returns_valid_choice() -> None:
    """v9.4.3: Mock clarify는 prompt에 따라 A/B/C 다양 (이전엔 항상 'tie')."""
    resp = client.post(
        "/clarify",
        json={"text": "오늘 좀 그래", "candidate_a": "미래예측", "candidate_b": "자기비난"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # 선택은 candidate_a, candidate_b, 또는 tie 중 하나
    assert body["choice"] in ("미래예측", "자기비난", "tie")
    assert body["model_used"] == "mock"


@pytest.mark.integration
def test_validation_error_returns_structured_body() -> None:
    resp = client.post("/label", json={"text": "", "user_id": "u"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in body["detail"]


@pytest.mark.integration
def test_quota_429_returns_structured_body() -> None:
    """v9.4.3: 분당 3회 후 4번째 거절."""
    for i in range(3):
        client.post("/label", json={"text": f"test {i}", "user_id": "u_q_struct"})
    resp = client.post("/label", json={"text": "test 4", "user_id": "u_q_struct"})
    assert resp.status_code == 429
    body = resp.json()
    assert body["detail"]["code"] == "QUOTA_EXCEEDED"
    assert body["detail"]["scope"] == "minute"
    assert body["detail"]["retry_after_seconds"] > 0
