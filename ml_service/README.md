# Step Back ML Service — v9.5

> CLAUDE.md §7. P1 영역. 로컬 전용.

## 빠른 시작

```powershell
# Windows
cd ml_service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# 환경 변수
copy ..\.env.example ..\.env
# .env에 FORCE_MOCK=true / ADMIN_TOKEN=<강한 토큰> 확인

# 서버 (127.0.0.1만 listen)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir . --reload
```

```bash
# Mac/Linux
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example ../.env
export ADMIN_TOKEN=dev_token_local FORCE_MOCK=true PYTHONIOENCODING=utf-8
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir .
```

## 엔드포인트 (v9.5 — 30개)

### BE 통합 권장
| Method | Path | 용도 |
|---|---|---|
| **POST** | **`/entries`** | **v9.5 통합 — label + recommend 한 번** |
| POST | `/recommend/after_ask` | ask-first 후속 |

### 옛 호환
| Method | Path | 용도 |
|---|---|---|
| POST | `/label` | 텍스트 라벨링 (단독) |
| POST | `/recommend` | 드릴 추천 (단독) |

### 주간·월간
| Method | Path | 용도 |
|---|---|---|
| GET / POST | `/weekly` | 주간 리포트 5블록 + 시각화 + 발견 |
| PATCH | `/weekly/quiz` | 자가진단 답 |
| POST | `/weekly/condition_flow` | 7일 라인 |
| POST | `/weekly/pattern_diff` | 이번주 vs 지난주 |
| GET / POST | `/monthly` ⭐ | **v9.5 월간 리포트 6블록** |

### 발견
| Method | Path | 용도 |
|---|---|---|
| POST / GET | `/insights` | 시스템·사용자 발견 (주간) |
| POST / GET | `/insights/user_discovery` ⭐ | **v9.5 나의 발견 — 추천 affinity** |

### 평가·드릴
| Method | Path | 용도 |
|---|---|---|
| POST / GET | `/feedback` | 평가 (GET 응답 점수 비공개) |
| POST | `/reject` | "아닌 것 같아요" |
| GET | `/drills/{id}` | 드릴 상세 (INT 또는 D01) |
| GET | `/drills` | 카탈로그 |

### Baseline·캘린더
| Method | Path | 용도 |
|---|---|---|
| POST | `/baseline/recompute` | 30일 누적 |
| GET | `/baseline` | 학습 전용 |
| GET / POST | `/calendar` | 월간 dominant |
| POST | `/daily` | 일별 상세 (helpful 비공개) |

### 헬스·운영 (ADMIN_TOKEN)
| Method | Path | 용도 |
|---|---|---|
| GET | `/healthz` | 공개 |
| GET | `/healthz/detail` | ADMIN |
| GET | `/metrics` / `/metrics/json` | ADMIN |
| POST | `/admin/quota/reset` | ADMIN |

Swagger UI: http://127.0.0.1:8001/docs

## 테스트

```powershell
$env:ADMIN_TOKEN="dev_token_local"; $env:FORCE_MOCK="true"
pytest tests/                     # 207 PASS (v9.5)
pytest tests/unit -q              # 단위
pytest tests/integration -q       # 통합 (monthly·v95 포함)
pytest tests/smoke -q             # 30 시나리오
```

## 스크립트

```powershell
python -X utf8 scripts/analyze_labeling.py     # W1 라벨링 합치율 분석
python -X utf8 scripts/lint_copy.py app/       # 금지 표현 검출
python -X utf8 scripts/simulate_recommend.py   # 7일 가상 시뮬레이션
python -X utf8 scripts/pre_demo_check.py       # 시연 전 5항목 점검
python -X utf8 scripts/purge_old_data.py       # 90일 지난 데이터 삭제
python -X utf8 scripts/seed_demo_data.py       # 데모 데이터 시드
python -X utf8 scripts/load_test.py            # 12명 동시 부하 (서버 실행 중일 때)
python -X utf8 scripts/check_gemini_key.py     # Gemini API 키 즉시 검증
python -X utf8 scripts/test_gemini_e2e.py      # 실 Gemini E2E 검증
```

## API 키 발급 후 — 실 Gemini 활성화

```powershell
# .env 편집
$env:GEMINI_API_KEY="AIzaSy..."
$env:FORCE_MOCK="false"

pip install google-genai     # 신 SDK 권장 (v9.5)

# 검증
python -X utf8 scripts/check_gemini_key.py
# → "[OK] google-genai (신 SDK)" + 사용 가능 모델 목록

# 서버 재시작 → /healthz의 primary_model이 gemini-2.0-flash-lite 등으로 표시
```

`app/infra/llm_client.py`가 자동 감지 (신 SDK 우선 → 구 SDK 폴백 → Mock). 코드 수정 불필요.

## 폴더 구조 (v9.5)

```
ml_service/
├── app/
│   ├── main.py                    # FastAPI 부트 + CORS + 미들웨어
│   ├── config.py                  # 환경 변수
│   ├── api/                       # health / label / entries(v9.5) / recommend /
│   │                                feedback / weekly / monthly(v9.5) / insights /
│   │                                reports / drills / calendar / admin
│   ├── core/                      # labeler / recommender / monthly_report(v9.5) /
│   │                                weekly_report / auto_discovery /
│   │                                insights_store / baselines / feedback_store /
│   │                                cards / self_check_quiz
│   ├── infra/                     # pii_masker / quota_manager / llm_client /
│   │                                audit_log / request_context / error_handler / metrics
│   ├── schemas/                   # common / label / recommend / feedback /
│   │                                weekly / monthly(v9.5) / insight / baseline
│   └── data/
├── tests/
│   ├── unit/                      # 26 PASS
│   ├── integration/               # ~150 PASS (monthly·v95·security 추가)
│   └── smoke/                     # 31 PASS
├── scripts/                       # 8 운영 스크립트
└── data/                          # feedback.db / insights.db / baselines.db (자동 생성)
```

## 안전

- 127.0.0.1만 listen (§13.3)
- 외부 통신 0 — Gemini 한 곳만
- PII 마스킹 7종 자동 (§11.1)
- 위기 신호 시 일반 드릴 차단 (§16.2)
- 욕설 감지 → intensity/confidence 가산 (Mock + 실 LLM 양쪽 — v9.5)
- audit log 평문 거부 (§11.5)
- ADMIN_TOKEN 강제 (admin 엔드포인트)
- CORS localhost만
