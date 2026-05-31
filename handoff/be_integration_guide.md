# BE 통합 가이드 (P2 — Spring Boot) v9.5

## 1. ML 서비스 URL

`application.yml`:
```yaml
ml-service:
  url: ${ML_SERVICE_URL:http://localhost:8001}
  admin-token: ${ML_ADMIN_TOKEN:}   # /healthz/detail · /metrics 호출 시
  timeout:
    entries: 12s     # v9.5 통합 (label + recommend)
    label: 10s
    recommend: 3s
    weekly: 5s
    monthly: 8s
    health: 3s
```

호출은 `WebClient` 또는 `RestTemplate` (P2 선택).

## 2. 권장 통합 경로 — POST /entries (v9.5 옵션 C)

BE가 한 번 호출로 label + recommend 받음. ML 두 번 왕복 제거.

```java
EntriesResponse ml = mlClient.post("/entries", Map.of(
    "text", req.getText(),
    "user_id", userId,
    "context", Map.of(
        "self_condition", ctx.getSelfCondition(),
        "sleep_hours", ctx.getSleepHours(),
        "social_today", ctx.getSocialToday(),
        "exercise_today", ctx.getExerciseToday()
    ),
    "recent_drill_ids", recentDrillIds   // List<Integer>
), EntriesResponse.class);
```

응답 필드:
- `label_result` — 라벨링 결과 (BE entries.llm_result에 저장)
- `recommendation` — 드릴 추천 5 type
- `drill_category` — `cognitive_restructuring` 등 (캘린더 색용)
- `drill_category_label` — "생각 전환" 한국어
- `drill_calendar_color` — `pink_soft`, `green_calm` 등 FE 매핑 키
- `context_used` — 정규화 후 ML이 실제 사용한 context (BE 캐시 + 기본값 흔적)

## 3. 응답 매핑 — snake_case → camelCase

```java
@Data
public class LabelResult {
    @JsonProperty("calendar_dominant") String calendarDominant;
    @JsonProperty("crisis_detected") boolean crisisDetected;
    @JsonProperty("model_used") String modelUsed;
    @JsonProperty("labeled_at") OffsetDateTime labeledAt;
    Map<String, Double> patterns;
    Map<String, Double> behaviors;
    Map<String, Double> emotions;
    double intensity;
    double confidence;
    @JsonProperty("evidence_span") String evidenceSpan;
    @JsonProperty("_profanity_detected") Boolean profanityDetected;  // v9.5
}

@Data
public class DrillPayload {
    private int id;                       // v9.5: INT (옛 "D01"도 호환은 됨)
    private String name;
    private String category;
    @JsonProperty("duration_min") private int durationMin;
    private String instruction;
    private String citation;
}

@Data
public class RecommendResponse {
    private String type;
    private DrillPayload drill;
    private Map<String, String> copy;
    @JsonProperty("crisis_resources") private Map<String, String> crisisResources;
    @JsonProperty("user_message") private String userMessage;
    private String message;
    private String question;
    private List<Map<String, String>> options;
    // v9.4.4 ask-first
    @JsonProperty("offer_category") private String offerCategory;
    @JsonProperty("offer_reason_type") private String offerReasonType;
    @JsonProperty("offer_context_value") private Double offerContextValue;
}
```

## 4. ask-first 후속 호출 (v9.4.4/v9.5)

ask_user 응답 받으면 entries(또는 Redis)에 offer_* 보관 → 사용자 응답 시:

```java
RecommendResponse next = mlClient.post("/recommend/after_ask", Map.of(
    "label_result", savedLabelResult,
    "context", savedContext,
    "user_id", userId,
    "user_choice", req.getUserChoice(),   // "yes" | "no"
    "offer_category", savedOfferCategory,
    "offer_reason_type", savedReasonType
), RecommendResponse.class);
```

`user_choice="yes"` + offer_category → 그 카테고리 드릴.
`user_choice="no"` → `type=skip`, 메시지: "기록만 남겨두었어요."

## 5. 위기 응답 (`crisis_card`) — 변형 절대 금지

ML 응답을 그대로 FE 전달. 카피·전화번호 변경 X (§16.2). 일반 드릴 라우팅 X.

## 6. 컨텍스트 캐싱 책임 (BE — v9.5 일 1회 정책)

```java
String dayKey = "ctx:" + userId + ":" + LocalDate.now(KST);
Context cached = redis.get(dayKey);
Context merged = mergeWithCache(req.getContext(), cached);

// 첫 입력이면 캐시 저장 (TTL = KST 자정까지)
if (cached == null) {
    redis.setex(dayKey, ttlUntilKstMidnight(), merged);
}
```

`self_condition`은 매번 받음 (캐시 X). `sleep_hours` / `social_today` / `exercise_today`만 캐시.

ML 측에도 `/context/today` 보조 엔드포인트 있음 (BE 캐시 대안). 정본은 BE.

## 7. 에러 처리

| ML 응답 | BE 처리 |
|---|---|
| 200 | 통과 |
| 400 (`INVALID_INPUT`) | 400 그대로 + 사용자 메시지 |
| 422 (`VALIDATION_ERROR`) | 400 변환 + "텍스트 1~200자 입력" |
| 429 (`QUOTA_EXCEEDED`) | 429 그대로 + Retry-After 헤더 |
| 503 (`ML_UNAVAILABLE`) | 503 + "지금 라벨링이 어려워요" |
| 500 (`INTERNAL_ERROR`) | 500 + request_id 표시 |

모든 에러 응답 body: `{detail: {code, message, request_id, ...}}`.

## 8. 데이터 저장 (BE entries 테이블)

```java
Entry e = new Entry();
e.setText(req.getText());                              // 원문 (PII 마스킹은 ML 호출 직전 자동)
e.setContext(toJsonb(ml.getContextUsed()));            // 정규화 후 context
e.setLlmResult(toJsonb(ml.getLabelResult()));
e.setLlmRecommendation(toJsonb(ml.getRecommendation())); // ask_user의 offer_* 보관용
e.setCalendarDominant(ml.getLabelResult().get("calendar_dominant"));

RecommendResponse rec = ml.getRecommendation();
if ("drill".equals(rec.getType())) {
    e.setDrillId(rec.getDrill().getId());              // INT
    e.setDrillCategory(rec.getDrill().getCategory());
    e.setDrillCalendarColor(ml.getDrillCalendarColor());
}
entryRepo.save(e);
```

`time_of_day` 컬럼은 v9.5 옵셔널 (옛 호환만, 새 데이터에 안 넣어도 OK).

## 9. 동시성

ML은 단일 프로세스 + 메모리 quota. BE 다중 인스턴스 시 한도 분산 미보장 (학부 MVP 허용). 베타 운영 시 user별 격리는 정상.

## 10. CORS

ML은 BE에서만 호출. FE 직접 호출 X. ML 측 `allow_origins=["http://localhost:3000", ...]` 로컬만 허용.

## 11. 운영 엔드포인트 (ADMIN_TOKEN 필요)

```java
HttpHeaders h = new HttpHeaders();
h.add("X-Admin-Token", env.getProperty("ml-service.admin-token"));
mlClient.exchange("/healthz/detail", HttpMethod.GET, new HttpEntity<>(h), Map.class);
```

운영 모니터링용. 사용자 호출 흐름엔 사용 X.

## 12. 일 1회 정책 강제 (BE 책임)

PostgreSQL UNIQUE 인덱스로:
```sql
CREATE UNIQUE INDEX idx_entries_user_day
  ON entries(user_id, DATE(created_at AT TIME ZONE 'Asia/Seoul'));
```

같은 날 두 번째 INSERT 시 `409 Conflict` → BE에서 "오늘 이미 기록하셨어요. 덮어쓸까요?" 안내.

## 13. v9.5 신규 — 나의 발견 (맞춤형 추천)

```java
// 사용자가 주간 리포트에서 "나의 발견" 적을 때
mlClient.post("/insights/user_discovery", Map.of(
    "user_id", userId,
    "discoveries", List.of("잠을 충분히 잔 날은 마음이 가벼워요", "감사한 일 적기가 도움돼요")
), Object.class);
```

이후 추천 시 자동으로 키워드 매칭 → 같은 카테고리 드릴 affinity 가산. BE 추가 작업 X (ML 자동).

## 14. v9.5 신규 — 월간 리포트 (선택)

```java
@Scheduled(cron = "0 0 9 1 * *", zone = "Asia/Seoul")  // 매월 1일 09:00
public void monthlyReports() {
    String month = LocalDate.now(KST).minusMonths(1).format(DateTimeFormatter.ofPattern("yyyy-MM"));
    for (User u : activeUsers()) {
        List<Entry> entries = entryRepo.findByMonth(u.getId(), month);
        mlClient.post("/monthly", Map.of(
            "user_id", u.getId().toString(),
            "month", month,
            "entries", entries.stream().map(this::toMlFormat).toList(),
            "drills_recommended", entries.stream().filter(e -> e.getDrillId() != null).count(),
            "drills_practiced", entries.stream().filter(Entry::isDrillComplete).count()
        ), Object.class);
    }
}
```

6 블록 응답 — overview / dominant_pattern / calendar_distribution / emotion_pentagon / condition_trend / drill_action.
