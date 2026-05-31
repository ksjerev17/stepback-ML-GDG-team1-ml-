# v9.6 인계 — 개인화 강화 + ERD/FE 점검 + 서버 연동

> 작성: ML(P1). 대상: BE(P2)·FE(P3)·기획.
> 이번 변경의 핵심 한 줄: **"시스템이 사용자와 함께 변화한다"를 실제 코드로 구현했고, 그걸 사용자에게 보여주는 주간 코칭 블록을 추가했다.**
> 발표 피드백("핵심 기능이 안 보인다 / 시연으로 보여줘라")에 대한 답: 이 개인화 루프가 바로 시연용 핵심 기능입니다.

---

## 0. 한눈에 — 무엇이 바뀌었나

| 구분 | 내용 |
|---|---|
| 신규 모듈 | `app/core/personalization.py` (UCB1 적응 학습), `app/core/weekly_coaching.py` (주간 상태 추론·경향·다음 주 초점) |
| 신규 엔드포인트 | `GET /personalization/profile`, `POST /personalization/event`, `GET /personalization/next_focus` |
| 기존 응답 확장 | `GET/POST /weekly` 응답에 `weekly_coaching` 블록 추가 |
| 자동 학습 연결 | `POST /entries`·`POST /recommend`(드릴 노출), `POST /feedback`(도움됨/완료), `POST /reject`(거부)가 개인화를 자동 갱신 |
| 서버 연동 | BE `119.201.125.216:8080` / DB `:5432` 인지. CORS 자동 허용. GCP Cloud Run 배포 파일(`Dockerfile`, `deploy_gcp.sh`) |
| 테스트 | 신규 20개 포함 **240개 전부 통과** (3회 반복 안정) |

---

## 1. ERD 점검 결과 — 수정 필요 (중요도 순)

업로드된 ERD(6테이블: `users`, `entries`, `reports_weekly`, `reports_monthly`, `baselines`, `insights_user`)를 ML이 실제로 주고받는 데이터와 대조했습니다. 테이블 구성·이름 변경(`insights → insights_user`, `reports → weekly/monthly` 분리)은 적절합니다. 다만 **`entries` 테이블에 빠진 컬럼이 있어 그대로 두면 주간/월간 리포트가 동작하지 않습니다.**

### 🔴 P0 — `entries`에 `context` 저장 컬럼이 없음 (반드시 추가)

ML의 주간·월간 리포트는 입력 당시의 **맥락(컨디션·수면)** 을 반드시 다시 읽습니다.

- `condition_flow` (요일별 컨디션 흐름) → `self_condition` 필요
- `weekly_recovery_pattern` (주 전반/후반 회복·소진) → `self_condition` + `created_at` 필요
- `context_pattern_correlation` (수면 6h 미만 vs 7h↑ 패턴 차이) → `context.sleep_hours` 필요
- `weekly_coaching`(신규)의 경향 narrative("잠 못 잔 날 미래예측↑") → `context.sleep_hours` + `self_condition` 필요

그런데 ERD `entries`에는 컨디션/수면을 담을 칸이 없습니다. BE 통합 가이드 코드(`e.setContext(toJsonb(ml.getContextUsed()))`)는 이미 저장을 전제하고 있으니, **ERD만 누락된 상태**입니다.

**권장 수정:**
```sql
ALTER TABLE entries ADD COLUMN context_json JSONB;     -- ML이 반환한 context_used 그대로 저장
-- context_json 예: {"self_condition":2,"sleep_hours":5.0,"social_today":"보통","exercise_today":0.0}
```
(조회 빈도가 높으면 `self_condition SMALLINT`, `sleep_hours REAL`를 별도 컬럼으로 빼서 인덱스해도 됩니다. 최소 요건은 위 JSONB 하나.)

### 🔴 P0 — `entries`에 드릴 완료/도움됨 컬럼이 없음

와이어프레임의 "완료 드릴 수 6/7", 일별 기록 체크표시(✓), 주간 리포트의 **드릴 실천율**과 **"가장 효과적이었던 드릴" 발견**, 그리고 이번 v9.6 **개인화 보상 학습**이 전부 이 두 값에 의존합니다. 인계 명세(§9)는 "feedbacks를 entries에 병합"한다고 했는데 ERD엔 반영되지 않았습니다.

**권장 수정:**
```sql
ALTER TABLE entries ADD COLUMN drill_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE entries ADD COLUMN helpful BOOLEAN;          -- NULL=미평가 / true=도움됨 / false=아님
```
BE는 사용자가 드릴 완료·평가 시 이 컬럼을 갱신하고, 그 값을 ML `POST /feedback`(또는 `/personalization/event`)로 전달하면 개인화가 학습됩니다(§3 참조).

### 🟡 P1 — `baselines.snapshot_json` 내부 구조 문서화

ERD 주석의 "어떤 것에 대한 누적?" 질문 답: ML이 채우는 `snapshot_json`은 다음 형태입니다.
```json
{
  "patterns_avg":  {"미래예측":0.32, ...},   // 6 인지패턴 30일 평균
  "behaviors_avg": {"회피미루기":0.18, ...}, // 2 행동 평균
  "emotions_avg":  {"불안":0.41, ...},        // 5 감정 평균
  "rejected_drills":[12, 45],                  // 거부 드릴 id (INT)
  "sample_count": 27, "window_days": 30
}
```
컬럼 구조는 그대로 두되, 위 형태를 ERD 주석/명세에 적어두면 BE가 역직렬화할 때 안전합니다.

### 🟢 P2 — 선택 개선
- `insights_user`에 `week_of VARCHAR(10)` 추가하면 "어느 주의 발견인지" 구분 가능(현재는 created_at으로 추정).
- `entries.awaiting_answer` / `offered_category`는 ask-first 흐름에 잘 맞습니다(그대로 유지). 단 사용자가 다음 날 응답을 안 하면 자동 만료(다음 입력 시 reset)하는 규칙을 BE가 정해두면 좋습니다.

> 요약: **`entries`에 `context_json`, `drill_completed`, `helpful` 3개 컬럼만 추가하면 ERD는 ML과 완전히 정합**됩니다. 나머지는 문서화 수준.

---

## 2. 와이어프레임 기준 — FE가 추가/보완할 부분

화면을 ML 응답과 대조했습니다. (디자인은 좋습니다. 아래는 "데이터를 다 보여주려면 필요한 것" 목록.)

### 2-1. 일일 입력 화면 (마음 챙김 일기 + 오늘의 상태)
- 현재 와이어프레임엔 **컨디션 슬라이더 + 수면 시간**만 있습니다.
- ML 추천은 `social_today`(좋음/보통/갈등)와 `exercise_today`(운동 시간)도 사용합니다(자기자비·행동활성화 보너스). **둘 다 없어도 동작은 하지만**(기본값 보통/0), 있으면 추천 품질이 올라갑니다. → 선택 입력 2개 추가 권장(접어두기 가능).
- 입력 후 추천 카드는 `recommendation.type` 5종을 분기 렌더해야 합니다: `drill`(드릴 카드) / `crisis_card`(상담 안내 — 1393 등) / `positive_card`("평온한 하루") / `ask_user`(받으실래요? Yes/No 버튼) / `skip`. 와이어프레임엔 drill 카드만 보여서, **나머지 4종 카드 디자인이 필요**합니다. 특히 `ask_user`는 사용자가 Yes를 누르면 `offer_category`를 그대로 담아 `POST /recommend/after_ask`를 호출해야 합니다.

### 2-2. 캘린더 화면
- 각 날짜 색은 `entries.drill_calendar_color`(예: `green_calm`, `pink_soft`)를 **디자인 토큰 hex로 매핑**해야 합니다. 키→hex 매핑은 `handoff/calendar_color_spec.md`에 있습니다. 와이어프레임은 색만 칠해져 있고 매핑 규칙 연결이 필요합니다.

### 2-3. 주간 리포트 화면 (가장 중요 — 핵심 기능 시연 포인트)
와이어프레임의 주간 리포트엔 일일 드릴 기록 / 감정 오각형 / 생활 지표 / 컨디션 흐름 / 패턴 변화 / 이번 주 발견 / 나의 발견이 있습니다. **여기에 v9.6 신규 `weekly_coaching` 블록을 위한 영역이 필요합니다.** 응답 `weekly_coaching` 구조:
```jsonc
"weekly_coaching": {
  "state": { "key":"recovery", "label":"회복기",
             "summary":"한 주 후반으로 갈수록 컨디션이 올라오는 흐름이에요 (전반 2.0 → 후반 4.3)." },
  "tendencies": [
    { "kind":"sleep_pattern", "text":"잠이 6시간 미만이던 날엔 '미래예측' 표현이 더 자주 보였어요.",
      "detail":"평균 0.63 vs 충분히 잔 날 0.05" }
  ],
  "next_week_focus": { "category":"grounding", "label_ko":"마음 챙김",
                       "reason":"한 주가 무거웠던 만큼, 다음 주엔 마음을 먼저 가라앉히는 연습이 도움이 될 수 있어요." },
  "personalization_note": { "text":"지금까지 '자기 자비' 계열 드릴이 가장 도움이 되셨어요 (3회 도움됨 / 4회 추천).",
                            "is_active":true, "top_category_label":"자기 자비" },
  "insufficient": false
}
```
**FE 권장 카드 3개:**
1. **이번 주 상태** — `state.label`을 큰 배지로 + `state.summary` 한 줄. (회복기/안정기/부담기/소진기/흔들림/낮은 에너지/관찰기)
2. **이런 경향이 보였어요** — `tendencies[]`를 불릿으로. 비어있고 `tendencies_message`가 있으면 그 안내문 표시.
3. **다음 주엔** — `next_week_focus.label_ko` + `reason`. (+ `personalization_note.text`가 있으면 "지금까지 ~가 잘 맞으셨어요" 작은 글씨)

`insufficient:true`(기록 4일 미만)면 세 카드 대신 "며칠 더 모이면 보여드릴게요" 안내 하나만.

### 2-4. 마이페이지 / 회원정보 (예정 → 구현 필요)
- 인계 진행상황상 "마이페이지·회원정보 수정"이 예정 상태였습니다. 와이어프레임은 있으니 BE의 회원정보 수정 API에 연결만 하면 됩니다(ML 무관).
- **개인화 초기화 버튼**(선택): 사용자가 원하면 `DELETE` 계열로 개인화 데이터 리셋 — ML은 `personalization.reset_user(user_id)`를 제공합니다. BE가 래핑하거나, 필요하면 ML에 엔드포인트 추가 가능.

> Git 레포 구현이 적었다는 피드백은 주로 FE 화면 완성도였을 가능성이 큽니다. 위 2-1~2-3을 채우면 "입력→추천→주간 코칭"의 한 바퀴가 시연으로 완결됩니다.

---

## 3. BE(P2)가 해야 할 일 — 개인화 자동 연동

좋은 소식: **대부분 자동입니다.** BE가 이미 호출하는 엔드포인트가 알아서 학습합니다.

| BE가 이미 호출하는 것 | ML이 자동으로 하는 일(v9.6) |
|---|---|
| `POST /entries` | 드릴 추천 시 그 카테고리를 "노출(offer)"로 기록 |
| `POST /recommend`, `/recommend/after_ask` | 동일하게 노출 기록 |
| `POST /feedback` (rating) | `helpful`→보상 1.0, 그 외 완료→0.5 누적 |
| `POST /reject` | 거부 신호 누적(약한 음의 보상) |

**BE가 추가로 신경 쓸 것은 단 하나** — `entries`에 `context_json`·`drill_completed`·`helpful` 컬럼 추가(§1) 후, 드릴 완료/평가가 일어나면 그 사실을 ML `POST /feedback`로 전달(이미 계약에 있음). 그러면 다음 추천부터 개인화가 반영됩니다.

선택: 주간 리포트 화면을 빠르게 그리고 싶으면 `GET /personalization/profile?user_id=`로 "지금까지 가장 잘 맞은 카테고리"를 바로 받을 수 있습니다(주간 entries 재전송 없이).

`next_week_focus`를 다음 주 추천에 반영하고 싶다면: 그대로 둬도 ML 내부 UCB 가산점이 자동 반영하므로 추가 작업 불필요. 명시적으로 강제하고 싶으면 BE가 `next_week_focus.category`를 저장해뒀다가 다음 주 첫 추천의 힌트로 쓰는 정도(선택).

### 서버/배포 (BE·인프라 공통)
- ML은 BE `119.201.125.216:8080` / DB `:5432`를 인지합니다(`config.py`). **CORS에 BE 출처가 자동 포함**되므로 BE가 ML을 직접 호출할 때 막히지 않습니다.
- ML을 **GCP Cloud Run**에 올리는 파일을 추가했습니다: `ml_service/Dockerfile`(0.0.0.0 바인딩 + `$PORT`), `ml_service/deploy_gcp.sh`(빌드→배포 자동, 서울 리전). 배포 후 출력되는 URL을 **BE의 `ML_BASE_URL` 환경변수**로 설정하면 됩니다.
- 실 LLM(Gemini)을 쓰려면 GCP에서 `FORCE_MOCK=false` + `GEMINI_API_KEY` 주입. 키 없으면 자동 Mock 폴백이라 배포 자체는 키 없이도 성공합니다.

> ⚠️ 솔직한 한계: ML 작업자(저)는 `119.201.125.216`·GCP에 직접 접속/배포할 권한·네트워크가 없어 **코드·설정·배포 스크립트까지** 준비했습니다. 실제 `gcloud` 실행과 BE 서버 기동은 인프라 담당이 위 스크립트로 진행해야 합니다.

---

## 4. ML 파트 — 완료 상태 (이전 "예정/미구현" 정리)

인계 §14의 ML 항목을 모두 처리했습니다.

| 이전 상태 | 항목 | v9.6 결과 |
|---|---|---|
| 수정·검토 예정 | 사용자 발견 → 맞춤 추천 가산 | ✅ 완료(v9.5에 이미 있었고 v9.6에서 개인화 프로파일과 통합) |
| 수정·검토 예정 | 프롬프트 anchor 튜닝 | ✅ 확정(`w1/labeling_prompt_v3.md` 기준 동결, Mock·실 LLM 동일 anchor) |
| 미구현 | Contextual Bandit 개인화(베타 후) | ✅ **구현 완료** — UCB1 방식 `personalization.py`. "향후 계획"에서 "현재 기능"으로 승격 |
| 미구현 | 실 LLM 부하 테스트 | 🟡 코드·배포 준비 완료, 실제 부하 측정은 GCP 기동 후 (외부 환경 필요) |

**남는 단 하나(외부 의존):** GCP에 실제로 띄워 실 Gemini로 부하를 재보는 것. 이건 인프라 접근이 있어야 가능하고, 코드는 준비됐습니다.

테스트: `pytest` **240개 통과**(신규 20개 = 개인화 8 + 코칭 9 + 엔드포인트 3 + 기타). 3회 반복 동일 결과. (참고: `ADMIN_TOKEN` 환경변수 미설정 시 admin 관련 테스트 4개가 skip/1개 fail로 보일 수 있는데, `ADMIN_TOKEN=dev_token_local` 설정 시 전부 통과 — 코드 문제 아님.)

---

## 5. 설계 원칙 — 발표 Q&A 대비

- **개인화가 임상 안전을 덮어쓰지 않음.** UCB 가산점은 [0, 0.35]로 상한(clamp). 위기/인지/행동 라우팅이 먼저 카테고리를 정하고, 개인화는 "같은 카테고리 안에서 어떤 드릴을, 약신호 구간에서 어떤 방향을" 고를 때만 부드럽게 작용. (시연에서 "강한 감정엔 여전히 진정 먼저"를 보여주면 좋음)
- **콜드 스타트 안전.** 노출 0회면 가산점 0 → 신규 사용자에겐 개인화가 작동하지 않고 기본 추천. 데이터가 쌓이며 점진 적응.
- **인과 단정 없음.** 경향 narrative는 전부 "~한 날에 ~가 더 보였어요" 관찰 톤. 진단어(`scripts/lint_copy.py`)·인과 단정 회피.
- **개인정보.** 개인화 DB도 user_id를 SHA-256+salt 해시로만 저장(`preferences.db`). 평문 0%.
- **이론 근거.** UCB1 = Auer(1985) regret bound. "왜 학습 데이터 없이 개인화?" → 운영하며 학습하는 bandit 구조라 사전 데이터 불필요(§11 그대로 구현).

---

## 6. 신규 엔드포인트 계약 (요약)

```
GET  /personalization/profile?user_id=U
 → { user_id, total_offers, is_learning_active,
     categories:[{category,label_ko,n_offered,n_completed,n_helpful,n_rejected,reward_estimate,ucb_bonus}, ...6] }

POST /personalization/event   { user_id, category, event:"offer"|"complete"|"helpful"|"reject" }
 → { accepted:true, ... }     // BE가 별도 경로로 학습을 푸시하고 싶을 때(보통은 불필요)

GET  /personalization/next_focus?user_id=U&state_key=fatigue
 → { category, label_ko, reason, source }   // entries 없이 빠르게 다음 초점만

GET/POST /weekly  (기존)  →  응답에 weekly_coaching 블록 추가(§2-3 구조)
```

자세한 필드는 Swagger(`/docs`)에서 확인 가능합니다.
