@echo off
REM CLAUDE.md §8.W6 DoD #1 - 30 케이스 스모크
cd /d "%~dp0\.."
python -X utf8 -m pytest tests/smoke -q
