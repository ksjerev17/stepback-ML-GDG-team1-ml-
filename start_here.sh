#!/usr/bin/env bash
# ====================================================================
#  Step Back ML — 원클릭 실행 (mac / Linux / 기타 환경)
#  사용:  bash start_here.sh
#  기본값: Gemini (GEMINI_API_KEY 있으면 자동). 없으면 Mock 자동 폴백.
# ====================================================================
set -e
cd "$(dirname "$0")"

# ml_service 자동 탐색 (현재 폴더 또는 stepback/ 하위)
if [ ! -f "ml_service/app/main.py" ]; then
  if [ -f "stepback/ml_service/app/main.py" ]; then
    cd stepback
  else
    echo "[오류] ml_service 폴더를 찾지 못했습니다. ml_service 가 보이는 폴더에서 실행하세요."
    exit 1
  fi
fi

# 의존성 (최초 1회 자동 설치 시도; 권한 문제 시 무시)
python3 -c "import fastapi" 2>/dev/null || pip install -r ml_service/requirements.txt --break-system-packages 2>/dev/null || pip install -r ml_service/requirements.txt 2>/dev/null || true

export PYTHONUTF8=1
export ADMIN_TOKEN="${ADMIN_TOKEN:-dev_token_local}"
export AUDIT_SALT="${AUDIT_SALT:-local_dev_salt_change_me_0123456789abcd}"
PORT="${PORT:-8001}"

echo ""
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "[모드] GEMINI_API_KEY 없음 → Mock 실행 (전 기능 동작)."
  echo "       실제 Gemini:  export GEMINI_API_KEY=AIza...키...  후 다시 실행"
else
  echo "[모드] Gemini 키 감지 → 실제 Gemini 실행."
fi
echo "[주소] http://127.0.0.1:${PORT}/docs"
echo "[종료] Ctrl + C"
echo ""

exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}" --app-dir ml_service
