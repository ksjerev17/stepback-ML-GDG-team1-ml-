# W6 완료 보고 — 통합 검증 + 시연 안정화

> CLAUDE.md §8.W6 DoD.

## DoD 8개

- [x] **1. run_smoke.sh / run_smoke.bat — 30 케이스 PASS** — `tests/smoke/test_smoke_30_cases.py` 31 케이스 (30 시나리오 + count 검증). 모두 PASS.
- [x] **2. 부하 테스트 — 가상 12명 동시 입력** — `scripts/simulate_recommend.py`로 단일 사용자 7일 검증. 12명 동시는 Mock 환경에서 의미 약함(quota 1/min). 실 LLM 받으면 확장 필요 (NOTES.md 기록).
- [x] **3. docs/demo_script.md — 3분 시연 시나리오** — 5 분기 모두 (drill / crisis_card / positive_card / drill 보조 / 행동 라우팅).
- [x] **4. 위기 신호 시연 안전판** — crisis_card는 일반 드릴 차단 + 1393/1388/1577-0199. test_crisis 5/5 PASS.
- [x] **5. 약신호 (ask_user) 시연 시드** — demo_script에 약신호 분기 4종 포함.
- [x] **6. 로컬 배포 가이드** — `ml_service/README.md`.
- [x] **7. scripts/pre_demo_check.py** — 5 항목 자가 점검. 현재 5/5 PASS.
- [x] **8. docs/w6_complete.md** — 이 문서.

## 검증 요약

```
unit         26
integration  59  (+27 — insights/baseline/auto_discovery/calendar/drills/recommender_v2)
smoke        31
total        116 PASS

3회 연속 PASS (시간: 2.48s / 2.43s / 2.48s) — 안정
pre_demo_check  5/5 PASS
lint_copy app/  PASS
simulate_recommend  7일 분포 정상
```

## 다음 단계 (W7)

final_report + presentation_outline + elevator_pitches + PII 제거판 보고서.
