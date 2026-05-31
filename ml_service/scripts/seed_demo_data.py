# 출처: 운영 보강 — 시연·QA용 데모 데이터 시드
"""베타 사용자 3명 × 7일 가상 데이터를 SQLite에 시드.

용도:
- 시연 직전 demo_user_1~3 미리 만들기 → 캘린더·주간 리포트가 즉시 채워짐
- E2E 통합 테스트 (BE 미연결 시 ML 단독으로 화면 흐름 검증)

주의: production DB에 절대 실행 X. force_seed=False가 기본값.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import insights_store  # noqa: E402
from app.core import baselines  # noqa: E402
from app.core.feedback_store import upsert_feedback  # noqa: E402
from app.core.labeler import label_text  # noqa: E402


DEMO_USERS = ("demo_user_1", "demo_user_2", "demo_user_3")

# 7일 × 3 시간대 = 21 입력 풀
SEED_INPUTS = [
    ("morning", "내일 발표 망할 것 같아"),
    ("afternoon", "과제 시작해야 하는데 자꾸 폰만"),
    ("evening", "오늘 너무 피곤하다"),
    ("morning", "다 귀찮고 누워있고 싶어"),
    ("afternoon", "발표에서 한심하게 봤을 것 같아"),
    ("evening", "오늘은 평범했어"),
    ("morning", "잠을 4시간밖에 못 잤어 피곤해"),
    ("afternoon", "다 내 탓 같다"),
    ("evening", "완전 망쳤어 다 끝났다"),
    ("morning", "반드시 만점 받아야 해"),
    ("afternoon", "나는 항상 이래 매번 망쳐"),
    ("evening", "오늘 좋았다"),
]


def seed_one_user(user_id: str, *, rng: random.Random) -> dict:
    today = date.today()
    counts = {"entries": 0, "feedbacks": 0, "reports": 0, "insights": 0}

    # 7일치 입력
    for d_back in range(7):
        day = today - timedelta(days=d_back)
        sample = rng.sample(SEED_INPUTS, k=min(3, len(SEED_INPUTS)))
        for slot, text in sample:
            label_text(text, user_id=user_id, skip_quota=True)
            counts["entries"] += 1

    # 드릴 평가 5건 (3 helpful / 1 meh / 1 unhelpful)
    for drill_id, rating in [("D01", "helpful"), ("D02", "helpful"), ("D08", "helpful"), ("D31", "meh"), ("D77", "unhelpful")]:
        try:
            upsert_feedback(
                user_id=user_id, drill_id=drill_id, rating=rating,
                recommended_at=today,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc) if rating != "unhelpful" else None,
            )
            counts["feedbacks"] += 1
        except Exception as e:
            print(f"  skip feedback {drill_id}: {e}")

    # 주간 리포트 시드 (이번 주 W21)
    week = "2026-W21"
    rpt = insights_store.upsert_report(
        user_id=user_id,
        week_of=week,
        pattern_analysis={"미래예측": 45, "자기비난": 30, "이분법": 15, "당위진술": 10},
        emotion_distribution={"불안": 0.5, "우울": 0.3, "분노": 0.1, "죄책": 0.1, "중립": 0.0},
    )
    counts["reports"] += 1
    rid = rpt["report_id"]

    # 발견 4건 (system 2 + user 2)
    for src, cat, txt in [
        ("system", "context", "잠 6시간 미만 날에 미래예측 표현이 더 자주 보였어요"),
        ("system", "drill", "드릴 D01이 '도움됨' 비율 80% (4회 시도)"),
        ("user", "cognitive", "잠 부족할 때 발표 걱정이 커지는 듯"),
        ("user", "context", "운동한 날은 좀 가볍게 느껴짐"),
    ]:
        try:
            insights_store.add_insight(
                user_id=user_id, text=txt, source=src, category=cat,
                week_of=week, report_id=rid,
            )
            counts["insights"] += 1
        except Exception as e:
            print(f"  skip insight: {e}")

    # baseline 1건
    try:
        baselines.recompute_baseline(
            user_id=user_id,
            entries=[],
            rejected_drills=["D17"],
        )
    except Exception as e:
        print(f"  skip baseline: {e}")

    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="production에서도 실행 (위험)")
    parser.add_argument("--users", default=",".join(DEMO_USERS), help="콤마 구분 user_id 리스트")
    args = parser.parse_args()

    print("[seed_demo_data]")
    if not args.force:
        from app.config import should_force_mock
        if not should_force_mock():
            print("  ERROR: FORCE_MOCK=false 환경에서는 --force 필요 (실 LLM 호출 비용 보호)")
            return 1

    users = [u.strip() for u in args.users.split(",") if u.strip()]
    rng = random.Random(42)
    for u in users:
        print(f"  seeding {u}...")
        c = seed_one_user(u, rng=rng)
        print(f"    {c}")
    print("[seed_demo_data] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
