#!/usr/bin/env bash
# Step Back ML — GCP Cloud Run 배포 스크립트 (v9.6)
#
# 사전 준비:
#   1) gcloud CLI 설치 + 로그인:  gcloud auth login
#   2) 프로젝트 지정:             gcloud config set project <YOUR_PROJECT_ID>
#   3) API 활성화:               gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
#   4) ★ Gemini 키를 Secret Manager에 저장 (최종 산출물은 실 Gemini 사용):
#        echo -n "<당신의_GEMINI_API_KEY>" | gcloud secrets create gemini-key --data-file=-
#        # (이미 있으면)  echo -n "<KEY>" | gcloud secrets versions add gemini-key --data-file=-
#
# 실행:  cd stepback && bash ml_service/deploy_gcp.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-asia-northeast3}"          # 서울 리전
SERVICE="${SERVICE:-stepback-ml}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/stepback/${SERVICE}:$(date +%Y%m%d-%H%M%S)"

echo "▶ 프로젝트: ${PROJECT_ID} / 리전: ${REGION} / 서비스: ${SERVICE}"

# Artifact Registry 저장소 (최초 1회만 — 이미 있으면 무시)
gcloud artifacts repositories create stepback \
  --repository-format=docker --location="${REGION}" 2>/dev/null || true

# 빌드 (Cloud Build) — 컨텍스트는 stepback/ 루트
gcloud builds submit --tag "${IMAGE}" -f ml_service/Dockerfile .

# 배포 — ★ 최종 산출물 기본값: 실 Gemini (FORCE_MOCK=false + Secret Manager 키 주입)
#   키가 없거나 호출 실패 시에는 코드가 자동으로 Mock 폴백하므로 서비스는 죽지 않음(안전망).
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --concurrency 20 --max-instances 3 \
  --set-env-vars "DEPLOY_MODE=true,FORCE_MOCK=false,BE_HOST=119.201.125.216,BE_PORT=8080,DB_HOST=119.201.125.216,DB_PORT=5432" \
  --set-secrets "GEMINI_API_KEY=gemini-key:latest"
  #
  # (선택) 데모/연동만 먼저 하고 싶고 키 비용을 아끼려면 Mock으로:
  #   위 두 줄 대신 --set-env-vars "...,FORCE_MOCK=true" 만 사용하고 --set-secrets 제거.

echo "✔ 배포 완료. URL 확인:"
gcloud run services describe "${SERVICE}" --region "${REGION}" --format='value(status.url)'
echo "→ BE의 ML_BASE_URL 환경변수를 위 URL로 설정하세요."
echo "→ 실 Gemini로 떴는지 확인 (ADMIN_TOKEN 헤더 필요):"
echo "   curl -H 'x-admin-token: <ADMIN_TOKEN>' <URL>/healthz/detail   # is_mock=false, primary_model=gemini-* 면 성공"
