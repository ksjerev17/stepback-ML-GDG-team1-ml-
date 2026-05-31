# 출처: CLAUDE.md §8.W3 DoD #5
"""가상 사용자 7일 시뮬레이션 → 카테고리 분포 출력."""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.labeler import label_text  # noqa: E402
from app.core.recommender import recommend  # noqa: E402


# 시드 문장 5종 × 7일
SEED_INPUTS = [
    ("아침", "내일 발표 망할 것 같아"),
    ("점심", "과제 시작해야 하는데 자꾸 폰만"),
    ("저녁", "오늘 너무 피곤하다"),
    ("아침", "다 귀찮고 누워있고 싶어"),
    ("점심", "교수님 발표에서 한심하게 봤을 것 같아"),
    ("저녁", "오늘은 평범했어"),
    ("아침", "잠을 4시간밖에 못 잤어 피곤해"),
]


def run() -> None:
    rng = random.Random(42)
    counter: Counter[str] = Counter()
    type_counter: Counter[str] = Counter()
    user_id = "u_sim_001"
    base_context = {
        "self_condition": 3,
        "sleep_hours": 7.0,
        "social_today": "보통",
        "exercise_today": 0.0,
    }

    recent: list[str] = []
    for day, (slot, text) in enumerate(SEED_INPUTS, start=1):
        label = label_text(text, user_id=f"{user_id}_d{day}", skip_quota=True)
        ctx = dict(base_context)
        if "잠을 4시간" in text:
            ctx["sleep_hours"] = 4.0
        out = recommend(
            label_result=label, context=ctx, user_id=f"{user_id}_d{day}",
            recent_drill_ids=recent, rng=rng,
        )
        type_counter[out["type"]] += 1
        if out["type"] == "drill":
            counter[out["drill"]["category"]] += 1
            recent.append(out["drill"]["id"])
            recent = recent[-3:]
        print(f"Day {day} ({slot}) {text!r} → {out['type']}", end="")
        if out["type"] == "drill":
            print(f"  [{out['drill']['category']}] {out['drill']['id']} {out['drill']['name']}")
        else:
            print()

    print("\n=== 7일 시뮬레이션 요약 ===")
    print("Type 분포:")
    for t, n in type_counter.most_common():
        print(f"  {t}: {n}")
    print("Drill 카테고리 분포:")
    for c, n in counter.most_common():
        print(f"  {c}: {n}")


if __name__ == "__main__":
    run()
