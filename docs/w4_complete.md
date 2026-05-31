# W4 완료 보고 — 드릴 평가 + 행동 추적

> CLAUDE.md §8.W4 DoD.

## DoD 8개

- [x] **1. SQLite `feedback.db` 스키마** — `app/core/feedback_store.py`의 `SCHEMA` (§4.4 그대로). UNIQUE(user_hash, drill_id, recommended_at).
- [x] **2. feedback_store** — `upsert_feedback()` 당일 수정, 다음날 거부. `user_summary()` 점수 비공개.
- [x] **3. action_tracker** — `practice_rate(user_id, since_days=7)`. started_count / practiced_count / 실천율.
- [x] **4. POST /feedback, GET /feedback** — `app/api/feedback.py`. GET 응답에 rating 노출 X (§4.4).
- [x] **5. test_feedback_endpoint** — 4 시나리오 PASS (accepted / 422 / 비공개 / idempotent upsert).
- [x] **6. purge_old_data.py** — 90일 자동 삭제 (feedback rows + audit-*.jsonl).
- [x] **7. api_contract.md /feedback 추가** — W2 시점에 이미 포함됨.
- [x] **8. docs/w4_complete.md** — 이 문서.

## 검증

```
tests/integration/test_feedback_endpoint.py  4 passed
```

전체 테스트: 54/54 PASS.

## 다음 단계 (W5)

weekly_report 5블록 + self_check_quiz + /weekly.
