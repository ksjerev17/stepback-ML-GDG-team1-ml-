# 출처: CLAUDE.md §8.W6 DoD #2 (가상 12명 동시 입력)
"""베타 12명 동시 입력 시뮬레이션 — quota 격리 + 응답 시간 측정.

서버가 떠 있어야 함:
  uvicorn app.main:app --host 127.0.0.1 --port 8001

실행:
  python -X utf8 scripts/load_test.py --users 12 --rounds 3
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


SCENARIOS = [
    "내일 발표 망할 것 같아",
    "과제 시작해야 하는데 자꾸 폰만",
    "오늘 평범했어",
    "다 귀찮고 누워있고 싶어",
    "사라지고 싶다",   # 위기 — 일반 드릴 차단 검증
    "잠 4시간밖에 못 잤어",
    "오늘은 그냥 그래",
    "공부해야 하는데 일어나지 못해서 하기 싫어",
]


def one_call(client: httpx.Client, base_url: str, user_id: str, text: str) -> dict:
    t0 = time.perf_counter()
    try:
        resp = client.post(
            f"{base_url}/label",
            json={"text": text, "user_id": user_id},
            timeout=10.0,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "user_id": user_id,
            "text": text,
            "status": resp.status_code,
            "ms": elapsed,
            "crisis": resp.json().get("crisis_detected") if resp.status_code == 200 else None,
        }
    except httpx.HTTPError as e:
        return {"user_id": user_id, "text": text, "status": "ERROR", "ms": -1, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=1, help="각 user 호출 횟수 (quota 한도 분당 1)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--concurrency", type=int, default=12)
    args = parser.parse_args()

    print(f"[load_test] base={args.base_url} users={args.users} rounds={args.rounds}")

    # 헬스 체크
    try:
        r = httpx.get(f"{args.base_url}/healthz", timeout=3.0)
        if r.status_code != 200:
            print(f"  ERROR: /healthz {r.status_code}")
            return 1
    except Exception as e:
        print(f"  ERROR: 서버 미응답 - {e}")
        print("  먼저 uvicorn app.main:app --host 127.0.0.1 --port 8001 실행")
        return 1

    # quota reset (admin token으로) — 각 user 깨끗한 상태 보장
    for i in range(args.users):
        try:
            httpx.post(
                f"{args.base_url}/admin/quota/reset",
                json=f"load_user_{i}",
                headers={"X-Admin-Token": "dev-admin-token"},
                timeout=2.0,
            )
        except Exception:
            pass

    results: list[dict] = []
    with httpx.Client() as client:
        for round_n in range(args.rounds):
            print(f"\n  Round {round_n + 1}/{args.rounds}")
            tasks = []
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                for i in range(args.users):
                    text = SCENARIOS[(round_n * args.users + i) % len(SCENARIOS)]
                    tasks.append(pool.submit(one_call, client, args.base_url, f"load_user_{i}", text))
                for f in as_completed(tasks):
                    results.append(f.result())
            # 라운드 사이 분당 quota 회피 (간단히 wait — 실제는 다른 user_id로 분산)
            if round_n < args.rounds - 1:
                print("    waiting 61s for minute quota reset...")
                time.sleep(61)

    # 통계
    ok = [r for r in results if r["status"] == 200]
    quota_429 = [r for r in results if r["status"] == 429]
    errors = [r for r in results if r["status"] not in (200, 429)]
    crisis = [r for r in ok if r.get("crisis")]

    print("\n[load_test 결과]")
    print(f"  총 요청: {len(results)}")
    print(f"  200 OK: {len(ok)}")
    print(f"  429 quota: {len(quota_429)}")
    print(f"  기타: {len(errors)}")
    print(f"  위기 감지: {len(crisis)}")
    if ok:
        ms = [r["ms"] for r in ok]
        print(f"  지연 (200만, ms): min={min(ms):.0f} / p50={statistics.median(ms):.0f} / p95={statistics.quantiles(ms, n=20)[-1]:.0f} / max={max(ms):.0f}")
    if errors:
        print("  에러 샘플:")
        for r in errors[:3]:
            print(f"    {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
