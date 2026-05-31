# Step Back — ML Service

> **Step Back**은 사용자가 매일 짧은 글과 상태를 기록하면, 그 글을 분석해 **지금 마음에 맞는 작은 실천(드릴)을 추천**하고, 일주일이 쌓이면 **개인 맞춤 주간 리포트**를 만들어 주는 CBT/ACT 기반 자기발견 도구입니다. 이 저장소는 그중 **ML 서비스**(추천 엔진)입니다.
>
> 이 문서 하나로 **처음 보는 사람도** 전체 구조·기능·실행법을 이해할 수 있게 작성했습니다.

---

## 0. 한눈에 보기 (30초 요약)

```
[사용자] 오늘 글 + 상태(수면/컨디션/사교/운동) 입력
   │
   ▼
[BE]  ── HTTP ──▶ [이 ML 서비스]
                      │ 1) 글을 13개 차원으로 분석 (Gemini 또는 Mock)
                      │ 2) 분석 + 상태로 가장 맞는 드릴 1개 추천
                      │ 3) "왜 이 드릴인지" 설명 생성
                      ▼
                  추천 결과(JSON) 반환
   ◀──────────────────┘
[BE] 결과를 DB 저장 + FE로 전달 → [사용자] 드릴 카드 화면

(일주일 후) BE가 7일치를 모아 ML에 요청 → ML이 주간 코칭 리포트 생성
```

- **언어/프레임워크**: Python 3.11 + FastAPI
- **AI**: Google Gemini (API 키 없으면 자동으로 규칙 기반 Mock으로 동작 → 키 없이도 전 기능 시연 가능)
- **저장소**: ML 자체 학습 데이터는 SQLite (사용자 원본 데이터는 BE의 PostgreSQL이 담당)
- **드릴 카탈로그**: 100개 (CBT/ACT 근거 기반), `w1/drills_seed_v6_4.json`

---

## 1. 이게 뭘 푸는 문제인가

기존의 "AI 상담 챗봇"은 매번 답이 다르고(비결정적), 왜 그렇게 답했는지 설명이 약하고, 사용자를 기억하지 못합니다. Step Back ML은 그 반대를 지향합니다:

| 목표 | 어떻게 |
|---|---|
| **설명 가능** | "왜 이 드릴인지"를 사용자 원문 인용 + 근거와 함께 제시 |
| **일관성** | LLM은 점수만 매기고, 추천 결정은 규칙 기반 함수 → 같은 입력 = 같은 결과 |
| **개인화** | 완료·도움·거부를 학습해 그 사람에게 맞는 추천으로 수렴 |
| **안전** | 위기 신호는 LLM 호출 전에 차단하고 상담 연락처 안내 |
| **근거 기반** | 100개 드릴 모두 학술 논문(Beck, Ellis, Neff 등) 출처 명시 |

---

## 2. 핵심 개념 3가지

### (1) 13개 차원 (13 dimensions)
사용자 글을 아래 13개 점수(0~1)로 분석합니다.
- **인지 패턴 6개**: 미래예측, 독심술, 자기비난, 이분법, 당위진술, 과잉일반화 (Beck의 인지왜곡)
- **행동 신호 2개**: 회피미루기, 동기저하
- **감정 5개**: 불안, 우울, 분노, 죄책, 중립

### (2) 드릴 (drill)
드릴 = 1~5분짜리 작은 심리 실천. 100개가 6개 카테고리로 분류됩니다.
- `cognitive_restructuring`(생각 다시 보기), `behavioral_activation`(작은 행동), `habit_design`(습관), `grounding`(지금·진정), `self_compassion`(자기 자비), `sleep_circadian`(수면)

### (3) evidence_span (근거 인용)
분석 결과 중 "사용자가 실제로 쓴 어느 문구가 근거였는지"를 뽑아 보여줍니다. 예: *"'망할 것 같아'가 보여서 골랐어요"*. 이게 "내 말을 읽었구나" 하는 신뢰감의 핵심입니다.

---

## 3. 폴더 구조 — 각 파일이 무엇인가

```
stepback/
├── ml_service/              ← ML 서비스 본체 (이 저장소의 핵심)
│   ├── app/
│   │   ├── main.py          ← FastAPI 진입점. 모든 라우터를 모아 앱을 만든다. (= 서버의 main)
│   │   ├── config.py        ← 설정. 환경변수(Gemini 키, Mock 여부, 서버 주소 등) 읽기
│   │   │
│   │   ├── api/             ← HTTP 엔드포인트 (BE가 호출하는 입구)
│   │   │   ├── entries.py        · POST /entries  : 오늘 기록 → 라벨링+추천 (가장 많이 쓰임)
│   │   │   ├── recommend.py      · POST /recommend: 추천만 따로
│   │   │   ├── weekly.py         · GET/POST /weekly : 주간 리포트(개인 맞춤 코칭)
│   │   │   ├── monthly.py        · GET /monthly   : 월간 리포트
│   │   │   ├── feedback.py       · POST /feedback : 드릴 도움됨/완료 (개인화 학습)
│   │   │   ├── personalization.py· GET /personalization/* : 학습된 취향 조회
│   │   │   ├── drills.py         · GET /drills, /categories : 드릴 목록
│   │   │   ├── insights.py       · 인사이트 + DELETE /users/{id}/data (탈퇴 시 ML데이터 삭제)
│   │   │   ├── health.py         · GET /healthz : 살아있는지 확인
│   │   │   └── admin.py          · GET /healthz/detail : 상세 상태(관리자 토큰 필요)
│   │   │
│   │   ├── core/            ← 비즈니스 로직 (실제 "머리")
│   │   │   ├── recommender.py    · 추천의 심장. 라우팅 규칙 + 점수 계산 + "왜 이 드릴" 생성
│   │   │   ├── personalization.py· 개인화 학습(할인 UCB). SQLite에 카테고리별 보상 누적
│   │   │   ├── weekly_coaching.py· 주간 코칭: 상태 추론 + 다변량 경향 분석 + 다음 초점
│   │   │   ├── weekly_report.py / monthly_report.py · 리포트 조립
│   │   │   ├── drill_catalog.py  · 100개 드릴 JSON 로더 (v6_4 우선, 없으면 v6_3)
│   │   │   ├── labels.py         · 임상용어 ↔ 일상어 라벨 매핑 (예: 미래예측→미리 결론 내리기)
│   │   │   ├── auto_discovery.py · 사용자 표현/패턴 자동 발견
│   │   │   └── baselines.py      · 30일 평균 대비 이번 주 비교
│   │   │
│   │   ├── infra/           ← 외부 연동 + 안전장치
│   │   │   ├── llm_client.py     · Gemini 호출 / Mock 폴백 / 위기 사전 차단 / 점수 계산
│   │   │   ├── pii_masker.py     · 개인정보(전화·이메일 등) 마스킹
│   │   │   └── audit_log.py      · user_id를 SHA-256 해시로 (평문 저장 안 함)
│   │   │
│   │   └── schemas/         ← 요청/응답 데이터 형식 정의 (Pydantic)
│   │       ├── recommend.py      · 추천 응답 형식 (drill, why, factors ...)
│   │       └── label.py, weekly.py, monthly.py, feedback.py ...
│   │
│   ├── tests/               ← 자동 테스트 258개 (pytest)
│   ├── requirements.txt     ← 파이썬 의존성 목록
│   ├── Dockerfile           ← 컨테이너 빌드 정의 (서버/클라우드 배포용)
│   └── deploy_gcp.sh        ← GCP Cloud Run 배포 스크립트
│
├── w1/                      ← 드릴 카탈로그 + 분류 체계 (데이터)
│   ├── drills_seed_v6_4.json    · 100개 드릴 정본 (ML이 실제 로드)
│   ├── drills_seed_v6_3.json    · 기존 77개 (병합 소스)
│   ├── drills_new_v6_4.json     · 신규 23개 (병합 소스)
│   ├── taxonomy_v7.json         · 13차원 정의 + 단서(cue) + 사용자 친화 라벨
│   ├── labeling_prompt_v3.md    · Gemini에게 주는 라벨링 프롬프트
│   └── validate_and_merge_drills.py · 드릴 3회 검증 + 병합 스크립트
│
├── handoff/                 ← 팀 인계 문서 (FE/BE/UX 메시지, 가이드)
│   ├── ML_FINAL_HANDOFF.md       · 전체 인계 요약
│   ├── MESSAGE_to_FE/BE/UX.md    · 각 파트 담당에게 보내는 메시지
│   ├── SERVER_DEPLOY_GUIDE.md    · BE 서버에 ML 띄우기
│   ├── GCP_GEMINI_GUIDE.md       · Gemini 키 발급 + GCP 배포
│   ├── RUN_AND_VERIFY_GUIDE.md   · 로컬 실행/확인
│   ├── weekly_erd_check.md       · 주간 맞춤형에 필요한 DB 컬럼
│   └── drill_color_spec.md + drill_color_table.json · 드릴 색상표
│
├── START_HERE.bat / start_here.sh · 원클릭 실행 런처
└── README.md                · (이 문서)
```

---

## 4. 동작 워크플로우 (자세히)

### 워크플로우 A — 매일 기록 → 추천
1. 사용자가 글 + 상태를 입력 → BE가 `POST /entries` 호출.
2. **`llm_client.py`**: 글을 13차원으로 분석.
   - 먼저 **위기 신호 검사** (죽고 싶다 등) → 있으면 즉시 위기 카드 반환, **Gemini로 전송 안 함**.
   - 위기 아니면 → Gemini가 점수+evidence_span 반환 (키 없으면 단서 기반 Mock).
3. **`recommender.py`**: 점수 + 상태(맥락)로 추천 결정.
   - 규칙 라우팅(위기→인지→행동→감정→약신호) + 개인화 가산점.
   - 드릴 1개 선택 후 **"왜 이 드릴인지"**(왜+효용+근거+원문인용) 생성.
4. 응답(JSON) 반환 → BE 저장 → FE가 드릴 카드 표시.

### 워크플로우 B — 개인화 학습
- 사용자가 드릴을 완료/도움됨/거부 → BE가 `POST /feedback` 또는 `/reject`.
- **`personalization.py`**가 카테고리별 보상을 SQLite에 누적(할인 UCB: 최근 선택에 가중).
- 다음 추천부터 그 사람에게 맞는 카테고리에 가산점 → 점점 맞춰짐.

### 워크플로우 C — 주간 리포트 (개인 맞춤)
- BE가 그 주 7일치 기록을 모아 `POST /weekly`.
- **`weekly_coaching.py`**가 분석:
  - 상태(컨디션 흐름), 다변량 경향(수면↔패턴, 사교↔컨디션 등), 다음 주 초점.
- 모두 **사용자가 입력한 데이터에서만** 도출 (지어내지 않음).

---

## 5. 기술 선택 이유 (왜 이렇게 만들었나)

- **FastAPI**: 비동기 + 자동 문서(`/docs`) + Pydantic 검증. 빠른 API 개발에 적합.
- **Gemini + Mock 폴백 구조**: 운영은 Gemini, 개발/CI는 키 없이 Mock. "키 없으면 멈춤"이 아니라 "키 없으면 규칙 기반으로라도 동작" → 데모·테스트가 쉬움.
- **LLM은 점수만, 결정은 규칙**: LLM 단독은 비결정적·설명 약함. 점수 산출만 LLM에 맡기고 추천 결정은 코드로 → 일관성·설명가능성·안전성 확보 (차별점).
- **SQLite (개인화/피드백)**: 사용자 원본은 BE의 PostgreSQL이 담당. ML은 가벼운 학습 통계만 자체 SQLite로 → BE와 결합도를 낮춤. user_id는 해시로만 저장.
- **드릴을 코드가 아닌 JSON으로**: 비개발자(기획)도 드릴을 추가·수정 가능. 검증 스크립트로 품질 보장.

---

## 6. 실행 방법

### 가장 빠른 길 (로컬, 키 없이 Mock)
```bash
# stepback/ 폴더(= ml_service, w1 이 보이는 곳)에서
pip install -r ml_service/requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
# 브라우저로 http://127.0.0.1:8001/docs
```
- Windows는 `START_HERE.bat` 더블클릭, mac/Linux는 `bash start_here.sh` 로도 됩니다.

### 실제 Gemini로
```bash
export GEMINI_API_KEY="AIza...키"   # 이 환경변수만 있으면 자동으로 Gemini 사용
export AUDIT_SALT="32자 이상 랜덤문자열"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
```
- 확인: `curl http://127.0.0.1:8001/healthz` → `{"status":"ok","drills_loaded":100}`
- Gemini로 떴는지: `/healthz/detail` (관리자 토큰 헤더) → `"is_mock": false`

### 테스트
```bash
cd ml_service
ADMIN_TOKEN=dev_token_local python -m pytest -q   # 258 passed 가 정상
```

### 배포
- 서버: `handoff/SERVER_DEPLOY_GUIDE.md`
- GCP: `handoff/GCP_GEMINI_GUIDE.md` + `ml_service/deploy_gcp.sh`

---

## 7. 주요 API 한눈에

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/entries` | 오늘 기록 → 라벨링 + 추천 (메인) |
| POST | `/recommend` | 추천만 |
| POST | `/feedback` | 드릴 평가(도움됨/완료) → 개인화 학습 |
| POST | `/reject` | 드릴 거부 → 개인화 학습 |
| GET | `/weekly` · `/monthly` | 리포트 (개인 맞춤 코칭 포함) |
| GET | `/personalization/profile` | 학습된 취향 조회 |
| GET | `/drills` · `/categories` | 드릴 목록 |
| DELETE | `/users/{user_id}/data` | 회원 탈퇴 시 ML 데이터 삭제 |
| GET | `/healthz` · `/healthz/detail` | 상태 확인 |

> 전체 요청/응답 형식은 서버 실행 후 **`/docs`** (Swagger UI)에서 바로 확인할 수 있습니다.

---

## 8. 안전 · 개인정보

- **위기 차단**: 자해/자살 신호는 LLM 호출 **전에** 차단하고 상담 연락처(1393/1388/1577-0199) 안내. 위기 텍스트는 외부로 전송되지 않음.
- **PII 마스킹**: 전화·이메일 등은 처리 전 마스킹.
- **해시 저장**: user_id는 SHA-256 + salt로만 저장 (평문 0%).
- **의료 행위 아님**: 진단/치료가 아닌 자기발견 보조 도구.

---

## 9. 품질

- 자동 테스트 **258개** 통과 (3회 반복 동일).
- 드릴 카탈로그 100개 **3회 검증** 통과 (스키마·라우팅·근거 일관성).
- 새 환경에서 압축 해제 후 바로 테스트 통과 (자체 완결).

---

## 10. 더 읽을 문서
- 전체 인계: `handoff/ML_FINAL_HANDOFF.md`
- 실행/확인 상세: `handoff/RUN_AND_VERIFY_GUIDE.md`
- 팀별 연동: `handoff/MESSAGE_to_FE.md` · `MESSAGE_to_BE.md` · `MESSAGE_to_UX.md`
- 자체 점검(효율성·타당성·신뢰성·차별성·재미): `handoff/v96_self_review.md`
