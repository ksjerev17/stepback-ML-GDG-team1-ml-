"""v9.5 + Design 와이어프레임 호환 변경 통합 검증.

- POST /entries 통합 엔드포인트 (BE/ML context 양쪽 지원)
- drill_category + 한국어 라벨 + 캘린더 색
- POST/GET /insights/user_discovery
- 나의 발견 → 다음 추천 affinity 가산
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.recommender import _user_discovery_affinity_keys
from app.infra.quota_manager import get_quota_manager
from app.main import app


client = TestClient(app)


# ============================================================================
# POST /entries — BE 통합 엔드포인트
# ============================================================================

@pytest.mark.integration
def test_entries_be_format_context() -> None:
    """BE 명세 형식 (sleep:6, exercise:bool, condition:"bad") → 자동 매핑."""
    get_quota_manager().reset()
    r = client.post("/entries", json={
        "text": "내일 발표 망할 것 같아 진짜",
        "user_id": "u_be_format",
        "context": {"sleep": 6, "exercise": True, "condition": "bad", "meals": 2},
    })
    assert r.status_code == 200
    body = r.json()
    ctx = body["context_used"]
    assert ctx["sleep_hours"] == 6.0
    assert ctx["self_condition"] == 2  # "bad" → 2
    assert ctx["exercise_today"] == 0.5  # bool True → 0.5h
    assert ctx["social_today"] == "보통"  # 기본값


@pytest.mark.integration
def test_entries_ml_format_context() -> None:
    """ML 표준 형식도 그대로 동작."""
    get_quota_manager().reset()
    r = client.post("/entries", json={
        "text": "공부해야 하는데 자꾸 폰만 보게 돼",
        "user_id": "u_ml_format",
        "context": {"self_condition": 3, "sleep_hours": 7.5,
                    "social_today": "보통", "exercise_today": 0.5},
    })
    assert r.status_code == 200
    body = r.json()
    ctx = body["context_used"]
    assert ctx["self_condition"] == 3
    assert ctx["sleep_hours"] == 7.5


@pytest.mark.integration
def test_entries_returns_drill_category_metadata() -> None:
    """drill 추천 시 drill_category + 한국어 라벨 + 캘린더 색 응답."""
    get_quota_manager().reset()
    r = client.post("/entries", json={
        "text": "내일 발표 망할 것 같아 진짜 떨려",
        "user_id": "u_meta",
        "context": {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통"},
    })
    assert r.status_code == 200
    body = r.json()
    rec = body["recommendation"]
    if rec.get("type") == "drill":
        assert body["drill_category"] in (
            "cognitive_restructuring", "behavioral_activation", "habit_design",
            "grounding", "self_compassion", "sleep_circadian"
        )
        assert body["drill_category_label"] in (
            "생각 전환", "산책", "긍정 확언", "마음 챙김", "자기 자비", "수면 정돈"
        )
        assert body["drill_calendar_color"] is not None


@pytest.mark.integration
def test_entries_no_context_uses_defaults() -> None:
    """context 없이도 호출 가능 (기본값 적용)."""
    get_quota_manager().reset()
    r = client.post("/entries", json={
        "text": "오늘 평범한 하루였어",
        "user_id": "u_no_ctx",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["context_used"]["self_condition"] == 3
    assert body["context_used"]["sleep_hours"] == 7.0


# ============================================================================
# 나의 발견 — 저장 / 조회
# ============================================================================

@pytest.mark.integration
def test_post_user_discovery() -> None:
    r = client.post("/insights/user_discovery", json={
        "user_id": "u_disc_save",
        "week_of": "2026-W21",
        "discoveries": [
            "잠을 충분히 잔 날은 마음이 가벼워요",
            "감사한 일 한 가지 적는 게 도움이 돼요",
        ],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["saved_count"] == 2
    assert body["week_of"] == "2026-W21"


@pytest.mark.integration
def test_get_user_discoveries() -> None:
    # 저장 먼저
    client.post("/insights/user_discovery", json={
        "user_id": "u_disc_get",
        "week_of": "2026-W21",
        "discoveries": ["산책하면 기분이 좋아져요"],
    })
    r = client.get("/insights/user_discovery", params={"user_id": "u_disc_get"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert "산책" in " ".join(body["discoveries"])


@pytest.mark.integration
def test_user_discovery_empty_after_clean() -> None:
    """빈 문자열·공백만 → 저장 X."""
    r = client.post("/insights/user_discovery", json={
        "user_id": "u_disc_empty",
        "week_of": "2026-W21",
        "discoveries": ["   ", "    ", " "],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["saved_count"] == 0


# ============================================================================
# affinity 키 생성 — 키워드 매칭
# ============================================================================

@pytest.mark.integration
def test_affinity_sleep_keyword() -> None:
    keys = _user_discovery_affinity_keys(["잠을 충분히 잔 날은 마음이 가벼워요"])
    assert "category_sleep_circadian" in keys


@pytest.mark.integration
def test_affinity_self_compassion_keyword() -> None:
    keys = _user_discovery_affinity_keys(["감사한 일 한 가지 적는 게 도움이 돼요"])
    assert "category_self_compassion" in keys


@pytest.mark.integration
def test_affinity_multiple_categories() -> None:
    keys = _user_discovery_affinity_keys([
        "잠을 잘 잔 날 좋아요",
        "산책하면 기분이 풀려요",
    ])
    assert "category_sleep_circadian" in keys
    assert "category_behavioral_activation" in keys


@pytest.mark.integration
def test_affinity_empty_returns_empty() -> None:
    assert _user_discovery_affinity_keys([]) == set()
    assert _user_discovery_affinity_keys(None) == set()
