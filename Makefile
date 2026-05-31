# 사용: make <target>  (Unix/Mac/WSL/Git Bash). Windows CMD는 run_all.bat 사용.

.PHONY: install test test3 lint serve demo precheck smoke seed loadtest

install:
	cd ml_service && python -m pip install -r requirements.txt -r requirements-dev.txt

test:
	cd ml_service && python -X utf8 -m pytest tests/ -q

test3:
	cd ml_service && for i in 1 2 3; do echo "Run $$i" && python -X utf8 -m pytest tests/ -q; done

lint:
	cd ml_service && python -X utf8 scripts/lint_copy.py app/
	cd ml_service && ruff check . || true
	cd ml_service && ruff format --check . || true

serve:
	cd ml_service && uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

precheck:
	cd ml_service && python -X utf8 scripts/pre_demo_check.py

smoke:
	cd ml_service && python -X utf8 -m pytest tests/smoke -v

seed:
	cd ml_service && python -X utf8 scripts/seed_demo_data.py

loadtest:
	cd ml_service && python -X utf8 scripts/load_test.py --users 12 --rounds 1

demo: precheck lint test smoke
	@echo "[demo] 시연 준비 완료 — uvicorn 실행 후 http://127.0.0.1:8001/docs"
