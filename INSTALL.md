# 설치 가이드 — Windows 우선

## 사전 요구사항

- **Python 3.11~3.13 권장** (3.14는 pydantic 일부 wheel 부재 — `requirements.txt`가 이미 `>=2.10.4`로 대응)
- pip / venv
- (시연 시) 노트북 와이파이 + 1393 단축번호
- (선택) Git, Docker

## 1. 한 번만 — 초기 셋업

```powershell
# 폴더로 이동
cd "C:\cogdrill 팀1 ML\stepback"

# Python 가상환경
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 의존성 (Python 3.14도 가능하도록 pydantic>=2.10.4)
python -m pip install --upgrade pip
pip install -r ml_service\requirements.txt -r ml_service\requirements-dev.txt

# 환경 변수 파일 (API 키 없으면 FORCE_MOCK=true 그대로 OK)
copy .env.example .env
# notepad .env  로 ADMIN_TOKEN / GEMINI_API_KEY 입력 (선택)
```

### Mac/Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r ml_service/requirements.txt -r ml_service/requirements-dev.txt
cp .env.example .env
```

## 2. PowerShell 인코딩 + 환경 통합 셋업 (Windows 필수)

**새 PowerShell 창을 열 때마다** 인코딩이 cp949로 돌아가서 한국어 응답이 깨집니다.
한 번에 모두 잡는 헬퍼 스크립트:

```powershell
. .\scripts\Setup-Env.ps1
```

자동 처리:
- UTF-8 콘솔 (`chcp 65001`) + `PYTHONIOENCODING=utf-8`
- `ADMIN_TOKEN=dev_token_local` (admin 엔드포인트 활성화)
- `FORCE_MOCK=true` (Gemini 키 없어도 안전)
- `.venv` 활성화

**자동 cd는 일부러 안 함** — `stepback` 루트에 머무르고 모든 명령은 `ml_service\...` 접두어로 명시. (이전 버전의 경로 중복 문제 해결)

### PowerShell 프로필에 자동 로드 (한 번만)

```powershell
notepad $PROFILE
# 다음 한 줄 추가:
# function sb { Set-Location "C:\cogdrill 팀1 ML\stepback"; . .\scripts\Setup-Env.ps1 }
```

이후 어디서든 `sb` 한 글자로 셋업 완료.

## 3. PowerShell 실행 정책 (스크립트 차단 시)

다음 에러가 나면:
```
이 시스템에서 스크립트를 실행할 수 없으므로 ...\Activate.ps1 파일을 로드할 수 없습니다.
```

→ 현재 사용자에 한해 RemoteSigned 허용:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 4. 동작 확인

```powershell
cd ml_service
python -X utf8 -m pytest tests/ -q
# 207 passed 기대 (v9.5, ADMIN_TOKEN 설정 시)
# 158 passed + 4 skipped + 1 fail (미설정 시 — admin 테스트만 skip)

python -X utf8 scripts/pre_demo_check.py
# 5/5 PASS 기대
```

## 5. 서버 시작 — 3가지 방식

### 방식 1 — 더블 클릭 (가장 쉬움)

탐색기에서 `run_serve.bat` 더블 클릭. UTF-8·ADMIN_TOKEN·venv·이동 모두 자동.

### 방식 2 — PowerShell

```powershell
.\run_serve.bat
```

### 방식 3 — 수동

```powershell
. .\scripts\Setup-Env.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

확인: 브라우저로 http://127.0.0.1:8001/docs (Swagger UI)

## 6. Docker 옵션 (미설치 가능)

학부 MVP는 uvicorn 직접 실행으로 충분. Docker는 BE 통합 또는 격리 운영 시점에만 필요.

설치하려면: https://www.docker.com/products/docker-desktop/ (Windows는 WSL2 필요)

실행:
```powershell
docker compose -f ml_service\docker-compose.local.yml up
```

## 7. 데이터 위치

```
stepback/
├── .env                              ← 절대 git X (.gitignore 이미 처리)
├── logs/audit-YYYY-MM-DD.jsonl       ← 일별 hash 로깅
└── ml_service/data/
    ├── feedback.db                   ← 드릴 평가 SQLite
    ├── insights.db                   ← 발견·리포트·rejected·quiz
    └── baselines.db                  ← 30일 누적 평균
```

모두 git ignore. 회원 탈퇴 시 자동 삭제 (`DELETE /users/{id}/data`).

## 8. 의존성 트러블슈팅

| 증상 | 해결 |
|---|---|
| `pydantic-core` 빌드 실패 (`maturin`) | Python 3.14 + 구 pydantic 조합. `requirements.txt`는 이미 `pydantic>=2.10.4`로 해결. `pip install --upgrade` |
| 한국어 깨짐 | `. .\scripts\Setup-Env.ps1` 또는 모든 python에 `-X utf8` |
| `uvicorn 인식 안 됨` | `.venv` 미활성. `Setup-Env.ps1` 또는 `python -m uvicorn ...` |
| port 8001 already in use | `Get-Process python \| Stop-Process` 또는 다른 포트 |
| admin 엔드포인트 503 | `ADMIN_TOKEN` 미설정 — Setup-Env.ps1이 자동 설정 |
| google.generativeai import 실패 | 키 받기 전엔 미사용. 받으면 `pip install google-generativeai` |

## 9. 새 팀원 합류 시

1. 폴더 압축본 또는 `git clone` 전달
2. 이 `INSTALL.md` 따라 설치 (1~5번)
3. `RUN.md` 읽기 (Swagger UI 또는 PowerShell 헬퍼)
4. `TEST.md` 따라 검증
5. 본인 영역:
   - P2 (BE): `HANDOFF_TO_BE.md` + `handoff/be_integration_guide.md`
   - P3 (FE): `handoff/fe_integration_guide.md`
   - P4 (캘린더): `handoff/calendar_color_spec.md`
   - P5 (콘텐츠): `handoff/content_guide.md`
