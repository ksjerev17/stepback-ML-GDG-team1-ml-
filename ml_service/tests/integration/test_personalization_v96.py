# 출처: v9.6 — 개인화 엔진·주간 코칭 테스트.
"""personalization (UCB1 적응 학습) + weekly_coaching (상태 추론·경향) 테스트.

격리: 각 테스트는 tmp_path SQLite를 db_path로 주입 → 사용자 데이터 오염 없음.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import personalization as pz
from app.core import weekly_coaching as wc
from app.main import app


client = TestClient(app)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "preferences.db"


# ============================================================================
# personalization — UCB1 적응 학습
# ============================================================================

@pytest.mark.unit
def test_cold_start_zero_bonus(db) -> None:
    """노출 0회 → 가산점 0 (콜드 스타트 안전)."""
    assert pz.ucb_bonus("u1", "grounding", db_path=db) == 0.0
    bm = pz.bonus_map("u1", db_path=db)
    assert all(v == 0.0 for v in bm.values())


@pytest.mark.unit
def test_offer_counting(db) -> None:
    pz.record_offer("u2", "grounding", db_path=db)
    pz.record_offer("u2", "grounding", db_path=db)
    prof = pz.get_profile("u2", db_path=db)
    assert prof["total_offers"] == 2
    g = next(c for c in prof["categories"] if c["category"] == "grounding")
    assert g["n_offered"] == 2


@pytest.mark.unit
def test_reward_helpful_beats_completed(db) -> None:
    """helpful(1.0) > completed-only(0.5) — 보상 추정 순서 보장."""
    pz.record_offer("u3", "grounding", db_path=db)
    pz.record_outcome("u3", "grounding", completed=True, helpful=True, db_path=db)
    pz.record_offer("u3", "habit_design", db_path=db)
    pz.record_outcome("u3", "habit_design", completed=True, helpful=False, db_path=db)
    r_help = pz.category_reward_estimate("u3", "grounding", db_path=db)
    r_comp = pz.category_reward_estimate("u3", "habit_design", db_path=db)
    assert r_help > r_comp


@pytest.mark.unit
def test_reject_lowers_reward(db) -> None:
    pz.record_offer("u4", "sleep_circadian", db_path=db)
    base = pz.category_reward_estimate("u4", "sleep_circadian", db_path=db)
    pz.record_reject("u4", "sleep_circadian", db_path=db)
    after = pz.category_reward_estimate("u4", "sleep_circadian", db_path=db)
    assert after < base


@pytest.mark.unit
def test_ucb_explores_untried_category(db) -> None:
    """한 카테고리만 많이 노출되면, 미시도 카테고리가 탐험 가산점을 받는다."""
    for _ in range(10):
        pz.record_offer("u5", "grounding", db_path=db)
    b_tried = pz.ucb_bonus("u5", "grounding", db_path=db)
    b_untried = pz.ucb_bonus("u5", "self_compassion", db_path=db)
    assert b_untried > b_tried  # 탐험 항이 미시도 쪽을 끌어올림


@pytest.mark.unit
def test_bonus_capped(db) -> None:
    """가산점은 BONUS_CAP을 넘지 않는다 (임상 라우팅 보호)."""
    for _ in range(50):
        pz.record_offer("u6", "grounding", db_path=db)
        pz.record_outcome("u6", "grounding", completed=True, helpful=True, db_path=db)
    assert pz.ucb_bonus("u6", "grounding", db_path=db) <= pz.BONUS_CAP


@pytest.mark.unit
def test_top_helpful_category(db) -> None:
    for _ in range(3):
        pz.record_offer("u7", "self_compassion", db_path=db)
        pz.record_outcome("u7", "self_compassion", completed=True, helpful=True, db_path=db)
    pz.record_offer("u7", "habit_design", db_path=db)
    top = pz.top_helpful_category("u7", db_path=db)
    assert top is not None
    assert top["category"] == "self_compassion"


@pytest.mark.unit
def test_reset_user(db) -> None:
    pz.record_offer("u8", "grounding", db_path=db)
    pz.reset_user("u8", db_path=db)
    assert pz.get_profile("u8", db_path=db)["total_offers"] == 0


# ============================================================================
# weekly_coaching — 상태 추론
# ============================================================================

def _entry(day_offset: int, *, cond: int, pattern: dict | None = None,
           emotions: dict | None = None, sleep: float = 7.0):
    base = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)  # 월요일
    dt = base + timedelta(days=day_offset)
    return {
        "created_at": dt.isoformat(),
        "self_condition": cond,
        "context": {"sleep_hours": sleep},
        "label_result": {
            "patterns": pattern or {},
            "behaviors": {},
            "emotions": emotions or {},
        },
        "calendar_dominant": "weak_signal_positive",
    }


@pytest.mark.unit
def test_state_insufficient_when_few_days() -> None:
    entries = [_entry(0, cond=3), _entry(1, cond=3)]
    st = wc.infer_state(entries)
    assert st["key"] == "observing"


@pytest.mark.unit
def test_state_recovery() -> None:
    # 전반 낮음(2) → 후반 높음(4)
    entries = [
        _entry(0, cond=2), _entry(1, cond=2), _entry(2, cond=2),
        _entry(3, cond=4), _entry(4, cond=4), _entry(5, cond=5), _entry(6, cond=4),
    ]
    st = wc.infer_state(entries)
    assert st["key"] == "recovery"


@pytest.mark.unit
def test_state_fatigue() -> None:
    entries = [
        _entry(0, cond=5), _entry(1, cond=4), _entry(2, cond=4),
        _entry(3, cond=2), _entry(4, cond=2), _entry(5, cond=2), _entry(6, cond=1),
    ]
    st = wc.infer_state(entries)
    assert st["key"] == "fatigue"


@pytest.mark.unit
def test_tendency_sleep_pattern() -> None:
    # 수면 부족 날엔 미래예측 높음, 충분한 날엔 낮음
    entries = [
        _entry(0, cond=3, sleep=4.0, pattern={"미래예측": 0.7}),
        _entry(1, cond=3, sleep=4.5, pattern={"미래예측": 0.6}),
        _entry(2, cond=3, sleep=8.0, pattern={"미래예측": 0.1}),
        _entry(3, cond=3, sleep=8.0, pattern={"미래예측": 0.0}),
    ]
    tends = wc.build_tendencies(entries)
    kinds = {t["kind"] for t in tends}
    assert "sleep_pattern" in kinds
    sp = next(t for t in tends if t["kind"] == "sleep_pattern")
    assert "미래예측" in sp["text"]


@pytest.mark.unit
def test_next_focus_safety_first_on_fatigue(db, monkeypatch) -> None:
    monkeypatch.setattr(pz, "PREFERENCES_DB", db)
    focus = wc.build_next_week_focus([], "u_f", state_key="fatigue", db_path=db)
    assert focus["category"] == "grounding"
    assert focus["source"] == "state"


@pytest.mark.unit
def test_next_focus_uses_weekly_signal(db) -> None:
    entries = [
        _entry(0, cond=3, pattern={"자기비난": 0.7}),
        _entry(1, cond=3, pattern={"자기비난": 0.6}),
        _entry(2, cond=3, pattern={"자기비난": 0.5}),
    ]
    focus = wc.build_next_week_focus(entries, "u_s", state_key="stable", db_path=db)
    assert focus["category"] == "cognitive_restructuring"
    assert focus["source"] == "weekly_signal"


@pytest.mark.unit
def test_next_focus_uses_personalization(db) -> None:
    # 약신호 주 + 학습된 선호 → personalization 소스
    for _ in range(3):
        pz.record_offer("u_p", "self_compassion", db_path=db)
        pz.record_outcome("u_p", "self_compassion", completed=True, helpful=True, db_path=db)
    focus = wc.build_next_week_focus([], "u_p", state_key="stable", db_path=db)
    assert focus["source"] == "personalization"
    assert focus["category"] == "self_compassion"


@pytest.mark.unit
def test_build_weekly_coaching_shape(db, monkeypatch) -> None:
    monkeypatch.setattr(pz, "PREFERENCES_DB", db)
    entries = [
        _entry(0, cond=2, sleep=4.0, pattern={"미래예측": 0.7}),
        _entry(1, cond=2, sleep=4.5, pattern={"미래예측": 0.6}),
        _entry(2, cond=2, sleep=5.0, pattern={"미래예측": 0.5}),
        _entry(3, cond=4, sleep=8.0, pattern={"미래예측": 0.1}),
        _entry(4, cond=4, sleep=8.0),
        _entry(5, cond=5, sleep=8.0),
        _entry(6, cond=4, sleep=7.5),
    ]
    out = wc.build_weekly_coaching(entries=entries, user_id="u_c", db_path=db)
    assert "state" in out and "next_week_focus" in out
    assert out["state"]["key"] in ("recovery", "stable", "loaded", "low", "fatigue", "turbulent")
    assert isinstance(out["tendencies"], list)


# ============================================================================
# integration — 엔드포인트
# ============================================================================

@pytest.mark.integration
def test_weekly_report_includes_coaching() -> None:
    resp = client.get("/weekly", params={"user_id": "u_wk", "week": "2026-W21"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "weekly_coaching" in body
    assert body["weekly_coaching"] is not None
    assert "state" in body["weekly_coaching"]
    assert "next_week_focus" in body["weekly_coaching"]


@pytest.mark.integration
def test_personalization_profile_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pz, "PREFERENCES_DB", tmp_path / "prefs.db")
    resp = client.get("/personalization/profile", params={"user_id": "u_pe"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_offers"] == 0
    assert len(body["categories"]) == 6


@pytest.mark.integration
def test_personalization_event_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pz, "PREFERENCES_DB", tmp_path / "prefs2.db")
    r1 = client.post("/personalization/event",
                     json={"user_id": "u_ev", "category": "grounding", "event": "offer"})
    assert r1.status_code == 200, r1.text
    r2 = client.post("/personalization/event",
                     json={"user_id": "u_ev", "category": "grounding", "event": "helpful"})
    assert r2.status_code == 200
    prof = client.get("/personalization/profile", params={"user_id": "u_ev"}).json()
    g = next(c for c in prof["categories"] if c["category"] == "grounding")
    assert g["n_helpful"] == 1


@pytest.mark.integration
def test_next_focus_endpoint() -> None:
    resp = client.get("/personalization/next_focus",
                      params={"user_id": "u_nf", "state_key": "fatigue"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["category"] == "grounding"


# ============================================================================
# v9.6 추가 — 설명가능 추천(why) + always-drill + 다변량 경향
# ============================================================================

import random as _random
from app.core.recommender import recommend as _recommend


def _label(patterns=None, behaviors=None, emotions=None, evidence=None, conf=0.6, crisis=False):
    return {
        "patterns": patterns or {}, "behaviors": behaviors or {},
        "emotions": emotions or {"중립": 0.5}, "evidence_span": evidence,
        "confidence": conf, "crisis_detected": crisis,
    }


_CTX = {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}


@pytest.mark.unit
def test_why_present_on_drill() -> None:
    out = _recommend(
        label_result=_label(patterns={"미래예측": 0.7}, evidence="망할 것 같아"),
        context={**_CTX, "sleep_hours": 4.0, "self_condition": 2},
        user_id="u_why", rng=_random.Random(0),
    )
    assert out["type"] == "drill"
    assert "why" in out and out["why"]["text"]
    # 근거 factor에 맥락·신호가 포함
    kinds = {f["kind"] for f in out["why"]["factors"]}
    assert "context" in kinds or "pattern" in kinds


@pytest.mark.unit
def test_why_text_natural_single_factor() -> None:
    out = _recommend(
        label_result=_label(emotions={"중립": 0.6}),
        context={**_CTX, "self_condition": 1, "sleep_hours": 3.0},
        user_id="u_why2", rng=_random.Random(0),
    )
    # 단일 요인이라도 자연스러운 종결 ("…서 이 드릴을 골랐어요.")
    assert out["why"]["text"].endswith("골랐어요.")


@pytest.mark.unit
def test_always_drill_no_ask_user() -> None:
    """경계선·약신호 어디서도 ask_user 안 나옴."""
    for lbl, ctx in (
        (_label(patterns={"자기비난": 0.35}, behaviors={"회피미루기": 0.32}), _CTX),
        (_label(emotions={"중립": 0.9}), {**_CTX, "self_condition": 5, "sleep_hours": 8.0}),
        (_label(emotions={"중립": 0.6}), {**_CTX, "self_condition": 2, "sleep_hours": 4.0}),
    ):
        out = _recommend(label_result=lbl, context=ctx, user_id="u_ad", rng=_random.Random(0))
        assert out["type"] in ("drill", "crisis_card")
        assert out["type"] != "ask_user"


@pytest.mark.unit
def test_positive_tone_on_calm_day() -> None:
    out = _recommend(
        label_result=_label(emotions={"중립": 0.9}),
        context={**_CTX, "self_condition": 5, "sleep_hours": 8.0, "social_today": "좋음"},
        user_id="u_pos", rng=_random.Random(0),
    )
    assert out["type"] == "drill"
    assert out["tone"] == "positive"


@pytest.mark.unit
def test_crisis_still_card() -> None:
    out = _recommend(label_result=_label(crisis=True), context=_CTX, user_id="u_cr", rng=_random.Random(0))
    assert out["type"] == "crisis_card"


@pytest.mark.unit
def test_tendencies_multivariable() -> None:
    """수면 점감 + 사교↔컨디션 + 맥락↔표현 등 다변량 경향이 잡힌다."""
    base = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)
    def E(off, cond, sleep, social, ex, pat=None, emo=None, ev=None):
        return {"created_at": (base + timedelta(days=off)).isoformat(),
                "self_condition": cond,
                "context": {"sleep_hours": sleep, "social_today": social, "exercise_today": ex},
                "label_result": {"patterns": pat or {}, "behaviors": {},
                                 "emotions": emo or {"중립": 0.5}, "evidence_span": ev},
                "calendar_dominant": "cognitive_dominant"}
    entries = [
        E(0, 4, 8.0, "좋음", 1.0, {"미래예측": 0.2}, ev="괜찮아"),
        E(1, 4, 7.5, "보통", 0.5, {"미래예측": 0.3}),
        E(2, 3, 6.5, "갈등", 0.0, {"자기비난": 0.4}, {"분노": 0.4, "중립": 0.2}, "다 내 탓"),
        E(3, 2, 5.5, "갈등", 0.0, {"미래예측": 0.6}, {"불안": 0.5, "중립": 0.1}, "망할 것 같아"),
        E(4, 2, 5.0, "보통", 0.0, {"미래예측": 0.6}, {"불안": 0.55, "중립": 0.1}, "망할 것 같아"),
        E(5, 3, 4.5, "보통", 0.5, {"미래예측": 0.5}),
        E(6, 4, 4.0, "좋음", 1.0, {"미래예측": 0.3}),
    ]
    tends = wc.build_tendencies(entries)
    kinds = {t["kind"] for t in tends}
    assert len(tends) >= 3
    assert "sleep_trend" in kinds            # 수면 점감
    assert "social_condition" in kinds or "social_emotion" in kinds  # 사교 관계
