# Step Back ML — GCP Cloud Run / Docker 배포용 (v9.6)
# 빌드 컨텍스트는 stepback/ (상위) — w1 드릴 카탈로그를 함께 담기 위함.
#
# 로컬 빌드/실행:
#   cd stepback
#   docker build -f ml_service/Dockerfile -t stepback-ml .
#   docker run -p 8001:8001 --env-file .env stepback-ml
#
# GCP Cloud Run 배포: ml_service/deploy_gcp.sh 참고.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    DEPLOY_MODE=true

WORKDIR /srv

# 의존성 먼저 (레이어 캐시 최적화)
COPY ml_service/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

# 앱 + 드릴 카탈로그(w1) 복사
COPY ml_service /srv/ml_service
COPY w1 /srv/w1

WORKDIR /srv/ml_service
ENV PYTHONPATH=/srv/ml_service

# Cloud Run은 $PORT(기본 8080)를 주입. 로컬은 8001.
ENV PORT=8001
EXPOSE 8001

# 0.0.0.0 바인딩 — 외부(BE)에서 접근 가능.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
