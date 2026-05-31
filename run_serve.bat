@echo off
REM 한 번 클릭으로 서버 띄우기 — UTF-8 + ADMIN_TOKEN + venv 자동
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if "%ADMIN_TOKEN%"=="" set ADMIN_TOKEN=dev_token_local
if "%FORCE_MOCK%"=="" set FORCE_MOCK=true

cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

cd ml_service
echo [run_serve] http://127.0.0.1:8001/docs
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
