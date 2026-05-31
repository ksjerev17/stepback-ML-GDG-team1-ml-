# 실행 가이드 (Windows PowerShell + Swagger 권장)

> Windows PowerShell의 한국어 인코딩(cp949)·curl 별칭 문제를 모두 회피하는 방식.

## 가장 빠른 시작 — 더블 클릭 1번

탐색기에서 `run_serve.bat` 더블 클릭 → 서버 자동 시작.
- UTF-8 코드페이지 자동 설정
- ADMIN_TOKEN 자동 (`dev_token_local`)
- FORCE_MOCK=true 자동
- `.venv` 있으면 자동 활성화
- http://127.0.0.1:8001/docs 접속

종료: 콘솔창에서 Ctrl+C.

## PowerShell 한 줄로 시작

```powershell
.\run_serve.bat
```

## 수동 시작 (셸 안에서)

```powershell
cd "C:\cogdrill 팀1 ML\stepback"
. .\scripts\Setup-Env.ps1     # UTF-8 + ADMIN_TOKEN + venv 자동
# 현재 디렉토리: stepback (자동 cd 안 함 — 경로 중복 방지)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload --app-dir ml_service
```

또는 `ml_service`로 명시 이동:
```powershell
cd ml_service
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

`Setup-Env.ps1`이 다음을 자동 처리:
- `[Console]::OutputEncoding = UTF8` + `chcp 65001`
- `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`
- `ADMIN_TOKEN=dev_token_local` (미설정 시)
- `FORCE_MOCK=true` (미설정 시)
- `.venv` 활성화 (있을 시)

**주의 — 자동 cd 없음**: 이전 버전은 자동으로 `ml_service`로 이동했지만, 사용자가 다시 `ml_service\...` 입력 시 경로 중복(`ml_service\ml_service\...`) 발생. 현재는 `stepback` 루트에 머무름. 모든 명령 예시는 `ml_service\` 접두어 사용.

---

## API 호출 — 3가지 방식 (택1)

### 방식 1 — Swagger UI (가장 쉬움, 한국어 자동)

브라우저로 http://127.0.0.1:8001/docs

- 모든 24 엔드포인트 시각적 테스트
- 한국어 입력 자동 UTF-8
- "Try it out" → 요청 입력 → "Execute" → 응답 확인
- 인코딩 문제 0건

### 방식 2 — PowerShell 헬퍼 함수 (자동화 용)

```powershell
# 다른 PowerShell 창에서 (서버는 그대로 둔 채)
cd "C:\cogdrill 팀1 ML\stepback"
. .\scripts\Setup-Env.ps1
. .\scripts\Call-Api.ps1     # Call-Label, Get-Drill, Run-Demo 등 로드

# 헬스
Test-Health

# 라벨링
$label = Call-Label "내일 발표 망할 것 같아" "u_demo"
$label | ConvertTo-Json -Depth 5

# 추천 (라벨 응답 전달)
$rec = Call-Recommend -LabelResult $label -SelfCondition 3
$rec | ConvertTo-Json -Depth 5

# 드릴 상세 (v9.5: INT 또는 옛 string 둘 다 호환)
Get-Drill 1
# 또는: Get-Drill D01

# 주간 리포트 (데모)
Get-Weekly -UserId u_demo -Week 2026-W21

# 자가진단 퀴즈 답 저장
Submit-QuizAnswer -Predicted 미래예측 -UserId u_demo

# 드릴 거부 (v9.5: INT)
Reject-Drill -DrillId 1 -UserId u_demo

# 시연 5종 한 번에
Run-Demo
```

### 방식 3 — curl.exe (Linux/Mac 동등)

PowerShell의 `curl` 별칭이 아닌 진짜 curl 사용. 한국어는 파일에 저장 후 `--data-binary`.

```powershell
# 1) UTF-8 JSON 파일 생성
$json = '{"text":"내일 발표 망할 것 같아","user_id":"u_demo"}'
[System.IO.File]::WriteAllText("$pwd\req.json", $json, [System.Text.UTF8Encoding]::new($false))

# 2) curl.exe로 전송
curl.exe -X POST http://127.0.0.1:8001/label `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@req.json"
```

**주의**: PowerShell에서 `curl` 만 쓰면 `Invoke-WebRequest` 별칭이 실행되어 헤더·인코딩 문제 발생. 반드시 `curl.exe` 명시.

---

## 시연 5종 — Swagger UI 흐름 (3분)

1. **인지**: POST /label → `{"text":"내일 발표 망할 것 같아","user_id":"u1"}` → `미래예측 ≥ 0.4` 확인
2. **행동**: POST /label → `{"text":"과제 시작해야 하는데 자꾸 폰만","user_id":"u2"}` → `회피미루기 ≥ 0.5`
3. **위기**: POST /label → `{"text":"사라지고 싶다","user_id":"u3"}` → `crisis_detected: true`
4. **약신호**: POST /label → `{"text":"오늘 평범했어","user_id":"u4"}` → 모든 신호 < 0.3
5. **추천**: POST /recommend → 1번 응답 + context 입력 → `type: "drill"` 또는 `crisis_card`

또는 PowerShell 한 줄:
```powershell
Run-Demo
```

---

## 운영 스크립트

```powershell
# 시연 직전 5 항목 자가 점검
python -X utf8 scripts/pre_demo_check.py

# 카피 검증 — 진단·인과·압박 표현 검출
python -X utf8 scripts/lint_copy.py app/

# 7일 가상 시뮬레이션
python -X utf8 scripts/simulate_recommend.py

# 12명 동시 부하 테스트 (서버 별도 실행 필요)
python -X utf8 scripts/load_test.py --users 12 --rounds 1

# 데모 데이터 시드
python -X utf8 scripts/seed_demo_data.py

# 90일 지난 데이터 삭제
python -X utf8 scripts/purge_old_data.py
```

---

## API 키 발급 후 실 LLM 사용

```powershell
cd "C:\cogdrill 팀1 ML\stepback"
.\.venv\Scripts\activate
pip install google-generativeai

# .env 편집 (notepad .env)
# GEMINI_API_KEY=AIzaSy...
# FORCE_MOCK=false

# 또는 한 줄
$env:GEMINI_API_KEY = "AIzaSy..."
$env:FORCE_MOCK = "false"

# app/infra/llm_client.py의 initialize() TODO 주석 풀기 (NOTES.md §D1 참조)

.\run_serve.bat
# /healthz의 primary_model이 gemini-2.0-flash-lite 등으로 표시되면 성공
```

---

## 비상 — 시연 중 LLM 다운

```powershell
# 같은 셸에서
$env:FORCE_MOCK = "true"
# uvicorn --reload 자동 재시작
```

5 type 분기는 LLM 의존 X — Mock으로 동일 흐름 유지.

---

## 자주 발생하는 PowerShell 문제 + 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `uvicorn : 인식되지 않습니다` | venv 미활성 | `. .\scripts\Setup-Env.ps1` 또는 `python -m uvicorn ...` |
| 한국어 응답 `諛쒗몴` | cp949 출력 | `Setup-Env.ps1` 실행 |
| curl JSON `Unterminated string` | PowerShell 이스케이프 | `Invoke-RestMethod` 또는 `--data-binary @file` |
| `Headers 매개 변수를 바인딩할 수 없습니다` | `curl` ≠ `curl.exe` | `curl.exe` 명시 |
| admin 엔드포인트 503 | ADMIN_TOKEN 미설정 | `Setup-Env.ps1` 또는 `$env:ADMIN_TOKEN="dev_token_local"` |
| 422 ValidationError | 빈 텍스트/이모지만 | text는 1자 이상 의미 있는 문자 |
| 429 quota | 분 1 / 시 3 / 일 3 초과 | 다른 user_id 또는 `/admin/quota/reset` |
| Port 8001 already in use | 기존 uvicorn 미종료 | Ctrl+C 또는 `Get-Process python \| Stop-Process` |
