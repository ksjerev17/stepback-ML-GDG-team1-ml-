@echo off
REM 한 번 클릭으로 테스트 — UTF-8 + ADMIN_TOKEN + venv 자동
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
if "%ADMIN_TOKEN%"=="" set ADMIN_TOKEN=dev_token_local
if "%FORCE_MOCK%"=="" set FORCE_MOCK=true

cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

cd ml_service
python -X utf8 -m pytest tests/ -q
