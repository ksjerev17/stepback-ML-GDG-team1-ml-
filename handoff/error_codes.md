# 에러 코드 (P2 합의) — v9.5

| 코드 | HTTP | 의미 | 재시도 |
|---|---|---|---|
| `INVALID_INPUT` | 400 | 비즈니스 검증 실패 (drill_id 없음, report_id FK 위반 등) | X |
| `VALIDATION_ERROR` | 422 | Pydantic 검증 실패 (타입·길이·정규식·빈 텍스트·이모지만·반복문자) | X |
| `QUOTA_EXCEEDED` | 429 | 분 1 / 시 3 / 일 3 초과 (v9.5: 일 1회 정책이지만 quota 한도는 유지 — 시연·실수 보호) | `retry_after_seconds` 후 |
| `ML_UNAVAILABLE` | 503 | LLM 호출 실패 (Gemini quota·네트워크) — ADMIN_TOKEN 미설정 시 admin 엔드포인트도 503 | 자동 재시도 ≤ 2회 후 |
| `INTERNAL_ERROR` | 500 | 예상 못한 예외 | X — 사용자 에러 카드만 |

응답 본문 (v9.5 — `request_id` 포함):
```json
{
  "detail": {
    "code": "...",
    "message": "사람이 읽을 수 있는 메시지",
    "scope": "minute | hour | day",        // QUOTA_EXCEEDED만
    "retry_after_seconds": 60,             // QUOTA_EXCEEDED만
    "request_id": "abc123def456",          // 모든 에러에 포함 — 디버깅용
    "errors": [...]                        // VALIDATION_ERROR만 — pydantic detail
  }
}
```

추가 시 즉시 P2 통보 (changelog.md).
