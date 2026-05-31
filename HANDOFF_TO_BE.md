# BE(P2)에게 인계 — v9.5

> Spring Boot 3 + Java 17 + PostgreSQL + Redis 영역(P2)에 ML 서비스가 어떻게 합쳐지는지.

## 1. 받을 파일

```
stepback/
├── ml_service/             ← 전체 폴더 (P2가 별도 호스트에서 실행)
├── handoff/                ← 8개 마크다운 — 계약 정본
│   ├── api_contract.md          ← v9.5 갱신 — 30 엔드포인트 명세
│   ├── error_codes.md
│   ├── crisis_response_protocol.md
│   ├── be_integration_guide.md  ← 이거 최우선
│   ├── fe_integration_guide.md
│   ├── calendar_color_spec.md
│   ├── content_guide.md
│   └── changelog.md             ← v9.5 변경 사항 맨 위
└── docs/                   ← 참조용
```

`.env`, `logs/`, `ml_service/data/*.db`는 보내지 않음 (보안 + 사용자 데이터).

## 2. v9.5 핵심 — BE 통합 시 가장 중요

### 2.1 권장 통합 — POST /entries (옵션 C)

BE가 한 번 호출로 label + recommend 받음. ML 두 번 왕복 제거.

```java
@PostMapping("/api/entries")
public ResponseEntity<EntryResponse> createEntry(@RequestBody EntryRequest req, Authentication auth) {
    String userId = auth.getName();

    // 1. 컨텍스트 캐싱 (일 1회 정책 — BE 책임)
    String dayKey = "ctx:" + userId + ":" + LocalDate.now(KST);
    Context cached = redis.get(dayKey);
    Context merged = mergeWithCache(req.getContext(), cached);
    if (cached == null) redis.set(dayKey, merged, ttlUntilKstMidnight());

    // 2. ML 한 번 호출 — label + recommend 통합
    EntriesMlResponse ml = mlClient.post("/entries", new MlEntriesRequest(
        req.getText(),
        userId,
        merged,
        recentDrillIdsFromDb(userId, 3)  // INT 리스트
    ), EntriesMlResponse.class);

    // 3. BE entries 테이블 INSERT
    Entry e = new Entry();
    e.setUserId(userId);
    e.setText(req.getText());
    e.setContext(toJsonb(ml.getContextUsed()));
    e.setLlmResult(toJsonb(ml.getLabelResult()));
    e.setCalendarDominant(ml.getLabelResult().get("calendar_dominant"));
    e.setDrillCategory(ml.getDrillCategory());          // FE 캘린더 색용
    e.setDrillCalendarColor(ml.getDrillCalendarColor());
    if ("drill".equals(ml.getRecommendation().getType())) {
        e.setDrillId(ml.getRecommendation().getDrill().getId());  // INT
    }
    entryRepo.save(e);

    return ResponseEntity.ok(new EntryResponse(e.getEntryId(), ml));
}
```

응답 구조 (Java DTO):
```java
@Data
public class EntriesMlResponse {
    private String text;
    @JsonProperty("context_used") private Map<String, Object> contextUsed;
    @JsonProperty("label_result") private Map<String, Object> labelResult;
    private RecommendResponse recommendation;
    @JsonProperty("drill_category") private String drillCategory;
    @JsonProperty("drill_category_label") private String drillCategoryLabel;
    @JsonProperty("drill_calendar_color") private String drillCalendarColor;
    @JsonProperty("labeled_at") private OffsetDateTime labeledAt;
}

@Data
public class RecommendResponse {
    private String type;             // drill | crisis_card | positive_card | ask_user | skip
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

@Data
public class DrillPayload {
    private int id;                  // v9.5: INT (옛 "D01" 문자열 → 1)
    private String name;
    private String category;
    @JsonProperty("duration_min") private int durationMin;
    private String instruction;
    private String citation;
}
```

### 2.2 ask-first 후속 호출 (v9.4.4/v9.5)

ask_user 응답 받으면 entries 테이블이나 Redis에 `offer_*` 임시 저장 후:

```java
@PostMapping("/api/entries/{entryId}/ask-answer")
public ResponseEntity<RecommendResponse> answerAsk(
    @PathVariable Long entryId,
    @RequestBody AskAnswerRequest req,    // {user_choice: "yes"|"no"}
    Authentication auth
) {
    Entry e = entryRepo.findById(entryId).orElseThrow();
    Map<String, Object> prevRec = fromJsonb(e.getLlmRecommendation());

    RecommendResponse next = mlClient.post("/recommend/after_ask", Map.of(
        "label_result", fromJsonb(e.getLlmResult()),
        "context", fromJsonb(e.getContext()),
        "user_id", auth.getName(),
        "user_choice", req.getUserChoice(),
        "offer_category", prevRec.get("offer_category"),
        "offer_reason_type", prevRec.get("offer_reason_type")
    ), RecommendResponse.class);

    if ("drill".equals(next.getType())) {
        e.setDrillId(next.getDrill().getId());
        entryRepo.save(e);
    }
    return ResponseEntity.ok(next);
}
```

### 2.3 옛 호환 — 분리 호출도 그대로 지원

BE가 원하면 `POST /label` + `POST /recommend` 분리 호출도 가능. 새 통합 권장이지만 BC 유지.

## 3. P2가 할 일 — 6단계

### 1) ML 서비스 띄우기

```powershell
# Windows
cd ml_service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADMIN_TOKEN = "<강한 토큰>"   # 운영 endpoints 보호
$env:FORCE_MOCK = "true"            # Gemini 키 없으면 그대로
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir .
```

```bash
# Linux/Mac
cd ml_service && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_TOKEN=...
export FORCE_MOCK=true
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir .
```

확인: `curl http://127.0.0.1:8001/healthz` → 200 + `drills_loaded: 77`.

### 2) Spring Boot 설정

`application.yml`:
```yaml
ml-service:
  url: ${ML_SERVICE_URL:http://localhost:8001}
  admin-token: ${ML_ADMIN_TOKEN:}     # /healthz/detail · /metrics 호출 시
  timeout:
    label: 10s
    recommend: 3s
    entries: 12s      # label + recommend 합산
    weekly: 5s
    monthly: 8s
    health: 3s
  retry:
    max-attempts: 2
```

### 3) BE 책임 영역

| 책임 | 위치 |
|---|---|
| 사용자 인증 (Google OAuth) | Spring Security + NextAuth (FE) |
| `users` 테이블 | PostgreSQL |
| `entries` 테이블 — 입력 텍스트 저장 + ML 결과 캐시 | PostgreSQL (ML은 텍스트 보관 X) |
| `reports` / `insights` / `baselines` | PostgreSQL (ML SQLite는 학습 미러만) |
| 컨텍스트 캐싱 (Redis, 일 1회) | 본문 §2.1 |
| 주간 리포트 일요일 20:00 cron + 메일 발송 | Spring `@Scheduled` |
| 월간 리포트 매월 1일 cron (선택) | Spring `@Scheduled` |
| 일별 자정 baseline 갱신 (선택, W5 이후) | Spring `@Scheduled` |

### 4) 일요일 cron — 주간 리포트

```java
@Scheduled(cron = "0 0 20 * * SUN", zone = "Asia/Seoul")
public void generateWeeklyReports() {
    String week = isoWeekOf(LocalDate.now(KST).minusDays(1));

    for (User u : activeUsersLastWeek()) {
        try {
            // 1. /reports row 생성 (pending)
            mlClient.post("/reports", Map.of(
                "user_id", u.getId().toString(),
                "week_of", week,
                "pattern_analysis", computePatternAnalysis(u, week),
                "emotion_distribution", computeEmotionDist(u, week)
            ), Object.class);

            // 2. 메일 발송
            mailer.send(u.getEmail(),
                "이번 주 자가진단 퀴즈가 준비됐어요",
                emailTemplate.render(u, week));
        } catch (Exception ex) {
            log.error("주간 리포트 생성 실패 user={}", u.getId(), ex);
        }
    }
}
```

### 5) 월간 리포트 — v9.5 신규 (선택)

```java
@Scheduled(cron = "0 0 9 1 * *", zone = "Asia/Seoul")  // 매월 1일 09:00
public void generateMonthlyReports() {
    String month = LocalDate.now(KST).minusMonths(1).format(DateTimeFormatter.ofPattern("yyyy-MM"));

    for (User u : activeUsers()) {
        List<Entry> entries = entryRepo.findByMonth(u.getId(), month);
        MonthlyReport report = mlClient.post("/monthly", Map.of(
            "user_id", u.getId().toString(),
            "month", month,
            "entries", entries.stream().map(this::toMlFormat).toList(),
            "drills_recommended", entries.stream().filter(e -> e.getDrillId() != null).count(),
            "drills_practiced", entries.stream().filter(Entry::isDrillComplete).count()
        ), MonthlyReport.class);
        // BE에 caching or 사용자에게 메일 알림 등
    }
}
```

### 6) 에러 처리 매핑

| ML 응답 | BE 처리 |
|---|---|
| 200 | 그대로 통과 |
| 400 INVALID_INPUT | 400 그대로 + 사용자 메시지 |
| 422 VALIDATION_ERROR | 400 + "텍스트 1~200자 입력" |
| 429 QUOTA_EXCEEDED | 429 + Retry-After 헤더 (FE 카운트다운) |
| 503 ML_UNAVAILABLE | 503 + "지금 라벨링이 어려워요" |
| 500 INTERNAL_ERROR | 500 + request_id 표시 (디버깅용) |

위기 응답 (`crisis_card`)은 그대로 FE 전달 — 카피·전화번호 변경 X.

## 4. ML이 제공하는 30 엔드포인트 (v9.5)

| 카테고리 | Method | Path | 비고 |
|---|---|---|---|
| 헬스/운영 | GET | `/healthz` | 공개 |
| | GET | `/healthz/detail` | ADMIN |
| | GET | `/metrics` (Prometheus) | ADMIN |
| | GET | `/metrics/json` | ADMIN |
| | POST | `/admin/quota/reset` | ADMIN |
| **통합** | POST | `/entries` ⭐ | **BE 권장 — label+recommend 한 번** |
| 라벨링 | POST | `/label` | 옛 호환 |
| 컨텍스트 | GET / POST | `/context/today` | 옵션 (Redis 대안) |
| 추천 | POST | `/recommend` | 옛 호환 |
| | POST | `/recommend/after_ask` | ask-first 후속 |
| | POST | `/clarify` | LLM 정밀화 직접 호출 |
| 드릴 | GET | `/drills/{id}` | INT or "D01" 호환 |
| | GET | `/drills` | 카탈로그 |
| | POST | `/reject` | "아닌 것 같아요" |
| 평가 | POST / GET | `/feedback` | 점수 GET 비공개 |
| 주간 | GET / POST | `/weekly` | 5블록 + 시각화 + 발견 |
| | PATCH | `/weekly/quiz` | 자가진단 답 |
| | POST | `/weekly/condition_flow` | 7일 라인 |
| | POST | `/weekly/pattern_diff` | 이번주 vs 지난주 |
| **월간** | GET / POST | `/monthly` ⭐v9.5 | **약 30일 entries 기반 6 블록** |
| Baseline | POST | `/baseline/recompute` | 30일 누적 |
| | GET | `/baseline` | 학습 전용 |
| 발견 | POST / GET | `/insights` | 시스템·사용자 |
| **나의 발견** | POST / GET | `/insights/user_discovery` ⭐v9.5 | **추천 affinity 가산** |
| Reports | POST | `/reports` | 일요일 cron |
| | GET | `/reports/pending` | 팝업용 |
| | PATCH | `/reports/{id}/read` | 읽음 |
| 캘린더 | GET / POST | `/calendar` | 월간 dominant |
| | POST | `/daily` | helpful 비공개 |
| 데이터 | GET | `/export`, `/export/user_data` | 사용자 권리 |
| | DELETE | `/users/{user_id}/data` | 회원 탈퇴 |

자세히: `handoff/api_contract.md`.

## 5. BE PostgreSQL DDL (v9.5)

```sql
-- users
CREATE TABLE users (
  user_id BIGSERIAL PRIMARY KEY,
  username VARCHAR(20) NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ
);

-- entries (v9.5: drill_id INT, time_of_day 옵셔널)
CREATE TABLE entries (
  entry_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  text VARCHAR(200) NOT NULL,
  context JSONB NOT NULL,
  llm_result JSONB NOT NULL,
  llm_recommendation JSONB,            -- ask_user 응답의 offer_* 보관용
  drill_id INTEGER,                    -- v9.5 INT (옛 VARCHAR(8)에서 마이그레이션)
  drill_category VARCHAR(32),          -- 캘린더 색용
  drill_calendar_color VARCHAR(16),    -- FE 매핑 키
  drill_complete BOOLEAN DEFAULT FALSE,
  helpful BOOLEAN,                     -- helpful=true / unhelpful=false / meh=NULL
  time_of_day VARCHAR(16),             -- v9.5 옵셔널 (옛 호환만)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  feedback_at TIMESTAMPTZ
);

-- 일 1회 정책: 같은 user, 같은 날 UNIQUE
CREATE UNIQUE INDEX idx_entries_user_day
  ON entries(user_id, DATE(created_at AT TIME ZONE 'Asia/Seoul'));
CREATE INDEX idx_entries_user_created ON entries(user_id, created_at DESC);

-- reports (주간)
CREATE TABLE reports (
  report_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  week_of VARCHAR(10) NOT NULL,
  pattern_analysis JSONB NOT NULL,
  emotion_distribution JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  read_at TIMESTAMPTZ,
  UNIQUE(user_id, week_of)
);

-- insights (시스템·사용자)
CREATE TABLE insights (
  insight_id BIGSERIAL PRIMARY KEY,
  report_id BIGINT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  source VARCHAR(8) NOT NULL,     -- 'system' | 'user'
  category VARCHAR(16) NOT NULL,  -- cognitive/behavior/emotion/context/drill
  week_of VARCHAR(10) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- baselines (학습 전용 — 사용자 노출 X)
CREATE TABLE baselines (
  baseline_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
  patterns_avg JSONB NOT NULL,
  behaviors_avg JSONB NOT NULL,
  rejected_drills JSONB NOT NULL DEFAULT '[]'::jsonb,  -- INT 배열
  sample_count INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- v9.5: 사용자 발견 (나의 발견)
CREATE TABLE user_discoveries (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_user_discoveries_user ON user_discoveries(user_id, created_at DESC);

-- 자가진단 답
CREATE TABLE quiz_answers (
  answer_id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  week_of VARCHAR(10) NOT NULL,
  predicted VARCHAR(20) NOT NULL,
  correct VARCHAR(20) NOT NULL,
  gap INT NOT NULL,
  answered_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, week_of)
);

-- rejected_drills (INT)
CREATE TABLE rejected_drills (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  drill_id INTEGER NOT NULL,
  rejected_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, drill_id)
);
```

## 6. 통합 테스트 시나리오 8 (BE에서 해주면 좋은)

| # | 시나리오 | 기대 |
|---|---|---|
| 1 | 회원가입 → `/api/entries` 1회 | 200 + drill 또는 5 type 중 하나 |
| 2 | 같은 사용자 분당 2번째 | 429 + Retry-After |
| 3 | 위기 텍스트 → `crisis_card` | 일반 드릴 0 |
| 4 | 빈 텍스트 | 422 VALIDATION_ERROR |
| 5 | 같은 날 두 번째 entry | BE 409 ("덮어쓸까요?") |
| 6 | ask_user 응답 → /ask-answer (yes) → drill | offer_category 카테고리 일치 |
| 7 | 일요일 cron → `/reports/pending` 1건 | 다음 접속 시 팝업 |
| 8 | 12명 동시 입력 | 모두 200 (user 격리) |

## 7. 보안 필수

- **ADMIN_TOKEN 환경변수 강제** (미설정 시 admin 엔드포인트 503)
- **ML 호스팅 — 127.0.0.1만 listen**. 외부 노출 절대 X.
- **위기 응답 카피·전화번호 변형 절대 X** (§16.2)
- **사용자 텍스트는 BE DB만**. ML은 hash + 요약만 audit log.
- **회원 탈퇴 시 ML 데이터도 삭제**: `DELETE /api/users/me` → ML `/users/{id}/data` 호출.

## 8. P1에게 합의 필요 (체크리스트)

1. 위기 응답 직후 quota 면제 정책? (현재는 동일 quota)
2. 같은 날 두 번째 entry — 덮어쓰기 vs 강제 거부?
3. ask_user 응답 보관 방식 — `entries.llm_recommendation` vs Redis?
4. 메일 게이트웨이 (학교 SMTP vs SendGrid)?
5. 인증 — Google OAuth만 vs 비밀번호 병행?
6. 옛 데이터 마이그레이션 — drill_id "D01" → 1 변환 스크립트 필요?

질문은 P1에게.
