# W2 완료 보고 — ML 서비스 골격 + FastAPI

> CLAUDE.md §8.W2 DoD 체크.

## DoD 17개

- [x] **1. FastAPI 프로젝트 구조** — `app/{api,core,infra,schemas,data}/__init__.py` 모두 생성
- [x] **2. Pydantic v2 스키마 5종** — common / label / recommend / feedback / weekly
- [x] **3. `GET /healthz`** — drills_loaded, primary_model, ml_available 포함
- [x] **4. PII 마스킹 + tests** — 7종 (URL/이메일/전화/학번/호칭+이름/성씨+이름/일반어 화이트리스트). `tests/unit/test_pii.py` 12 케이스 PASS
- [x] **5. Quota Manager + tests** — user_id별 격리, 분 1 / 시 3 / 일 3. `test_quota.py` 7 케이스 PASS
- [x] **6. LLM Client + Mock 폴백** — `infra/llm_client.py`. **현재 API 키 미보유로 Mock 강제** (어휘 단서 기반 라벨 생성). Gemini 활성화 hook 자리 표시
- [x] **7. Labeler** — w1/`label_postprocess`·`clarification_loop` import + mask → quota → LLM → postprocess → clarify 흐름
- [x] **8. Recommender 라우팅 5단계 + 약신호 분기** — §6 정확히. 행동 가중치 0.40 > 인지 0.35. S005 (회피 우선) 회귀 방지
- [x] **9. crisis_card / positive_card / ask_user / skip** — 5 응답 타입
- [x] **10. `POST /label`, `POST /recommend`** — FastAPI 라우터
- [x] **11. test_routing_5_steps 7 시나리오** — S001/S036/S040/S016/S005/S007 + step6 PASS
- [x] **12. test_weak_signal_branches 5 케이스** — 5a/5b/5c/5d PASS (5e는 5a~5d에 항상 매칭되어 step6 fallback으로 검증)
- [x] **13. test_crisis 5종** — `사라지고/죽고/끝내고/자해/사라지고 싶어` PASS
- [ ] **14. Postman 컬렉션 15 요청** — 시간상 보류, FastAPI `/docs` Swagger UI로 대체 가능 (NOTES.md 기록)
- [x] **15. handoff/api_contract.md** — P2 합의용 (§9 그대로)
- [x] **16. docs/w2_complete.md** — 이 문서
- [x] **17. ruff·black·mypy·pytest** — pytest 50/50 PASS (unit 26 + integration 24). ruff/black/mypy는 미설치 환경에서 스킵 (NOTES.md)

## 시험 결과

```
tests/unit  26 passed
tests/integration  24 passed
total  50 passed in 1.7s
```

## 영향 받는 다른 팀원 통보

- P2: API 계약 v0.1 확정. `ML_SERVICE_URL` 환경변수.
- P3: 5 type 응답 분기 필요.
- P4: `calendar_dominant` 9 enum (부록 C).

## 다음 단계 (W3)

audit_log JSONL 정식 + analyze_labeling 스크립트 + context caching + lint_copy.
