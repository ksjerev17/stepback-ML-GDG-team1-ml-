# 출처: 명세서 §4.8, §8, §9.2, §9.3, §10.2
"""GET /weekly + 보조 엔드포인트.

엔드포인트:
- GET  /weekly           — 데모 entries 기반 5블록+확장 응답
- POST /weekly           — BE가 entries 전달하는 실 호출 경로
- PATCH /weekly/quiz     — 사용자 quiz 응답 저장 (메타인지 격차)
- POST /weekly/pattern_diff  — 이번 주 vs 지난 주 패턴 비교
- POST /weekly/condition_flow — 7일 컨디션 흐름
- POST /baseline/recompute   — 30일 baseline 갱신
- GET  /baseline             — 현재 baseline 조회 (학습 전용)
"""
from __future__ import annotations

import random
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query

from app.core import baselines, insights_store
from app.core.weekly_report import build_report, condition_flow, pattern_diff
from app.schemas.weekly import (
    ConditionFlow,
    PatternDiffRow,
    QuizAnswerRequest,
    QuizAnswerResponse,
    WeeklyReport,
)


router = APIRouter()


def _demo_entries() -> list[dict]:
    """v9.6: 다변량 경향이 살아나도록 7일치 풍부한 데모 주차.

    수면 점감(8→4), 갈등/좋음 사교 혼재, 운동 유무, 감정·evidence_span 포함.
    → sleep_trend / sleep_pattern / social_condition / exercise_condition /
      context_expression 등 여러 경향이 동시에 관찰됨.
    """
    return [
        {"created_at": "2026-05-18T09:00:00+00:00", "self_condition": 4,
         "context": {"sleep_hours": 8.0, "social_today": "좋음", "exercise_today": 1.0},
         "label_result": {"patterns": {"미래예측": 0.2}, "behaviors": {}, "emotions": {"중립": 0.7},
                          "evidence_span": "괜찮은 하루"},
         "calendar_dominant": "weak_signal_positive"},
        {"created_at": "2026-05-19T09:00:00+00:00", "self_condition": 4,
         "context": {"sleep_hours": 7.5, "social_today": "보통", "exercise_today": 0.5},
         "label_result": {"patterns": {"미래예측": 0.3}, "behaviors": {}, "emotions": {"불안": 0.2, "중립": 0.5},
                          "evidence_span": "조금 떨려"},
         "calendar_dominant": "cognitive_dominant"},
        {"created_at": "2026-05-20T09:00:00+00:00", "self_condition": 3,
         "context": {"sleep_hours": 6.5, "social_today": "갈등", "exercise_today": 0.0},
         "label_result": {"patterns": {"자기비난": 0.4}, "behaviors": {"회피미루기": 0.2},
                          "emotions": {"분노": 0.4, "우울": 0.2, "중립": 0.2}, "evidence_span": "다 내 탓"},
         "calendar_dominant": "emotion_anger"},
        {"created_at": "2026-05-21T09:00:00+00:00", "self_condition": 2,
         "context": {"sleep_hours": 5.5, "social_today": "갈등", "exercise_today": 0.0},
         "label_result": {"patterns": {"미래예측": 0.55, "자기비난": 0.3}, "behaviors": {"회피미루기": 0.4},
                          "emotions": {"불안": 0.5, "우울": 0.3, "중립": 0.1}, "evidence_span": "망할 것 같아"},
         "calendar_dominant": "emotion_anxiety"},
        {"created_at": "2026-05-22T09:00:00+00:00", "self_condition": 2,
         "context": {"sleep_hours": 5.0, "social_today": "보통", "exercise_today": 0.0},
         "label_result": {"patterns": {"미래예측": 0.6}, "behaviors": {"회피미루기": 0.5, "동기저하": 0.3},
                          "emotions": {"불안": 0.55, "중립": 0.1}, "evidence_span": "망할 것 같아"},
         "calendar_dominant": "behavior_dominant"},
        {"created_at": "2026-05-23T09:00:00+00:00", "self_condition": 3,
         "context": {"sleep_hours": 4.5, "social_today": "보통", "exercise_today": 0.5},
         "label_result": {"patterns": {"미래예측": 0.5}, "behaviors": {}, "emotions": {"불안": 0.4, "중립": 0.3},
                          "evidence_span": "걱정돼"},
         "calendar_dominant": "cognitive_dominant"},
        {"created_at": "2026-05-24T09:00:00+00:00", "self_condition": 4,
         "context": {"sleep_hours": 4.0, "social_today": "좋음", "exercise_today": 1.0},
         "label_result": {"patterns": {"미래예측": 0.3}, "behaviors": {}, "emotions": {"중립": 0.6},
                          "evidence_span": "한결 낫다"},
         "calendar_dominant": "weak_signal_positive"},
    ]


@router.get("/weekly", response_model=WeeklyReport)
def get_weekly(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
    week: Annotated[str, Query(pattern=r"^\d{4}-W\d{2}$")] = "2026-W21",
) -> WeeklyReport:
    entries = _demo_entries()
    raw = build_report(
        week=week,
        user_id=user_id,
        entries=entries,
        drills_recommended=12,
        drills_practiced=8,
        prev_week_avg=2.9,
        rng=random.Random(0),
    )
    return WeeklyReport.model_validate(raw)


@router.post("/weekly", response_model=WeeklyReport)
def post_weekly(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    week: Annotated[str, Body(pattern=r"^\d{4}-W\d{2}$")],
    entries: Annotated[list[dict], Body()],
    drills_recommended: Annotated[int, Body()] = 0,
    drills_practiced: Annotated[int, Body()] = 0,
    prev_week_avg: Annotated[float | None, Body()] = None,
    prev_entries: Annotated[list[dict] | None, Body()] = None,
    feedback_rows: Annotated[list[dict] | None, Body()] = None,
) -> WeeklyReport:
    raw = build_report(
        week=week,
        user_id=user_id,
        entries=entries,
        drills_recommended=drills_recommended,
        drills_practiced=drills_practiced,
        prev_week_avg=prev_week_avg,
        prev_entries=prev_entries,
        feedback_rows=feedback_rows,
    )
    return WeeklyReport.model_validate(raw)


@router.patch("/weekly/quiz", response_model=QuizAnswerResponse)
def patch_weekly_quiz(req: QuizAnswerRequest) -> QuizAnswerResponse:
    """사용자가 자가진단 퀴즈 응답 — 메타인지 격차 저장 (§8.2).

    v9.4.3: 정답은 server-side cache(self_check_quiz._quiz_answers)에서 lookup.
    응답에 노출되지 않은 정답을 cache에서 가져와 정오답 판정.
    """
    from app.core.self_check_quiz import get_cached_answer
    from app.core.weekly_report import build_report

    cached = get_cached_answer(req.user_id, req.week)
    if cached is None:
        # cache miss — GET /weekly 미호출 또는 cache expire. demo entries로 재계산.
        raw = build_report(
            week=req.week,
            user_id=req.user_id,
            entries=_demo_entries(),
        )
        cached = get_cached_answer(req.user_id, req.week)
        if cached is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_INPUT",
                        "message": "quiz not initialized. call GET /weekly first."},
            )

    correct = str(cached["correct_value"])
    actual = float(cached["actual_ratio_percent"])
    saved = insights_store.save_quiz_answer(
        user_id=req.user_id,
        week_of=req.week,
        predicted=req.predicted,
        correct=correct,
        actual_ratio_percent=actual,
    )
    return QuizAnswerResponse.model_validate(saved)


@router.post("/weekly/condition_flow", response_model=ConditionFlow)
def post_condition_flow(
    entries: Annotated[list[dict], Body()],
) -> ConditionFlow:
    return ConditionFlow.model_validate(condition_flow(entries))


@router.post("/weekly/pattern_diff", response_model=list[PatternDiffRow])
def post_pattern_diff(
    current_entries: Annotated[list[dict], Body()],
    prev_entries: Annotated[list[dict], Body()],
) -> list[PatternDiffRow]:
    diff = pattern_diff(current_entries, prev_entries)
    return [PatternDiffRow.model_validate(row) for row in diff]


@router.post("/baseline/recompute")
def post_baseline_recompute(
    user_id: Annotated[str, Body(min_length=1, max_length=64)],
    entries: Annotated[list[dict], Body()],
    rejected_drills: Annotated[list[str] | None, Body()] = None,
    window_days: Annotated[int, Body()] = 30,
) -> dict:
    return baselines.recompute_baseline(
        user_id=user_id,
        entries=entries,
        rejected_drills=rejected_drills,
        window_days=window_days,
    )


@router.get("/baseline")
def get_baseline(
    user_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> dict:
    base = baselines.get_baseline(user_id)
    if not base:
        raise HTTPException(
            status_code=404,
            detail={"code": "INVALID_INPUT", "message": "no baseline yet — call /baseline/recompute first"},
        )
    return base
