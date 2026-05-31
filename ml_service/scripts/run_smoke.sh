#!/usr/bin/env bash
# CLAUDE.md §8.W6 DoD #1 - 30 케이스 스모크
set -e
cd "$(dirname "$0")/.."
python -m pytest tests/smoke -q
