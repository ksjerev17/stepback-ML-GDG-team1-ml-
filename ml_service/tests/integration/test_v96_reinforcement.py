# 출처: v9.6 강화 — 회귀·엣지케이스 테스트.
"""기존 기능 강화(할인 UCB 감쇠 / always-drill 보장 / 경향 신뢰도 / 최소표본 가드 /
월간 코칭 / 추천 견고성)에 대한 테스트."""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.core import personalization as pz
from app.core import weekly_coaching as wc
from app.core.recommender import recommend
from app.infra.audit_log import hash_user_id


_CTX = {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}


def _label(patterns=None, behaviors=None, emotions=None, evidence=None, conf=0.6, crisis=False):
    return {"patterns": patterns or {}, "behaviors": behaviors or {},
            "emotions": emotions or {"중립": 0.5}, "evidence_span": evidence,
            "confidence": conf, "crisis_detected": crisis}


# ── 할인 UCB 감쇠(recency) ───────────────────────────────────────────────

@pytest.mark.unit
def test_decay_factor_monotonic() -> None:
    now = datetime(2026, 5, 28, tzinfo=timezone.utc)
    f0 = pz._decay_factor(now.isoformat(), now)
    f_recent = pz._decay_factor((now - timedelta(days=1)).isoformat(), now)
    f_old = pz._decay_factor((now - timedelta(days=60)).isoformat(), now)
    assert abs(f0 - 1.0) < 1e-6
    assert f0 >= f_recent > f_old > 0.0
    # 반감기(21일)에서 약 0.5
    f_half = pz._decay_factor((now - timedelta(days=21)).isoformat(), now)
    assert abs(f_half - 0.5) < 0.05


@pytest.mark.unit
def test_old_offers_decay(tmp_path) -> None:
    """오래된 노출은 감쇠되어 effective count가 줄어든다."""
    db = tmp_path / "p.db"
    uh = hash_user_id("u_decay")
    # 60일 전 타임스탬프로 행을 직접 심음 (n_offered=10)
    pz._ensure(db)
    with sqlite3.connect(db) as conn:
        old = (datetime.now(timezone.utc) - timedelta(days=63)).isoformat()
        conn.execute(
            "INSERT INTO category_stats (user_hash,category,n_offered,n_completed,n_helpful,n_rejected,reward_sum,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (uh, "grounding", 10.0, 0, 0, 0, 0.0, old),
        )
    # 새 노출 1회 → 기존 10회가 ~1/8로 감쇠된 뒤 +1
    pz.record_offer("u_decay", "grounding", db_path=db)
    prof = pz.get_profile("u_decay", db_path=db)
    g = next(c for c in prof["categories"] if c["category"] == "grounding")
    assert g["n_offered"] < 5  # 10회였지만 감쇠로 대폭 축소


# ── always-drill 보장 ────────────────────────────────────────────────────

@pytest.mark.unit
def test_always_drill_even_if_many_rejected() -> None:
    """대부분의 드릴을 거부해도 항상 드릴을 반환 (ask_user/skip 아님)."""
    from app.core import drill_catalog
    all_ids = [d["id"] for d in drill_catalog.get_drills()]
    out = recommend(
        label_result=_label(patterns={"미래예측": 0.7}),
        context=_CTX, user_id="u_rej",
        rejected_drill_ids=all_ids[:-1],  # 거의 다 거부
        rng=random.Random(0),
    )
    assert out["type"] == "drill"


@pytest.mark.unit
def test_no_crash_on_empty_label() -> None:
    """빈 label_result로도 깨지지 않고 드릴/크라이시스만 반환."""
    out = recommend(label_result={}, context=_CTX, user_id="u_empty", rng=random.Random(0))
    assert out["type"] in ("drill", "crisis_card")


@pytest.mark.unit
def test_no_crash_on_partial_context() -> None:
    out = recommend(label_result=_label(emotions={"불안": 0.7, "중립": 0.0}),
                    context={"self_condition": 2}, user_id="u_pc", rng=random.Random(0))
    assert out["type"] == "drill"


# ── 경향 신뢰도 라벨 + 최소표본 가드 ──────────────────────────────────────

def _entry(off, cond, sleep=7.0, social="보통", ex=0.0, pat=None, emo=None, ev=None):
    base = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)
    return {"created_at": (base + timedelta(days=off)).isoformat(), "self_condition": cond,
            "context": {"sleep_hours": sleep, "social_today": social, "exercise_today": ex},
            "label_result": {"patterns": pat or {}, "behaviors": {}, "emotions": emo or {"중립": 0.5},
                             "evidence_span": ev},
            "calendar_dominant": "cognitive_dominant"}


@pytest.mark.unit
def test_tendency_confidence_labels() -> None:
    entries = [
        _entry(0, 3, 4.0, pat={"미래예측": 0.8}), _entry(1, 3, 4.5, pat={"미래예측": 0.7}),
        _entry(2, 3, 8.0, pat={"미래예측": 0.0}), _entry(3, 3, 8.0, pat={"미래예측": 0.0}),
    ]
    tends = wc.build_tendencies(entries)
    assert tends
    assert all(t["strength"] in ("뚜렷한 관찰", "관찰", "약한 관찰") for t in tends)


@pytest.mark.unit
def test_min_sample_guard_single_day() -> None:
    """단 하루만 수면 부족이면 sleep_pattern 경향을 만들지 않는다 (잡음 방지)."""
    entries = [
        _entry(0, 3, 4.0, pat={"미래예측": 0.9}),   # 부족 1일
        _entry(1, 3, 8.0, pat={"미래예측": 0.0}),
        _entry(2, 3, 8.0, pat={"미래예측": 0.0}),
        _entry(3, 3, 8.0, pat={"미래예측": 0.0}),
    ]
    tends = wc.build_tendencies(entries)
    assert "sleep_pattern" not in {t["kind"] for t in tends}


# ── 월간 코칭 ────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_monthly_report_has_coaching() -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.get("/monthly", params={"user_id": "u_m", "month": "2026-05"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "monthly_coaching" in body


# ── 안전: 위기 텍스트는 LLM(실 Gemini) 호출 전에 차단 ──────────────────────

@pytest.mark.unit
def test_crisis_never_calls_llm() -> None:
    """실 LLM 모드라도 위기 텍스트는 _generate 호출 없이 즉시 차단."""
    from app.infra.llm_client import LLMClient
    c = LLMClient(force_mock=True)
    # 강제로 '실 LLM처럼' 보이게 만들고, 호출되면 실패하도록 _generate를 폭탄으로 교체
    c._force_mock = False
    c._gemini = object()      # is_mock=False 되도록
    c._sdk_kind = "new"

    def _boom(*a, **k):
        raise AssertionError("위기 텍스트인데 LLM이 호출됨! (외부 전송 위험)")

    c._generate = _boom  # type: ignore
    out = c.label("죽고 싶어")
    assert out["crisis_detected"] is True
    assert out["_model_used"] == "crisis_preblock"


@pytest.mark.unit
def test_noncrisis_real_mode_would_call_llm() -> None:
    """대조군: 위기 아닌 텍스트는 실 모드에서 _generate를 실제로 호출한다."""
    from app.infra.llm_client import LLMClient
    c = LLMClient(force_mock=True)
    c._force_mock = False
    c._gemini = object()
    c._sdk_kind = "new"
    called = {"n": 0}

    def _fake(*a, **k):
        called["n"] += 1
        return '{"patterns":{},"behaviors":{},"emotions":{"중립":1.0},"intensity":0.1,"confidence":0.5,"evidence_span":"","crisis_detected":false}'

    c._generate = _fake  # type: ignore
    c.label("오늘 그냥 평범했어")
    assert called["n"] == 1


# ── v9.7: 사용자 화면 품질 (효용성·신뢰성·가독성) ──────────────────────────

@pytest.mark.unit
def test_why_has_benefit_and_mechanism() -> None:
    """모든 드릴 추천의 why에 효용성(benefit)+근거(mechanism)가 채워진다."""
    out = recommend(
        label_result=_label(patterns={"미래예측": 0.7}, evidence="망할 것 같아"),
        context={**_CTX, "sleep_hours": 4.0, "self_condition": 2},
        user_id="u_b", rng=random.Random(0),
    )
    w = out["why"]
    assert w["expected_benefit"] and len(w["expected_benefit"]) > 5
    assert w["mechanism"] and "기반" in w["mechanism"]


@pytest.mark.unit
def test_why_factor_detail_is_human_readable() -> None:
    """factor detail에 원점수(0.75)가 아니라 자연어 강도가 표시된다."""
    out = recommend(
        label_result=_label(patterns={"미래예측": 0.75}),
        context=_CTX, user_id="u_h", rng=random.Random(0),
    )
    sig = [f for f in out["why"]["factors"] if f["kind"] == "pattern"]
    assert sig, "패턴 factor가 있어야 함"
    f = sig[0]
    assert f["detail"] in ("자주", "여러 번", "조금", "약간")
    assert f.get("score_raw") == 0.75   # 원점수는 분리 보관
