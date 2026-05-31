@echo off
REM Windows 단축 명령 — Makefile 대응판
REM 사용: run_all.bat <target>

if "%1"=="" goto usage
if "%1"=="install" goto install
if "%1"=="test" goto test
if "%1"=="test3" goto test3
if "%1"=="lint" goto lint
if "%1"=="serve" goto serve
if "%1"=="precheck" goto precheck
if "%1"=="smoke" goto smoke
if "%1"=="seed" goto seed
if "%1"=="loadtest" goto loadtest
if "%1"=="demo" goto demo
goto usage

:install
cd ml_service
python -m pip install -r requirements.txt -r requirements-dev.txt
goto end

:test
cd ml_service
python -X utf8 -m pytest tests/ -q
goto end

:test3
cd ml_service
echo === Run 1 ===
python -X utf8 -m pytest tests/ -q
echo === Run 2 ===
python -X utf8 -m pytest tests/ -q
echo === Run 3 ===
python -X utf8 -m pytest tests/ -q
goto end

:lint
cd ml_service
python -X utf8 scripts/lint_copy.py app/
goto end

:serve
cd ml_service
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
goto end

:precheck
cd ml_service
python -X utf8 scripts/pre_demo_check.py
goto end

:smoke
cd ml_service
python -X utf8 -m pytest tests/smoke -v
goto end

:seed
cd ml_service
python -X utf8 scripts/seed_demo_data.py
goto end

:loadtest
cd ml_service
python -X utf8 scripts/load_test.py --users 12 --rounds 1
goto end

:demo
call %0 precheck
call %0 lint
call %0 test
call %0 smoke
echo [demo] ready - uvicorn 실행 후 http://127.0.0.1:8001/docs
goto end

:usage
echo Usage: run_all.bat ^<target^>
echo Targets: install ^| test ^| test3 ^| lint ^| serve ^| precheck ^| smoke ^| seed ^| loadtest ^| demo

:end
