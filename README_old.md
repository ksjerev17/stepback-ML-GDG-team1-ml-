# Step Back ML — 학부 1팀 (v9.5)

> 한 줄 텍스트 → LLM 라벨링(인지 6 + 행동 2 + 감정 5) → 학술 드릴 추천.
> 7주 졸업 프로젝트 ML 파트. P1 담당.

## 산출물 한눈에

```
stepback/
├── INSTALL.md                 ← 설치 가이드
├── RUN.md                     ← 실행 + curl 예시
├── TEST.md                    ← 테스트 가이드
├── HANDOFF_TO_BE.md           ← P2(BE)에게 줄 인계 문서
├── NOTES.md                   ← P1 미해결·결정 필요 사항
├── ml_service/                ← FastAPI 서비스 (전체 코드)
│   ├── app/
│   │   ├── api/               ← entries(v9.5)/label/recommend/recommend/after_ask/feedback/weekly/
│   │   │                       monthly(v9.5)/insights/reports/drills/calendar/admin/health
│   │   ├── core/              ← labeler / recommender / monthly_report / weekly_report /
│   │   │                       auto_discovery / insights_store / baselines / feedback_store / cards
│   │   ├── infra/             ← pii_masker / quota_manager / llm_client / audit_log /
│   │   │                       request_context / error_handler / metrics
│   │   ├── schemas/           ← Pydantic v2 (8 파일 — monthly v9.5 추가)
│   │   └── main.py
│   ├── tests/                 ← 207 PASS (3회 안정)
│   │   ├── unit/              ← pii / quota / audit_log / postprocess
│   │   ├── integration/       ← routing / weak_signal / crisis / endpoints / feedback / weekly /
│   │   │                       monthly(v9.5) / insights / auto_discovery / baseline / calendar_drills /
│   │   │                       recommender_v2 / admin_ops / pentagon_diurnal / v95_changes / v95_design /
│   │   │                       security
│   │   └── smoke/             ← 30 시나리오
│   ├── scripts/               ← 8 운영 스크립트
│   │                            (analyze_labeling / lint_copy / simulate_recommend / pre_demo_check /
│   │                             purge_old_data / seed_demo_data / load_test /
│   │                             test_gemini_e2e / check_gemini_key)
│   ├── postman_collection.json
│   ├── docker-compose.local.yml
│   ├── Dockerfile
│   └── README.md
├── w1/                        ← 라벨링 데이터·후처리·정밀화 (읽기 전용)
├── handoff/                   ← 8 마크다운 — P2~P5 계약 정본
│   ├── api_contract.md
│   ├── error_codes.md
│   ├── crisis_response_protocol.md
│   ├── be_integration_guide.md
│   ├── fe_integration_guide.md
│   ├── calendar_color_spec.md
│   ├── content_guide.md
│   └── changelog.md
└── docs/                      ← w2~w7 완료 + final_report + demo_script + presentation
```

## 빠른 시작

```powershell
cd ml_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 테스트 (207 PASS 기대)
$env:ADMIN_TOKEN="dev_token_local"; $env:FORCE_MOCK="true"
python -X utf8 -m pytest tests/ -q

# 서버
uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
# → http://127.0.0.1:8001/docs (Swagger)
```

자세히: `INSTALL.md` → `RUN.md` → `TEST.md`.

## v9.5 핵심 정책

- **하루 1회 입력** — 1 LLM + 1 드릴 추천 (이전 3회 폐기)
- **drill_id INT** — `1, 2, ..., 77` (ERD BIGINT 호환). 옛 "D01" string도 `legacy_id` 매칭으로 호환.
- **`POST /entries` 통합** — BE 한 번 호출로 label + recommend
- **ask-first 정책** — 약신호 + 컨디션 나쁨 → "받으실래요?" 먼저 묻고 → `POST /recommend/after_ask`
- **월간 리포트** — `POST /monthly` (약 30일 entries 기반 6 블록)
- **나의 발견** — `POST /insights/user_discovery`. 사용자가 적은 발견에서 키워드 추출 → 다음 추천 affinity 가산
- **욕설 감지** — intensity +0.3, confidence +0.1 (Mock·실 LLM 양쪽)
- **주간 회복 패턴** — 아침/저녁 비교(v9.4.x) → 주 전반(월~수)/후반(목~일) 비교 (일 1회 정책 정합)

## 명세서 v9.5 — 구현 매핑

| 명세서 § | 기능 | 구현 위치 |
|---|---|---|
| §3 | Google OAuth 인증 | (P2 영역) |
| §4 | 매일 1회 입력 — 4 맥락 변수 | `app/api/entries.py` (통합) + `app/api/label.py` |
| §5 | LLM 라벨링 (인지 6 + 행동 2 + 감정 5) | `app/core/labeler.py` + `app/infra/llm_client.py` |
| §5.2 | PII 마스킹 7종 | `app/infra/pii_masker.py` |
| §5.3 | Quota (분 1 / 시 3 / 일 3) | `app/infra/quota_manager.py` |
| §5.4 | Gemini Primary/Light + Mock 폴백 | `app/infra/llm_client.py` (신 SDK `google-genai` 우선, 구 SDK 폴백) |
| §5.5 | 위기 신호 (한·영·띄어쓰기 우회 + 욕설 감지) | `app/core/crisis_card.py` + `app/infra/llm_client.py` |
| §5.6 | 후처리·정밀화 | W1 `label_postprocess` / `clarification_loop` import |
| §6.1 | 점수 공식 0.35×인지 + 0.40×행동 + 0.25×맥락 + bonus + user_discovery affinity | `app/core/recommender.py` `_score_drill` |
| §6.2 | 라우팅 5단계 + ask-first | `app/core/recommender.py` `recommend()` + `recommend_after_ask_user()` |
| §6.3 | 카탈로그 v6.3 (77개) — drill_id INT | `w1/drills_seed_v6_3.json` |
| §6.4 | 자기 발견 카피 3줄 + confidence 톤 조정 | `_build_copy()` |
| §6.5 | 3 버튼 (시작/거부/지금괜찮) | `/recommend` 응답 + `POST /reject` |
| §7.1 | 드릴 instruction (INT id) | `GET /drills/{id}` |
| §7.2 | 드릴 평가 (helpful/meh/unhelpful, KST 23:59) | `app/core/feedback_store.py` + `/feedback` |
| §7.3 | 캘린더 dominant 9색 | `_calendar_dominant()` + `handoff/calendar_color_spec.md` |
| §8.1 | 주간 리포트 cron + 인앱 팝업 | `/reports/pending`, `/reports/{id}/read` |
| §8.2 | 자가진단 퀴즈 4지선다 + "모르겠다" (정답 비공개) | `app/core/self_check_quiz.py` |
| §8.3 | 데이터 공개 + match 판정 | `PATCH /weekly/quiz` |
| §8.4 | 발견 4 알고리즘 (top_evidence / 맥락 상관 / 효과 드릴 / weekly_recovery) | `app/core/auto_discovery.py` |
| §8.5 | user_insights 저장 (시스템·사용자) | `POST /insights` + `app/core/insights_store.py` |
| §8.6 | 표현 원칙 (자기 발견 톤) | `scripts/lint_copy.py` |
| §9.1 | 월간 캘린더 + 일별 모달 | `POST /calendar`, `POST /daily` |
| §9.2 | 컨디션 흐름 7일 | `POST /weekly/condition_flow` |
| §9.3 | 패턴 변화 막대 | `POST /weekly/pattern_diff` |
| §9.4 | 발견 사전 토글 UI | `GET /insights?category=&source=` |
| §10.1 | v0 콘텐츠 기반 | 구현 완료 |
| §10.2 | v1 사용자 baseline 30일 | `app/core/baselines.py` + `/baseline/recompute` |
| §10.3 | v2 Logistic Regression | NOTES.md §D5 (베타 200 샘플 후) |
| §11.1 | ERD 5 테이블 | ML 측 SQLite 3개 + BE 측 PostgreSQL 5개 |
| §11.2 | 위기 처리 흐름 | `handoff/crisis_response_protocol.md` |
| §11.3 | 윤리·법 (90일 / export / 회원 탈퇴) | `/export`, `DELETE /users/{id}/data`, `scripts/purge_old_data.py` |
| §11.4 | 자기 발견 톤 | `scripts/lint_copy.py` |
| **v9.5 추가** | **POST /entries 통합 (옵션 C)** | `app/api/entries.py` (신규) |
| **v9.5 추가** | **나의 발견** | `app/core/insights_store.py` + `/insights/user_discovery` |
| **v9.5 추가** | **월간 리포트** | `app/core/monthly_report.py` + `/monthly` |
| **v9.5 추가** | **drill_id INT 마이그레이션** | `drill_catalog.get_drill()` + `insights_store.rejected_drills` |
| **v9.5 추가** | **욕설 감지 intensity 가산** | `app/infra/llm_client.py` (Mock + 실 LLM 양쪽) |

## 검증 상태

- **테스트**: **207/207 PASS** — 3회 연속 검증 (운영 안정)
- **카피 검증**: lint_copy app/ PASS
- **시연 자가 점검**: pre_demo_check 5/5 PASS

## 안전

- 127.0.0.1만 listen (외부 노출 X)
- 외부 통신 0 — Gemini API 1곳만
- PII 마스킹 7종 자동
- 위기 신호 시 일반 드릴 차단
- audit log 평문 거부 + JSONL hash 로깅
- 90일 자동 삭제
- ADMIN_TOKEN 강제 (admin 엔드포인트)

## 다음 단계

1. **API 키 발급 → 실 LLM 전환** (NOTES.md §D1)
2. **BE 통합** — `POST /entries` 통합 호출 사용 권장 (옵션 C)
3. **FE — v9.4.4 ask-first 카드 UI** (FE_GUIDE §2.2)
4. **P5 — 카탈로그 INT 마이그레이션 검수** + 베타 동의서
5. **베타 8~12명 2주 운영 → logistic regression 학습** (§10.3)

---

**v9.5 — 일 1회 정책 + BE 통합 + 월간 리포트 + 나의 발견 + ask-first.**
