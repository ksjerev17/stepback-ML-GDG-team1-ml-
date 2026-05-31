# Step Back ML — API 계약 (P2/P3 정본) v9.5

> 변경 시 `handoff/changelog.md`에 통보 (매주 월요일).
> Swagger UI 자동 명세: http://127.0.0.1:8001/docs

## 베이스 URL

- 로컬: `http://127.0.0.1:8001`
- BE→ML 환경 변수: `ML_SERVICE_URL`
- 타임아웃: 라벨링 10s / 추천 3s / 헬스 3s / 주간·월간 5s

## v9.5 핵심 변경

- **드릴 ID는 INT** (`1`, `2`, ... `77`). `legacy_id` ("D01") 옛 데이터 호환 가능.
- **하루 1회 입력 정책** — quota 분 1 / 시 3 / 일 3은 그대로지만 베타 권장은 일 1회.
- **`POST /entries` 통합** — BE 한 번 호출로 label+recommend.
- **ask-first 정책** — 약신호+맥락 나쁨 시 `type=ask_user` → `POST /recommend/after_ask`.
- **`time_of_day` 옵셔널** — 옛 호환만, 새 정책에선 의미 X.

---

## 1. GET /healthz — 헬스 체크

```json
{
  "status": "ok",
  "version": "v7",
  "catalog_version": "v6.3",
  "spec_version": "v9.5",
  "primary_model": "gemini-2.0-flash-lite",
  "drills_loaded": 77,
  "ml_available": true,
  "is_mock": false
}
```

---

## 2. POST /entries — 통합 (옵션 C, v9.5) — **BE 권장 경로**

한 번 호출로 라벨링 + 추천 + 카테고리 메타까지 모두 받음.

### 요청
```json
{
  "text": "내일 발표 망할 것 같아",
  "user_id": "u_123",
  "context": {
    "self_condition": 3,
    "sleep_hours": 7.0,
    "social_today": "보통",
    "exercise_today": 0.0
  },
  "recent_drill_ids": [3, 17]
}
```

`context`는 BE 명세 (`sleep`/`condition`/`exercise`) 또는 ML 표준 (`sleep_hours`/`self_condition`/...) 양쪽 자동 매핑. 누락 필드는 기본값 (sleep 7h / social 보통 / exercise 0h / condition 3).

### 응답 (`EntriesResponse`)
```json
{
  "text": "내일 발표 망할 것 같아",
  "context_used": {
    "self_condition": 3,
    "sleep_hours": 7.0,
    "social_today": "보통",
    "exercise_today": 0.0
  },
  "label_result": { /* /label 응답 그대로 */ },
  "recommendation": { /* /recommend 응답 — 5 type 중 하나 */ },
  "drill_category": "cognitive_restructuring",
  "drill_category_label": "생각 전환",
  "drill_calendar_color": "pink_soft",
  "labeled_at": "2026-05-25T03:14:00+00:00"
}
```

- `drill_category` 없을 수도 있음 (crisis_card / positive_card / ask_user / skip 시 null)
- `drill_calendar_color` 6 값: `pink_soft / white_soft / pink_warm / green_calm / lavender / blue_night`

---

## 3. POST /label — 단독 라벨링 (옛 호환, BE가 분리 호출 시)

### 요청
```json
{ "text": "내일 발표 망할 것 같아", "user_id": "u_123" }
```
- `text`: 1~200자, 공백만·이모지만·반복문자 거절 (422)

### 응답 (`LabelResult`)
```json
{
  "patterns": {"미래예측": 0.7, "독심술": 0.0, "자기비난": 0.0, "이분법": 0.2, "당위진술": 0.0, "과잉일반화": 0.0},
  "behaviors": {"회피미루기": 0.0, "동기저하": 0.0},
  "emotions": {"불안": 0.7, "우울": 0.1, "분노": 0.0, "죄책": 0.0, "중립": 0.0},
  "intensity": 0.5,
  "confidence": 0.50,
  "evidence_span": "망할 것 같아",
  "crisis_detected": false,
  "calendar_dominant": "emotion_anxiety",
  "model_used": "gemini-2.0-flash-lite",
  "labeled_at": "2026-05-25T03:14:00+00:00"
}
```

v9.5: 욕설 감지 시 `_profanity_detected: true` + intensity/confidence 가산.
위기 시 `crisis_detected: true` + 모든 점수 0 + `evidence_span: "위기 신호 감지"`.

---

## 4. POST /recommend — 단독 추천 (옛 호환)

### 요청
```json
{
  "label_result": { /* /label 응답 */ },
  "context": {
    "self_condition": 3,
    "sleep_hours": 7.0,
    "social_today": "보통",
    "exercise_today": 0.0
  },
  "user_id": "u_123",
  "recent_drill_ids": [3, 17]
}
```

### 응답 5 type

#### type = "drill"
```json
{
  "type": "drill",
  "drill": {
    "id": 1,
    "name": "증거 2:2 적기",
    "category": "cognitive_restructuring",
    "duration_min": 5,
    "instruction": "...",
    "citation": "Beck(2020) CBT 11장"
  },
  "copy": {
    "line1": "방금 쓰신 글에서 '망할 것 같아'가 보이네요.",
    "line2": "이런 때는 〈증거 2:2 적기〉이 어떠세요?",
    "line3": "5분 정도 걸려요."
  },
  "reason": "인지 미래예측 강함 (0.70)"
}
```

#### type = "crisis_card" (변형 절대 금지)
```json
{
  "type": "crisis_card",
  "reason": "위기 신호 감지 — 일반 드릴 차단",
  "crisis_resources": {"자살예방상담": "1393", "청소년상담": "1388", "정신건강위기상담": "1577-0199"},
  "user_message": "지금 많이 힘드신 것 같아요. 혼자 견디지 마세요."
}
```

#### type = "positive_card"
```json
{"type": "positive_card", "reason": "컨디션 양호 (4) + 신호 약함", "message": "오늘 평온한 하루였네요."}
```

#### type = "ask_user" (v9.4.4 ask-first 신규)
약신호 + 맥락 나쁨 시:
```json
{
  "type": "ask_user",
  "reason": "약신호 + 컨디션 낮음 — 동의 후 추천",
  "question": "텍스트는 잔잔한데 컨디션이 좀 낮으시네요 (2점). 잠시 그라운딩 해보실래요?",
  "options": [{"value":"yes","label":"네, 받을게요"}, {"value":"no","label":"괜찮아요, 기록만"}],
  "offer_category": "grounding",
  "offer_reason_type": "low_condition",
  "offer_context_value": 2.0
}
```

경계선(0.3~0.5) 정밀화 시:
```json
{
  "type": "ask_user",
  "reason": "경계선 신호 (0.40/0.35) — 정밀화 필요",
  "question": "어느 신호가 더 강하게 느껴지세요? '미래예측' 또는 '회피미루기'?",
  "options": [
    {"value":"미래예측","label":"미래예측"},
    {"value":"회피미루기","label":"회피미루기"},
    {"value":"tie","label":"비슷해요"}
  ]
}
```

#### type = "skip"
```json
{"type": "skip", "message": "오늘 기록만 남겨둘게요."}
```

---

## 5. POST /recommend/after_ask — ask-first 후속 (v9.4.4/v9.5)

### 요청
```json
{
  "label_result": { /* /label 응답 — 같은 것 */ },
  "context": { /* 같은 context */ },
  "user_id": "u_123",
  "user_choice": "yes",
  "offer_category": "grounding",
  "offer_reason_type": "low_condition"
}
```

`user_choice` 분기:
- `"yes"` + `offer_category` → 약속한 카테고리 드릴
- `"yes"` + offer_category 없음 → 상태값(컨디션/수면/사교) 기반 폴백 드릴
- `"no"` / `"skip"` → `type=skip`, 메시지: "기록만 남겨두었어요. 오늘도 충분해요."
- `"tie"` + `chosen_candidate` → 사용자 선택 카테고리 (경계선 정밀화용)

### 응답
일반 `/recommend`와 같은 `RecommendResponse` 5 type.

---

## 6. POST /feedback — 드릴 평가

```json
{
  "user_id": "u_123",
  "drill_id": 1,
  "rating": "helpful",
  "recommended_at": "2026-05-25",
  "started_at": "2026-05-25T03:20:00+09:00",
  "completed_at": "2026-05-25T03:25:00+09:00"
}
```
- `drill_id` INT (v9.5)
- KST 23:59까지 수정 가능. 다음날 거부 (400).

```json
{"accepted": true, "can_edit_until": "2026-05-25T23:59:59+09:00"}
```

## 7. GET /feedback — 메타 (점수 비공개)

```json
{"user_id": "u_123", "total_count": 12, "last_rated_at": "2026-05-24T15:30:00+00:00"}
```
의도적으로 rating 노출 X.

## 8. POST /reject — "아닌 것 같아요"

```json
{"user_id": "u_123", "drill_id": 1}
```

`drill_id` INT. 이후 추천에서 자동 회피.

## 9. GET /drills/{id} — 드릴 상세

```http
GET /drills/1
```
또는 옛 string 호환:
```http
GET /drills/D01
```

```json
{
  "id": 1,
  "title": "증거 2:2 적기",
  "category": "cognitive_restructuring",
  "duration_min": 5,
  "instruction": "지금 든 생각을 한 줄로 쓰고...",
  "source_short": "Beck(2020) CBT 11장",
  "evidence_level": "primary"
}
```

## 10. GET /drills — 카탈로그

```http
GET /drills?category=grounding
```

## 11. POST /weekly — 주간 리포트 (BE entries 전달)

```json
{
  "user_id": "u_123",
  "week": "2026-W21",
  "entries": [
    {
      "created_at": "2026-05-19T09:00:00+00:00",
      "self_condition": 3,
      "context": {"sleep_hours": 7.0, "social_today": "보통", "exercise_today": 0.0},
      "label_result": { /* ... */ },
      "calendar_dominant": "emotion_anxiety"
    },
    ...
  ],
  "drills_recommended": 7,
  "drills_practiced": 5,
  "prev_week_avg": 2.9,
  "prev_entries": [ /* 선택 */ ],
  "feedback_rows": [ /* 선택 */ ]
}
```

### 응답 (`WeeklyReport`)
```json
{
  "week": "2026-W21",
  "user_id": "u_123",
  "overview": {"recorded_days": 6, "avg_self_condition": 3.4, "prev_week_avg": 2.9, "delta_vs_prev": 0.5},
  "dominant_pattern": {"dominant_key": "미래예측", "ratio_percent": 32.0, "occurrences": 4},
  "drill_action": {"recommended_count": 7, "practiced_count": 5, "practice_rate": 0.71},
  "self_check_quiz": {
    "question": "이번 주 가장 자주 보인 패턴이 32%였어요. 무엇이었을까요?",
    "options": [
      {"value":"미래예측","label":"미래예측"},
      {"value":"자기비난","label":"자기비난"},
      {"value":"독심술","label":"독심술"},
      {"value":"모르겠다","label":"모르겠다"}
    ]
  },
  "calendar_distribution": {"distribution": {"emotion_anxiety": 3, "weak_signal_positive": 4}},
  "condition_flow": {"points": [{"dow":"월","avg_condition":2.5,"count":1}, ...]},
  "pattern_diff": [{"pattern":"미래예측","current_percent":32.0,"prev_percent":18.0,"delta_percent":14.0,"arrow":"up"}],
  "discoveries": [
    {"text":"이번 주 '망할 것 같' 표현이 3회 보였어요","category":"cognitive","source":"system","count":3},
    {"text":"잠 6시간 미만 날에 미래예측 표현이 더 자주 보였어요 (평균 0.55 vs 0.20)","category":"context","source":"system","low_avg":0.55,"high_avg":0.20,"delta":0.35},
    {"text":"드릴 1이 '도움됨' 비율 80% (4회 시도)","category":"drill","source":"system","drill_id":1,"helpful_ratio":0.80,"sample":4},
    {"text":"한 주 후반으로 갈수록 컨디션이 회복되는 패턴이에요 (전반 2.5 → 후반 3.8)","category":"context","source":"system","pattern_type":"recovery","early_condition_avg":2.5,"late_condition_avg":3.8,"condition_delta":1.3}
  ],
  "baseline_card": {"deltas":{"미래예측":0.14}, "top_increase":{"name":"미래예측","delta":0.14,"card":"평소보다 미래예측 표현이 14%p 더 보였어요"}},
  "emotion_pentagon": {
    "axes": [
      {"label":"불안","value":0.45},
      {"label":"우울","value":0.32},
      {"label":"분노","value":0.18},
      {"label":"죄책","value":0.21},
      {"label":"중립","value":0.55}
    ],
    "dominant": "중립",
    "entries_used": 7
  }
}
```

**중요**:
- `self_check_quiz`에 `correct_value` 없음 (server-side cache만 — 메타인지 측정 보호)
- `discoveries[].pattern_type` 4종: `recovery` / `fatigue` / `early_load` / `late_load` (v9.5 일 1회 정책)
- `emotion_pentagon.entries_used`: 일 1회 × 7일 = 약 7

## 12. PATCH /weekly/quiz — 자가진단 답

```json
{"user_id": "u_123", "week": "2026-W21", "predicted": "미래예측"}
```

응답:
```json
{
  "user_id": "u_123",
  "week_of": "2026-W21",
  "predicted": "미래예측",
  "correct": "미래예측",
  "match": true,
  "is_dont_know": false,
  "actual_ratio_percent": 32.0
}
```

## 13. GET /weekly — 데모

```http
GET /weekly?user_id=u_demo&week=2026-W21
```

---

## 14. POST /monthly — 월간 리포트 (v9.5 신규)

```json
{
  "month": "2026-05",
  "user_id": "u_123",
  "entries": [ /* 한 달치 entries (약 30개) */ ],
  "drills_recommended": 25,
  "drills_practiced": 18
}
```

### 응답 (`MonthlyReport`) — 6 블록
```json
{
  "month": "2026-05",
  "user_id": "u_123",
  "overview": {"recorded_days": 28, "total_entries": 28, "avg_self_condition": 3.5},
  "dominant_pattern": {"dominant_key": "미래예측", "ratio_percent": 35.0, "occurrences": 7, "total_strong": 20},
  "calendar_distribution": {"distribution": {"emotion_anxiety": 8, "weak_signal_positive": 12, ...}},
  "emotion_pentagon": {"axes": [...], "dominant": "중립", "entries_used": 28},
  "condition_trend": {"weeks": [
    {"week_in_month": 1, "avg_condition": 3.0, "count": 7},
    {"week_in_month": 2, "avg_condition": 3.5, "count": 7},
    ...
  ]},
  "drill_action": {"recommended_count": 25, "practiced_count": 18, "practice_rate": 0.72}
}
```

## 15. GET /monthly — 데모

```http
GET /monthly?user_id=u_demo&month=2026-05
```

---

## 16. POST /insights/user_discovery — "나의 발견" 저장 (v9.5)

```json
{
  "user_id": "u_123",
  "discoveries": ["잠을 충분히 잔 날은 마음이 가벼워요", "감사한 일 한 가지 적는 게 도움이 돼요"]
}
```

사용자가 적은 발견에 키워드 매칭 (잠/수면 → sleep_circadian, 감사/긍정 → self_compassion 등) → 다음 추천 시 affinity 가산.

## 17. GET /insights/user_discovery — 최근 발견 조회

```http
GET /insights/user_discovery?user_id=u_123&limit=5
```

## 18. POST /insights — 주간 발견 (시스템·사용자)

```json
{
  "user_id": "u_123",
  "text": "잠 부족할 때 미래예측 표현이 많아진다",
  "category": "context",
  "week_of": "2026-W21",
  "report_id": 42
}
```

`category`: `cognitive | behavior | emotion | context | drill`

## 19. GET /insights — 토글 UI 조회

```http
GET /insights?user_id=u_123&category=context&source=system
```

## 20. POST /reports — 일요일 cron

```json
{
  "user_id": "u_123",
  "week_of": "2026-W21",
  "pattern_analysis": {"미래예측": 32},
  "emotion_distribution": {"불안": 0.5}
}
```

## 21. GET /reports/pending — 인앱 팝업용

```http
GET /reports/pending?user_id=u_123
```

## 22. PATCH /reports/{id}/read

```http
PATCH /reports/42/read?user_id=u_123
```

---

## 23. POST /calendar — 월간 캘린더

```json
{
  "user_id": "u_123",
  "month": "2026-05",
  "entries": [ /* ... */ ]
}
```

### 응답
```json
{
  "user_id": "u_123",
  "month": "2026-05",
  "days": [
    {
      "date": "2026-05-19",
      "slots": [{"dominant": "emotion_anxiety"}],
      "avg_condition": 3.0
    }
  ]
}
```

v9.5: 일 1회 정책 → `slots` 길이 = 1이 일반. 옛 데이터 호환을 위해 list 유지.

## 24. GET /calendar?demo=true

```http
GET /calendar?user_id=u_demo&month=2026-05&demo=true
```

## 25. POST /daily — 일별 상세 모달

```json
{
  "user_id": "u_123",
  "date": "2026-05-19",
  "entries": [ /* ... */ ]
}
```

응답에 `helpful` 의도적으로 제외 (§9.1 사용자 비공개).

---

## 26. POST /baseline/recompute — 30일 누적 갱신

```json
{
  "user_id": "u_123",
  "entries": [ /* 30일치 */ ],
  "rejected_drills": [17, 77],
  "window_days": 30
}
```

## 27. GET /baseline

```http
GET /baseline?user_id=u_123
```

---

## 28. GET /clarify — LLM 객관식 정밀화 (직접 호출용)

## 29. GET /export, /export/user_data — 사용자 데이터 export

## 30. DELETE /users/{user_id}/data — 회원 탈퇴 시

---

## 운영 (ADMIN_TOKEN 필요)

| Method | Path | 헤더 |
|---|---|---|
| GET | `/healthz/detail` | `X-Admin-Token: <token>` |
| GET | `/metrics` (Prometheus) | 동상 |
| GET | `/metrics/json` | 동상 |
| POST | `/admin/quota/reset` | 동상 (body: `"u_123"`) |

ADMIN_TOKEN 미설정 시 503 — admin 비활성.

---

## 에러 형식 (5 코드)

```json
{
  "detail": {
    "code": "QUOTA_EXCEEDED",
    "message": "quota exceeded (minute, limit=1)",
    "scope": "minute",
    "retry_after_seconds": 60,
    "request_id": "abc123def456"
  }
}
```

| code | HTTP | 의미 |
|---|---|---|
| INVALID_INPUT | 400 | 비즈니스 검증 (FK 없음 등) |
| VALIDATION_ERROR | 422 | Pydantic 타입/길이 위반 |
| QUOTA_EXCEEDED | 429 | 분 1 / 시 3 / 일 3 초과 |
| ML_UNAVAILABLE | 503 | Gemini 다운 |
| INTERNAL_ERROR | 500 | 예외 |
