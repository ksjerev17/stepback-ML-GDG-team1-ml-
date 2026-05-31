# W5 완료 보고 — 주간 리포트 + 자가진단 퀴즈

> CLAUDE.md §8.W5 DoD.

## DoD 8개

- [x] **1. GET /weekly** — `app/api/weekly.py`. user_id + week 쿼리. POST /weekly (BE가 entries 보내는 경로) 추가.
- [x] **2. weekly_report 5블록** — `app/core/weekly_report.py`. overview / dominant_pattern / drill_action / self_check_quiz / calendar_distribution.
- [x] **3. self_check_quiz 4지선다** — `app/core/self_check_quiz.py`. 정답 + 같은 그룹 오답 3 + "모르겠다" 4번째.
- [x] **4. 카피 검증** — lint_copy.py 통과 (위로·평가성 표현 0). "맞췄어요/틀렸어요" 사용 X.
- [x] **5. test_weekly_report** — 4 케이스 PASS.
- [x] **6. test_self_check_quiz** — 4 옵션 검증.
- [x] **7. handoff/fe_integration_guide.md** — P3 전용.
- [x] **8. docs/w5_complete.md** — 이 문서.

추가 작성: `handoff/calendar_color_spec.md` (P4), `handoff/content_guide.md` (P5).

## 검증

```
tests 58 passed
- unit 26
- integration 32 (routing 7 + weak 4 + crisis 6 + endpoints 6 + feedback 4 + weekly 4 + audit_log 6 + skipped 5e)
```

## v2.0 보강 (명세서 풀스택)

W5 범위 확장 — 명세서 §8 자가진단 4단계 + §9 시각화 3개 + §10.2 baseline 모두 구현:
- `app/core/insights_store.py` — insights / reports / quiz / rejected_drills 통합 SQLite
- `app/core/auto_discovery.py` — 3 알고리즘 (evidence_span top2 / 맥락-패턴 상관 / 효과적 드릴 top1)
- `app/core/baselines.py` — 30일 누적 평균 + baseline 비교 카드
- `app/api/insights.py` — POST/GET /insights, POST /reject, GET /export, DELETE /users/{id}/data
- `app/api/reports.py` — POST /reports, GET /reports/pending, PATCH /reports/{id}/read
- `app/api/weekly.py` — PATCH /weekly/quiz, POST /weekly/condition_flow, /pattern_diff, /baseline/recompute, /baseline

## 다음 단계 (W6)

smoke 30 케이스 + demo_script + pre_demo_check.
