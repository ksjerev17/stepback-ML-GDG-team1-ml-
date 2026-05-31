@echo off
REM ====================================================================
REM  Step Back ML — 원클릭 실행 (Windows)
REM  이 파일을 stepback 폴더(= ml_service 가 보이는 폴더)에 두고 더블클릭.
REM  기본값: Gemini (환경변수 GEMINI_API_KEY 가 있으면 자동 사용).
REM          키가 없으면 자동으로 Mock 으로 동작 (그래도 전 기능 동작).
REM ====================================================================
chcp 65001 > nul
cd /d "%~dp0"

REM ml_service 가 현재 폴더에 없으면 한 칸 안(stepback)으로 자동 이동
if not exist "ml_service\app\main.py" (
  if exist "stepback\ml_service\app\main.py" (
    cd stepback
  ) else (
    echo [오류] ml_service 폴더를 찾지 못했습니다.
    echo 이 .bat 파일을 'ml_service' 가 보이는 폴더에 두고 실행하세요.
    pause
    exit /b 1
  )
)

REM 감사로그 salt 기본값 (운영 시 환경변수로 교체 권장)
if "%AUDIT_SALT%"=="" set AUDIT_SALT=local_dev_salt_change_me_0123456789abcd
set ADMIN_TOKEN=dev_token_local
set PYTHONUTF8=1

echo.
if "%GEMINI_API_KEY%"=="" (
  echo [모드] GEMINI_API_KEY 가 없어 Mock 으로 실행합니다.
  echo        실제 Gemini 로 쓰려면 이 창에서 먼저:  set GEMINI_API_KEY=AIza...키...
) else (
  echo [모드] Gemini 키 감지 → 실제 Gemini 로 실행합니다.
)
echo [주소] http://127.0.0.1:8001/docs  (브라우저로 열기)
echo [종료] 이 창에서 Ctrl + C
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
pause
