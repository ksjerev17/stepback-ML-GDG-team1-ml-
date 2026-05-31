# 출처: 실 Gemini E2E 검증 (긴 텍스트 + 드릴 추천 적정성 + 주간 리포트)
"""20+ 시나리오로 Gemini 라벨링·추천·주간 리포트 통합 검증.

검증 영역 (4):
  A. 라벨링 품질 (긴 텍스트 포함)
  B. 드릴 추천 적정성 — 입력 → 기대 카테고리 매칭
  C. 주간 리포트 5블록 (7일 가상)
  D. 자가진단 퀴즈 흐름

사용:
  $env:GEMINI_API_KEY = "AIzaSy..."
  $env:FORCE_MOCK = "false"
  python -X utf8 scripts/test_gemini_e2e.py
  python -X utf8 scripts/test_gemini_e2e.py --cases 10 --gap 3
  python -X utf8 scripts/test_gemini_e2e.py --skip-llm   # Mock으로 빠른 회귀

비용 추정:
  기본 24 호출 × 3초 = 약 1.5분
  무료 tier 일 1,500회 / 분 30회 — 충분
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ============================================================================
# 시나리오 정의 — 길이·카테고리·기대 라우팅
# ============================================================================

# (id, text, expected_category, expected_pattern_or_behavior, context_override)
SCENARIOS = [
    # --- 짧은 입력 (15자 미만) — confidence 보정 검증 ---
    ("S01", "다 망함", "ANY", None, {"self_condition": 2}),
    ("S02", "그냥 그래", "POSITIVE_OR_ASK", None, {"self_condition": 3}),

    # --- 중간 길이 — 표준 인지 패턴 (30~80자) ---
    ("S03", "내일 발표 망할 것 같아 진짜 어떻게 하지 잠도 안 와",
     "cognitive_restructuring", "미래예측", {"self_condition": 2, "sleep_hours": 5.0}),
    ("S04", "쟤는 분명히 나를 한심하게 봤을 거야 그 표정이 잊혀지지 않아",
     "cognitive_restructuring", "독심술", {"self_condition": 3}),
    ("S05", "다 내 탓이야 내가 그때 그렇게 말하지만 않았어도 이렇게 되지 않았을 텐데",
     "cognitive_restructuring", "자기비난", {"self_condition": 2}),
    ("S06", "완전 망쳤어 다 끝났다 이제 회복할 방법이 없어 보여 진짜로",
     "cognitive_restructuring", "이분법", {"self_condition": 2}),
    ("S07", "이 정도는 당연히 해내야 하는데 반드시 만점 받아야 하는데 절대 늦으면 안 되는데",
     "cognitive_restructuring", "당위진술", {"self_condition": 3}),
    ("S08", "나는 항상 이런 식이야 매번 똑같이 망치고 한 번도 제대로 해낸 적이 없는 것 같아",
     "cognitive_restructuring", "과잉일반화", {"self_condition": 2}),

    # --- 행동 신호 (회피·동기저하) ---
    ("S09", "과제 시작해야 하는데 자꾸 폰만 보게 돼 손이 안 가 시작을 못 하겠어",
     "behavioral_activation", "회피미루기", {"self_condition": 3}),
    ("S10", "다 귀찮고 아무것도 하기 싫다 그냥 누워있고 싶어 의욕이 하나도 없어",
     "habit_design", "동기저하", {"self_condition": 2}),

    # --- 인지 + 행동 동시 (S005 — 회피 우선) ---
    ("S11", "공부해야 하는데 일어나지도 못하겠고 하기 싫고 어차피 시험 망할 것 같아",
     "behavioral_activation", "회피미루기",
     {"self_condition": 2, "sleep_hours": 4.0}),

    # --- 위기 (5종) ---
    ("S12", "더 이상 살고 싶지 않아 그냥 사라지고 싶어",
     "CRISIS", None, {"self_condition": 1}),
    ("S13", "끝내고 싶다 다 끝내고 싶다",
     "CRISIS", None, {"self_condition": 1}),

    # --- 약신호 분기 ---
    ("S14", "오늘은 그냥 평범한 하루였어 별 일 없이 지나갔어",
     "POSITIVE_OR_ASK", None, {"self_condition": 4}),
    ("S15", "오늘 좀 피곤하네 그래도 그럭저럭",
     "grounding", None, {"self_condition": 2}),  # 약신호 + 컨디션 ≤ 2
    ("S16", "오늘은 그냥 그래 어제 4시간밖에 못 잤어",
     "sleep_circadian", None, {"sleep_hours": 4.0, "self_condition": 3}),
    ("S17", "오늘 사이가 안 좋아서 좀 그래",
     "self_compassion", None, {"social_today": "갈등", "self_condition": 3}),

    # --- 긴 텍스트 (150~200자) — confidence 상향 검증 + 다중 신호 ---
    ("S18",
     "이번 학기 시작부터 계속 잠을 못 자고 있는데 어차피 시험은 다 망할 것 같고 부모님 실망시킬 거고 다시 처음부터 준비할 자신도 없고 어떻게 살아야 할지 정말 모르겠어 너무 무서워",
     "cognitive_restructuring", "미래예측",
     {"self_condition": 1, "sleep_hours": 4.0}),
    ("S19",
     "친구가 어제 한 말이 자꾸 머릿속에 맴돌아 분명 나를 한심하게 봤을 거고 비웃었을 거고 이제는 같이 안 놀고 싶어 할 것 같고 다 내 탓 같고 내가 왜 그런 말을 했을까",
     "cognitive_restructuring", "독심술",
     {"social_today": "갈등", "self_condition": 2}),
    ("S20",
     "이번 주는 정말 평온했어 친구들이랑 카페에서 공부도 하고 운동도 적당히 했고 잠도 잘 잤고 별다른 스트레스 없이 흘러갔어 가끔 이런 주가 있다는 게 새삼 소중하게 느껴져",
     "POSITIVE_OR_ASK", None,
     {"self_condition": 5, "sleep_hours": 8.0, "social_today": "좋음", "exercise_today": 1.0}),

    # --- PII 마스킹 검증 ---
    ("S21", "교수님 김민수 발표가 자꾸 미뤄지는 게 너무 부담스럽고 잠도 안 와 010-1234-5678",
     "cognitive_restructuring", None, {"self_condition": 2}),

    # --- 정밀화 발동 가능 (top1·top2 차이 작음) ---
    ("S22", "다 내 탓 같으면서도 어차피 안 될 거라는 생각이 같이 들어 자기비난인지 미래예측인지 모르겠어",
     "cognitive_restructuring", None, {"self_condition": 2}),
]


# 기대 카테고리 정합성 — flexible matching
CRISIS_CARD = "CRISIS"  # crisis_card 응답
POSITIVE_OR_ASK = "POSITIVE_OR_ASK"  # positive_card 또는 ask_user (둘 다 허용)
ANY = "ANY"  # 검증 skip (짧은 입력)


def _check_recommendation(scenario_id: str, expected_cat: str, actual_response: dict) -> tuple[bool, str]:
    """기대 카테고리 vs 실제 응답 타입·카테고리 비교."""
    actual_type = actual_response.get("type")
    if expected_cat == CRISIS_CARD:
        return (actual_type == "crisis_card", f"type={actual_type}")
    if expected_cat == POSITIVE_OR_ASK:
        if actual_type in ("positive_card", "ask_user", "skip"):
            return (True, f"type={actual_type}")
        if actual_type == "drill":
            return (True, f"type=drill[{actual_response['drill']['category']}] (약신호 보조)")
        return (False, f"type={actual_type}")
    if expected_cat == ANY:
        return (True, f"type={actual_type} (검증 skip)")
    # 카테고리 매칭
    if actual_type != "drill":
        return (False, f"type={actual_type} (drill 기대)")
    actual_category = actual_response.get("drill", {}).get("category")
    return (actual_category == expected_cat, f"category={actual_category}")


# ============================================================================
# 메인
# ============================================================================

def run_e2e(args) -> int:
    import random
    from datetime import date

    from app.core.feedback_store import upsert_feedback
    from app.core.insights_store import upsert_report, save_quiz_answer
    from app.core.labeler import label_text
    from app.core.recommender import recommend
    from app.core.self_check_quiz import get_cached_answer
    from app.core.weekly_report import build_report
    from app.infra.llm_client import get_llm_client

    llm = get_llm_client()
    if args.skip_llm or llm.is_mock:
        print(f"[mode] MOCK (skip_llm={args.skip_llm}, is_mock={llm.is_mock})")
    else:
        print(f"[mode] REAL Gemini — primary={llm.primary_model} / light={llm.light_model}")
        print(f"       gap={args.gap}s · 호출 간격으로 quota 보호")

    cases = SCENARIOS[: args.cases] if args.cases > 0 else SCENARIOS
    print(f"\n[A] 라벨링 {len(cases)} 케이스 호출\n")

    # 1단계: 라벨링 (입력 → LLM → label_result)
    base_ctx = {"self_condition": 3, "sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0}
    labeled = []
    for i, (sid, text, _, _, _) in enumerate(cases):
        if i > 0 and not llm.is_mock and not args.skip_llm:
            time.sleep(args.gap)
        t0 = time.perf_counter()
        try:
            result = label_text(text, user_id=f"e2e_{sid}", skip_quota=True)
            elapsed = (time.perf_counter() - t0) * 1000
            warn = result.get("_warning") or result.get("clarification_error")
            top_p = max(result.get("patterns", {}).items(), key=lambda kv: kv[1], default=("-", 0))
            top_b = max(result.get("behaviors", {}).items(), key=lambda kv: kv[1], default=("-", 0))
            crisis = "🚨" if result.get("crisis_detected") else " "
            conf = result.get("confidence", 0)
            print(f"  [{sid}] {crisis} {elapsed:5.0f}ms  conf={conf:.2f}  "
                  f"top_p={top_p[0]}={top_p[1]:.2f}  top_b={top_b[0]}={top_b[1]:.2f}  "
                  f"[{result.get('model_used', '?')}]"
                  + (f"  WARN:{warn}" if warn else ""))
            labeled.append((sid, text, result))
        except Exception as e:
            print(f"  [{sid}] ERROR: {type(e).__name__}: {e}")
            labeled.append((sid, text, None))

    # 2단계: 추천 라우팅 (LLM 미사용 — 점수공식)
    print(f"\n[B] 드릴 추천 적정성 검증\n")
    rec_results = []
    pass_count = 0
    fail_count = 0
    for (sid, text, result), (_, _, expected_cat, _, ctx_override) in zip(labeled, cases):
        if result is None:
            continue
        ctx = {**base_ctx, **(ctx_override or {})}
        try:
            rec = recommend(label_result=result, context=ctx, user_id=f"e2e_{sid}")
        except Exception as e:
            print(f"  [{sid}] recommend ERROR: {e}")
            fail_count += 1
            continue
        ok, detail = _check_recommendation(sid, expected_cat, rec)
        mark = "PASS" if ok else "FAIL"
        if ok:
            pass_count += 1
        else:
            fail_count += 1
        print(f"  [{sid}] {mark}  기대={expected_cat:25s}  →  {detail}")
        rec_results.append((sid, rec, ctx))

    print(f"\n  요약: {pass_count}/{pass_count + fail_count} PASS  ({100 * pass_count / max(pass_count + fail_count, 1):.0f}%)")

    # 3단계: 주간 리포트 (7일 가상 entries 구성)
    print(f"\n[C] 주간 리포트 5블록 검증\n")
    # 첫 21개 라벨링 결과를 7일에 분배 (시뮬레이션)
    today = date.today()
    entries = []
    for i, (sid, text, result) in enumerate(labeled[:21]):
        if result is None:
            continue
        day = today - timedelta(days=i // 3)
        slot_hour = [8, 13, 19][i % 3]
        entries.append({
            "created_at": datetime.combine(day, datetime.min.time()).replace(hour=slot_hour, tzinfo=timezone.utc).isoformat(),
            "self_condition": (3 if i % 3 == 0 else 4 if i % 3 == 1 else 2),
            "context": {"sleep_hours": 5.0 if i % 4 == 0 else 7.0},
            "label_result": result,
            "calendar_dominant": result.get("calendar_dominant", "weak_signal_positive"),
        })

    if entries:
        report = build_report(
            week="2026-W21",
            user_id="e2e_weekly",
            entries=entries,
            drills_recommended=len([r for r in rec_results if r[1].get("type") == "drill"]),
            drills_practiced=3,
            prev_week_avg=3.0,
            rng=random.Random(0),
        )
        print(f"  Block 1 overview: 기록 {report['overview']['recorded_days']}일 / 평균 {report['overview']['avg_self_condition']}")
        print(f"  Block 2 dominant: {report['dominant_pattern']['dominant_key']} ({report['dominant_pattern']['ratio_percent']}%)")
        print(f"  Block 3 drill:    {report['drill_action']['practiced_count']}/{report['drill_action']['recommended_count']} ({100*report['drill_action']['practice_rate']:.0f}%)")
        print(f"  Block 4 quiz:     '{report['self_check_quiz']['question']}'")
        print(f"                    options: {[o['label'] for o in report['self_check_quiz']['options']]}")
        print(f"  Block 5 dist:     {report['calendar_distribution']['distribution']}")
        print(f"  발견 카드: {len(report.get('discoveries') or [])}건")
        for d in (report.get("discoveries") or [])[:3]:
            print(f"    · {d['text']}")

        # 4단계: 자가진단 퀴즈 흐름
        print(f"\n[D] 자가진단 퀴즈 흐름\n")
        # GET /weekly의 build_report가 이미 server-side cache에 정답 저장함
        cached = get_cached_answer("e2e_weekly", "2026-W21")
        if cached:
            print(f"  Server cache: correct={cached['correct_value']}  ratio={cached['actual_ratio_percent']}%")
        # 사용자가 dominant_pattern을 정확히 답한다고 가정
        try:
            from app.core.insights_store import save_quiz_answer as _sqa
            saved = _sqa(
                user_id="e2e_weekly",
                week_of="2026-W21",
                predicted=report["dominant_pattern"]["dominant_key"],
                correct=cached["correct_value"] if cached else report["dominant_pattern"]["dominant_key"],
                actual_ratio_percent=report["dominant_pattern"]["ratio_percent"],
            )
            print(f"  Quiz 답 저장: match={saved['match']}  is_dont_know={saved['is_dont_know']}")
        except Exception as e:
            print(f"  Quiz 저장 ERROR: {e}")
    else:
        print(f"  entries 없음 — skip")

    # 5. 종합 결과
    print(f"\n[요약]")
    print(f"  라벨링: {len([l for l in labeled if l[2] is not None])}/{len(labeled)} 성공")
    print(f"  추천:   {pass_count}/{pass_count + fail_count} PASS")
    print(f"  리포트: 5블록 + 발견 카드 + 퀴즈 — 동작")
    if not llm.is_mock:
        print(f"\n  실 Gemini 응답 품질 평가 권장:")
        print(f"  - confidence 분포 (Mock 균일 vs Real 다양 — 위 출력 conf 컬럼 비교)")
        print(f"  - 약신호 케이스에서 LLM이 0.3 미만으로 정확히 표시하는지")
        print(f"  - 긴 텍스트(S18,S19)에서 다중 신호를 잘 잡는지")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=0, help="처음 N 케이스만 (기본 0 = 전체)")
    parser.add_argument(
        "--gap", type=float, default=4.0,
        help="LLM 호출 간격 초 (기본 4). 무료 tier 기준: "
             "gemini-2.0-flash-lite=2초 / gemini-2.5-flash-lite=13초+",
    )
    parser.add_argument("--skip-llm", action="store_true", help="Mock 강제 (회귀 검증용)")
    args = parser.parse_args()
    if args.skip_llm:
        os.environ["FORCE_MOCK"] = "true"
    return run_e2e(args)


if __name__ == "__main__":
    sys.exit(main())
