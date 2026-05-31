# Handoff Changelog

매주 월요일 갱신. P2~P5 영향 사항 통보.

## 2026-05-28 — v9.6 (개인화 강화 + ERD/FE 점검 + 서버 연동)

> 상세 인계: `handoff/v96_personalization_handoff.md`

### 핵심
- **개인화 적응 학습(UCB1) 구현** — `personalization.py`. §11의 "향후 Contextual Bandit 계획"을 실제 기능으로 승격. 사용자의 드릴 완료/도움됨/거부를 누적해 카테고리별 보상을 추정하고 다음 추천에 가산점([0,0.35] clamp)으로 반영. 임상 라우팅은 그대로 우선 — 개인화는 그 위에서만 작동.
- **주간 개인화 코칭 블록** — `weekly_coaching.py`. 한 주를 읽어 상태(회복기/안정기/부담기/소진기/흔들림/낮은 에너지/관찰기) 추론 + "이러할 때 이런 경향" 관찰 narrative + 다음 주 초점. `GET/POST /weekly` 응답에 `weekly_coaching` 추가.

### 신규 엔드포인트
| Method | Path | 설명 |
|---|---|---|
| GET  | `/personalization/profile` | 사용자 카테고리별 학습 프로파일(통계·보상·UCB 가산점) |
| POST | `/personalization/event` | 학습 이벤트 직접 푸시(offer/complete/helpful/reject) — 보조 채널 |
| GET  | `/personalization/next_focus` | 다음 주 추천 초점(프로파일 기반, entries 불필요) |

### 자동 학습 연결 (BE 추가 작업 거의 없음)
- `POST /entries`·`/recommend`·`/recommend/after_ask` → 드릴 노출 자동 기록
- `POST /feedback` → 도움됨/완료 보상 자동 누적
- `POST /reject` → 거부 신호 자동 누적

### BE/FE 영향
- **ERD `entries`에 컬럼 3개 추가 필요**: `context_json`(JSONB), `drill_completed`(BOOL), `helpful`(BOOL). 없으면 주간/월간 리포트·개인화가 동작 못 함. (상세 §1)
- **FE 주간 리포트에 `weekly_coaching` 카드 3개**(이번 주 상태 / 경향 / 다음 주 초점) 추가. 추천 카드 5종(drill/crisis/positive/ask_user/skip) 분기 렌더. (상세 §2)

### 서버/배포
- BE `119.201.125.216:8080` / DB `:5432` 인지. CORS에 BE 출처 자동 포함(`config.allowed_cors_origins`).
- GCP Cloud Run 배포 파일 추가: `ml_service/Dockerfile`(0.0.0.0 + `$PORT`), `ml_service/deploy_gcp.sh`(서울 리전). 배포 URL을 BE `ML_BASE_URL`로 설정.

### 테스트
- 신규 20개 포함 **240개 통과** (3회 반복 안정). 개인화 DB도 user_id SHA-256 해시 저장(평문 0%).

---

## 2026-05-25 — v9.5+ 누적 변경 정리 (BE 명세 호환 + 일 1회 정책)

### 정책 변경
- **하루 1회 입력** (이전 3회) — 1 LLM 호출 + 1 드릴 추천이 한 entry
- **drill_id** 문자열 `"D01"` → **정수 `1`** (BE ERD INT 호환). `get_drill()`은 `legacy_id` 폴백으로 옛 데이터도 매칭.
- **회복 패턴**: 아침/저녁 비교 → **주 전반(월~수) vs 후반(목~일)** (일 1회 정책 정합)
- **ask-first**: 약신호 + 컨디션 나쁨 → 바로 추천 X → "받으실래요?" 먼저 묻기 → `POST /recommend/after_ask`로 후속
- **욕설 감지**: intensity +0.3 / confidence +0.1 (Mock·실 LLM 양쪽 적용 — v9.5)
- **감정 5개 유지**: 행복/기쁨 차원 추가 X (W4 이후 결정)

### 신규 엔드포인트
| Method | Path | 설명 |
|---|---|---|
| POST | `/entries` | BE 통합 — label + recommend 한 번 호출. 옵션 C 호환. 응답에 drill_category/label/calendar_color 포함 |
| POST | `/recommend/after_ask` | ask_user 응답 후 사용자 선택 처리 (yes + offer_category → 약속 카테고리 드릴) |
| POST | `/monthly` | 월간 리포트 (BE entries 전달) |
| GET  | `/monthly` | 월간 리포트 (데모 entries 자동) |
| POST | `/insights/user_discovery` | 사용자 "나의 발견" 저장 → 다음 추천 affinity 가산 |
| GET  | `/insights/user_discovery` | 최근 발견 조회 |

### 옛 엔드포인트 유지
- `POST /label` + `POST /recommend` 따로 호출도 그대로 지원 — BE가 선택해서 사용 가능

### 신규 응답 필드
- `EntriesResponse`: `drill_category` / `drill_category_label`(한국어) / `drill_calendar_color`(FE 매핑 키)
- `RecommendResponse.offer_category` / `offer_reason_type` / `offer_context_value` (ask-first)
- `WeeklyReport.discoveries[].pattern_type`: `recovery`/`fatigue`/`early_load`/`late_load` (v9.5 — 옛 morning_load/evening_load 폐기. alias `diurnal_recovery_pattern`은 호환만 유지)

### BE 영향
- `POST /entries` 한 번 호출로 끝 → `entries` 테이블에 응답 그대로 저장 가능
- `time_of_day` 필드 더 이상 필수 X — 보내도 무시 (옛 호환만)
- ask_user 응답의 `offer_*` 필드는 entries 또는 Redis에 보관 → `/recommend/after_ask` 호출 시 재전송
- `helpful` BOOL: helpful=true / unhelpful=false / meh=NULL

### FE 영향
- 5 type 분기 그대로 + ask_user의 v9.4.4 ask-first 카드 추가 처리
- `discoveries[].pattern_type` 4종 (recovery/fatigue/early_load/late_load) 강조 UI
- 자가진단 퀴즈 `correct_value` 응답에 노출 X (server-side cache) — 메타인지 측정 보호
- "맞췄어요/틀렸어요" 표현 X. 정답: X · 비율 Y%만

### P5 영향
- `_DRILL_OFFER_CONFIG` 3 템플릿 (low_condition / short_sleep / social_conflict) 톤 검수
- 드릴 카탈로그 `drill_id` INT 마이그레이션 완료 — 새 드릴 추가 시 INT id 사용

### 테스트
- **207/207 PASS** (3회 안정). monthly 10건 + v9.5 changes 11건 + v9.5 design 9건 신규.

### 옛 정책 잔존 (마이그레이션 호환)
- `time_of_day`는 응답·요청 모두 옵셔널 — 옛 데이터 호환만
- `diurnal_recovery_pattern` 함수 alias — 옛 import 호환

---

## 2026-05-23 — 주간 리포트 확장 (v9.4.3)

**신규 응답 필드 (`GET /weekly`)**:
- `emotion_pentagon` — 5감정 평균 (불안/우울/분노/죄책/중립) 오각형 radar chart 데이터
- `discoveries[].pattern_type` — diurnal 회복/소진 패턴 (4 종류: recovery/fatigue/morning_load/evening_load)

**BE 영향**:
- `POST /weekly` 호출 시 entries에 `time_of_day` 필드 (morning/afternoon/evening) **필수** — diurnal 분석에 사용
- 기존 BE 코드는 `time_of_day` 누락해도 동작은 함 (diurnal 카드만 미생성)

**FE 영향**:
- 5각형 radar chart 컴포넌트 신규 필요 (d3 / recharts 권장)
- discoveries에서 `pattern_type` 있는 카드 별도 강조 UI

**테스트**: 174/174 PASS (3회 안정).

---

## 2026-05-22 — W2 완료

- `POST /label`, `POST /recommend`, `GET /healthz` 신규 (api_contract.md 정본).
- 응답 5 type 분기: `drill | crisis_card | positive_card | ask_user | skip`.
- 에러 코드 5종 합의 (error_codes.md).
- 위기 응답 카드 형식 확정 (crisis_response_protocol.md).
- ML→Gemini 외부 호출은 현재 미활성 (API 키 발급 전), Mock 폴백으로 동작.

**P2 영향**: 위 3 엔드포인트 호출 가능. snake_case JSON, 422·429·500 처리.
**P3 영향**: 5 type 카드 UI 분기 필요.
**P4 영향**: `calendar_dominant` 키 9 enum (부록 C).
**P5 영향**: 카피 정본 §10 사용. 변경 시 협의.
