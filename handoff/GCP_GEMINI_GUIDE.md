# GCP / Gemini 사용법 — 처음 쓰는 사람 기준 (Step Back ML)

> 큰 그림부터. **두 가지는 완전히 별개야.**
> - **① Gemini API 키** = AI(라벨링)를 돌리는 열쇠. **무료, 신용카드 필요 없음.** (Google AI Studio)
> - **② 서비스 호스팅** = 우리 ML 서버(FastAPI)를 어디에 띄울지. 후보 2개: (A) 이미 있는 BE 서버, (B) GCP Cloud Run.
>
> 즉 "GCP를 꼭 써야" 하는 건 아니야. Gemini 키만 무료로 받고, 서버는 **이미 가진 BE 서버(119.201.125.216)** 에 올리면 카드 없이 끝낼 수도 있어. 아래에 둘 다 적어둘게.

---

## A. Gemini API 키 받기 (무료, 카드 X) — 2분

1. **https://aistudio.google.com** 접속 → 구글 계정 로그인.
2. 왼쪽 사이드바 **"Get API key"** 클릭.
3. **"Create API key"** → 구글 클라우드 프로젝트를 자동으로 하나 만들어 줌 → 그대로 진행.
4. `AIza...` 로 시작하는 키가 생성됨 → **복사해서 안전한 곳에 보관.**
5. (권장) 보안: 콘솔에서 그 키를 **"Generative Language API"** 로만 쓰도록 제한(restrict) 걸어두기.

**무료 한도 (2026 기준):** Gemini 2.5 Flash = 분당 10회·하루 약 250~1500회, 2.5 Flash-Lite도 무료.
우리 코드가 쓰는 모델이 딱 이 무료 모델들이라 **하루 1인 1입력** 규모면 비용 0.
**주의:** 키 깃허브에 올리지 말 것. 키는 만료 안 됨(직접 지우기 전까지).

> 이 키만으로 로컬에서 실 Gemini를 바로 테스트할 수 있어 (아래 D 참고). GCP 결제계정 필요 없음.

---

## B. 우리 서버 어디에 올릴까 — 두 갈래

### B-1. 이미 있는 BE 서버에 올리기 (카드 불필요 · 가장 간단 · 추천)
너흰 `119.201.125.216` 서버가 이미 있잖아. 거기에 Docker로 ML을 같이 띄우면 GCP·카드 다 필요 없어.
```bash
# BE 서버에 접속한 상태에서, stepback/ 폴더에서:
docker build -t stepback-ml -f ml_service/Dockerfile .
docker run -d --name stepback-ml -p 8001:8080 \
  -e FORCE_MOCK=false \
  -e GEMINI_API_KEY="AIza...(아까 받은 키)" \
  -e AUDIT_SALT="(32자 이상 랜덤 문자열)" \
  stepback-ml
```
- 그러면 ML이 `119.201.125.216:8001` 에서 뜸. BE의 `ML_BASE_URL` 을 `http://127.0.0.1:8001`(같은 서버면) 로 설정.
- Docker 없으면 그냥 `uvicorn` 으로도 가능 (RUN_AND_VERIFY.md 참고).
- **장점:** 카드/GCP 0. **단점:** 서버 죽으면 직접 살려야 함.

### B-2. GCP Cloud Run에 올리기 (자동 확장 · 무료 한도 $0 · 단, 카드 등록 필요)
"클라우드에 정석으로 올리고 싶다" 면 이 길. 무료 한도(월 200만 요청) 안이면 **요금 $0** 이지만, **무료라도 결제 계정(카드)을 붙여야** 함 (2026.2.3부터 규칙 강화). 아래 C로.

---

## C. GCP Cloud Run 배포 단계별

### C-0. 준비물
- 구글 계정, **신용/체크카드 1장** (무료 한도 안이면 청구 안 됨. 본인확인용).
- `gcloud` CLI 설치: https://cloud.google.com/sdk/docs/install

### C-1. 프로젝트 + 결제 계정
1. https://console.cloud.google.com 접속 → 상단에서 **새 프로젝트** 생성 (이름 예: `stepback`).
2. 좌측 **결제(Billing)** → **결제 계정 만들기** → 카드 등록.
   - 신규 가입이면 **$300 크레딧(90일)** 이 들어옴. (단, 이 크레딧은 **AI Studio Gemini API 요금엔 못 씀** — Gemini는 위 A의 무료 한도로 충당)
3. 프로젝트에 그 결제 계정을 연결.

### C-2. gcloud 로그인 + API 켜기
```bash
gcloud auth login
gcloud config set project <프로젝트ID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com
```

### C-3. Gemini 키를 Secret Manager에 저장 (코드에 키를 안 박기 위함)
```bash
echo -n "AIza...(A에서 받은 키)" | gcloud secrets create gemini-key --data-file=-
# 나중에 키 바꾸려면:
# echo -n "새키" | gcloud secrets versions add gemini-key --data-file=-
```

### C-4. 배포 (준비된 스크립트 실행)
```bash
cd stepback
bash ml_service/deploy_gcp.sh
```
- 이 스크립트가 **빌드 → Cloud Run 배포(서울 리전, 실 Gemini 기본)** 까지 자동으로 함.
- 끝에 **서비스 URL** 이 출력됨 (예: `https://stepback-ml-xxxxx.run.app`).

### C-5. 실 Gemini로 떴는지 확인
```bash
curl -H "x-admin-token: <ADMIN_TOKEN>" <위에서 나온 URL>/healthz/detail
# 응답에 "is_mock": false, "primary_model": "gemini-..." 면 성공!
```

### C-6. BE에 연결
- BE의 환경변수 `ML_BASE_URL` 을 C-4에서 나온 URL로 설정 → 연동 끝.

---

## D. GCP 없이 로컬에서 실 Gemini 먼저 테스트 (선택)
배포 전에 "Gemini가 진짜 도는지" 내 PC에서 보고 싶으면:
```powershell
# PowerShell
$env:FORCE_MOCK = "false"
$env:GEMINI_API_KEY = "AIza...(A에서 받은 키)"
python -m uvicorn app.main:app --port 8001 --app-dir ml_service
```
→ `/docs` 에서 `POST /entries` 해보고, `/healthz/detail`(admin 토큰 헤더)에서 `is_mock:false` 확인.
→ 이건 카드도 GCP도 필요 없음. **Gemini 키만 있으면 됨.**

---

## E. 비용 · 안전 (꼭 읽기)
- **Gemini 키 자체는 무료**(카드 X). 우리가 쓰는 모델이 무료 tier라 1일 1입력 규모면 $0.
- **Cloud Run 무료 한도**: 월 200만 요청 + 컴퓨팅 시간 무료. 우리 트래픽이면 사실상 $0. 단 **카드 등록은 필수**.
- **$300 크레딧은 Gemini API엔 못 씀** — Gemini는 A의 무료 tier로, Cloud Run/빌드 등은 크레딧/무료한도로.
- **예산 알림 걸어두기**: 콘솔 → 결제 → 예산 및 알림 → 50%/90%/100%에서 메일 알림. 사고 방지.
- **egress 무료 1GiB/월**(북미). 우리 응답은 작은 JSON이라 걱정 X.

---

## F. 정직한 한계 / 역할 분담
- **실제 GCP에 띄우는 행위**는 카드·계정 권한이 필요해서 ML 쪽(또는 AI 도구)이 대신 못 함 — 너 또는 인프라 담당이 위 C를 실행해야 함.
- 추천 순서: **(1) D로 로컬에서 Gemini 확인 → (2) B-1(BE 서버) 또는 C(Cloud Run) 중 택1로 배포 → (3) BE의 ML_BASE_URL 연결.**
- 학생 프로젝트면 **B-1(이미 있는 BE 서버) + Gemini 무료키** 조합이 제일 싸고 단순해. "정석 클라우드 경험"이 목표면 C(Cloud Run).
