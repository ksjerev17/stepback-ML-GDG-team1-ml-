# 테스트 가이드

## 가장 빠른 — 더블 클릭

탐색기에서 `run_test.bat` 더블 클릭 → UTF-8·ADMIN_TOKEN·venv 자동 + pytest 실행.

## 전체 테스트 — PowerShell 1줄

```powershell
.\run_test.bat
```

또는 수동:

```powershell
cd "C:\cogdrill 팀1 ML\stepback"
. .\scripts\Setup-Env.ps1
python -X utf8 -m pytest tests/ -v
```

기대: **207 passed** (v9.5, ADMIN_TOKEN 설정 시). 미설정 시 202 passed + 4 skipped + 1 failed (admin 관련만).

## 카테고리별

```powershell
python -X utf8 -m pytest tests/unit -q          # 26 (외부 의존 X)
python -X utf8 -m pytest tests/integration -q   # ~106 (FastAPI TestClient + SQLite tmp DB)
python -X utf8 -m pytest tests/smoke -q         # 31 (30 시나리오 + count)
```

## ADMIN_TOKEN 설정 (admin 테스트 통과)

```powershell
# 일회성
$env:ADMIN_TOKEN = "dev_token_local"
python -X utf8 -m pytest tests/ -q

# 영구 (이 셸 세션)
. .\scripts\Setup-Env.ps1   # 자동 설정됨

# 시스템 영구 (선택)
[System.Environment]::SetEnvironmentVariable("ADMIN_TOKEN", "dev_token_local", "User")
# PowerShell 재시작 후 적용
```

## 핵심 회귀 — 통과 필수

| 시험 파일 | 검증 항목 | 케이스 수 |
|---|---|---|
| `test_routing_5_steps.py` | 7 시나리오 (S001/S036/S040/S016/S005/S007 + step6) | 7 |
| `test_weak_signal_branches.py` | 약신호 5a/5b/5c/5d | 4 |
| `test_crisis.py` | 위기 표현 5종 + crisis_card 차단 | 6 |
| `test_pii.py` | PII 마스킹 7종 | 12 |
| `test_quota.py` | user 격리 + 한도 | 7 |
| `test_audit_log.py` | 평문 거부 + JSONL hash | 6 |
| `test_endpoints.py` | /healthz, /label, /recommend | 6 |
| `test_feedback_endpoint.py` | 평가 비공개 + KST 23:59 | 4 |
| `test_weekly_report.py` | 5블록 + 퀴즈 (정답 server-only) | 4 |
| `test_insights.py` | insights/reports/quiz/reject/export/delete | 9 |
| `test_auto_discovery.py` | 3 알고리즘 (evidence/상관/효과) | 5 |
| `test_baseline.py` | recompute / compare | 4 |
| `test_calendar_drills.py` | calendar/daily/drills | 5 |
| `test_recommender_v2.py` | bonus / step4 boundary / rejected | 5 |
| `test_admin_ops.py` | request_id / healthz/detail / metrics / clarify | 10 |
| smoke | 30 시나리오 (인지/행동/위기/약신호/PII/URL) | 31 |

## 운영 스크립트 검증

```powershell
# 시연 직전 5 항목
python -X utf8 scripts/pre_demo_check.py
# 1. FORCE_MOCK 상태
# 2. 드릴 카탈로그 77개
# 3. Quota 여유
# 4. logs/ 쓰기 권한
# 5. .env 누출 여부

# 카피 검증
python -X utf8 scripts/lint_copy.py app/

# 7일 가상 시뮬레이션
python -X utf8 scripts/simulate_recommend.py

# 12명 동시 부하 (서버 별도 실행 필요)
python -X utf8 scripts/load_test.py --users 12 --rounds 1

# W1 라벨링 분석 (결과 파일 있을 시)
python -X utf8 scripts/analyze_labeling.py

# 90일 지난 데이터 일괄 삭제
python -X utf8 scripts/purge_old_data.py
```

## 수동 검증 (Swagger UI)

http://127.0.0.1:8001/docs

다음 5건 직접 호출:
1. `POST /label` body: `{"text":"내일 발표 망할 것 같아","user_id":"u_test"}` → patterns.미래예측 > 0
2. `POST /recommend` (위 응답 + context) → type:"drill", drill.category:"cognitive_restructuring"
3. `POST /label` body: `{"text":"사라지고 싶다",...}` → crisis_detected:true
4. `POST /recommend` (위 응답) → type:"crisis_card", crisis_resources.자살예방상담:"1393"
5. `GET /weekly?user_id=u_test&week=2026-W21` → 5블록 응답 (정답값 미노출)

## PowerShell 헬퍼로 한 줄 시연

```powershell
. .\scripts\Setup-Env.ps1
. .\scripts\Call-Api.ps1
Run-Demo
```

5 시나리오를 순서대로 호출 + 응답 출력.

## 3회 반복 검증 권장 시점

- W2 종료
- W6 시연 1주 전
- W7 발표 전날

세 번 모두 통과 → 신뢰 가능.

## CI/CD

`.github/workflows/ml-tests.yml` 이미 작성됨. git init + push 시 자동 실행:
- pytest 207 PASS (v9.5)
- ruff check
- mypy (continue-on-error 점진 도입)
- lint_copy
- gitleaks secret scan
- pip-audit 의존성 취약점

## 자주 발생하는 테스트 문제 + 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| admin 테스트 4건 skip + 1건 fail | ADMIN_TOKEN 미설정 | `$env:ADMIN_TOKEN="dev_token_local"` |
| 한국어 응답 깨짐 (pytest) | cp949 | 모든 pytest 명령에 `-X utf8` 또는 `Setup-Env.ps1` |
| `ModuleNotFoundError: pydantic_settings` | venv 미활성 | `Setup-Env.ps1` 실행 |
| 느린 테스트 (>10s) | smoke 31 케이스 일괄 | 일반: `-q`, 단위만: `pytest tests/unit -q` |
| `port 8001 already in use` | uvicorn 미종료 | `Get-Process python \| Stop-Process` |
