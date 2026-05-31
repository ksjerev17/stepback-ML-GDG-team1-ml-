# 내가 직접 실행해서 확인하기 (Step Back ML v9.6)

> 목표: 서버를 띄우고, 핵심 기능(설명가능 추천 / 개인화 적응 / 주간 코칭)을 내 눈으로 확인하고, 테스트가 다 통과하는지 보는 것. Windows(PowerShell) 기준으로 적되, 공통 명령도 같이 적어둘게.

---

## 0. 준비 (최초 1회)

```powershell
cd "C:\cogdrill 팀1 ML\stepback"
# (가상환경 있으면) .\.venv\Scripts\Activate.ps1
pip install -r ml_service\requirements.txt
```
- 키 없이도 다 돌아가(Mock 자동). 실제 Gemini는 GCP 배포 때만 필요.

---

## 1. 서버 띄우기

가장 쉬운 길 — 더블클릭: 탐색기에서 **`run_serve.bat`** 실행.
또는 PowerShell에서:
```powershell
. .\scripts\Setup-Env.ps1     # UTF-8 + ADMIN_TOKEN + venv 자동
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
```
→ 브라우저로 **http://127.0.0.1:8001/docs** 열기. (한국어 입력 자동 처리되는 Swagger UI)

콘솔에 `Application startup complete` 가 보이면 성공. 종료는 Ctrl+C.

---

## 2. 핵심 기능 5가지 — Swagger에서 직접 확인

브라우저 `/docs`에서 각 엔드포인트의 **"Try it out" → 값 입력 → "Execute"**.

### ① 설명가능 추천 (why) — 차별 포인트
- `POST /entries` 에 입력:
```json
{ "text": "내일 발표 망할 것 같아 너무 불안해",
  "user_id": "me_test",
  "context": { "self_condition": 2, "sleep_hours": 4.0 } }
```
- 응답에서 확인할 것:
  - `recommendation.type` = `"drill"`
  - `recommendation.why.text` = **"어젯밤 잠이 부족해서, '미래예측' 생각이 자주 보여서… 골랐어요."** ← 이게 보이면 성공
  - `recommendation.drill.id` (정수), `drill_category`, `drill_calendar_color`

### ② 항상 드릴 + 안정적인 날 톤
- `POST /entries` 에 `text: "오늘은 잔잔하고 평온했어"`, `context: {"self_condition":5,"sleep_hours":8}` 넣어보기.
- 응답 `recommendation.tone` 이 `"positive"`, copy가 "오늘은 신호가 잔잔한 하루네요…" → 성공.
- (어떤 입력을 넣어도 `ask_user`/`positive_card`/`skip`은 안 나오고 `drill` 또는 `crisis_card`만 나옴)

### ③ 위기 안전망 (반드시 확인)
- `POST /entries` 에 위기 표현(예: "죽고 싶어") 넣기 → 응답 `type` = `"crisis_card"` + 1393/1388/1577-0199 안내. 드릴 추천 안 됨. (LLM 호출 전에 차단)

### ④ 개인화가 "나에게 맞춰 변하는지" — 가장 인상적인 데모
같은 사용자로 아래를 순서대로:
1. `GET /personalization/profile?user_id=me_test` → 처음엔 `total_offers`가 작고 `is_learning_active=false`.
2. `POST /feedback` 를 같은 카테고리로 3~4번 "helpful"로 보냄. 예:
```json
{ "user_id":"me_test", "drill_id": 50, "rating":"helpful", "recommended_at":"2026-05-28" }
```
   (drill_id는 ②③에서 받은 self_compassion/grounding 계열 id로)
3. 다시 `GET /personalization/profile?user_id=me_test` → 그 카테고리 `n_helpful`↑, `reward_estimate`↑, `ucb_bonus`↑, `is_learning_active=true`.
4. `GET /personalization/next_focus?user_id=me_test&state_key=stable` → 그 카테고리가 다음 초점으로 추천됨.
→ "내 선택이 추천을 바꾼다"가 눈에 보이면 성공.

### ⑤ 주간 코칭 (상태 + 다변량 경향 + 다음 초점)
- `GET /weekly?user_id=me_test&week=2026-W21`
- 응답 `weekly_coaching` 에서:
  - `state.label` (예: "소진기") + `summary`
  - `tendencies[]` — "수면이 점점 줄어드는 흐름", "사람과 갈등이 있던 날엔 컨디션이 더 낮았던 편" 등 여러 개
  - `next_week_focus.label_ko` + `reason`
- `GET /monthly?user_id=me_test&month=2026-05` → `monthly_coaching`도 같은 구조.

---

## 3. 테스트 전부 통과 확인

```powershell
cd ml_service
$env:ADMIN_TOKEN = "dev_token_local"
python -m pytest -q
```
→ **`254 passed`** 가 나오면 완성. (ADMIN_TOKEN을 안 넣으면 admin 4개가 skip/1 fail로 보이는데 코드 문제 아님 — 넣으면 다 통과)

특정 영역만 빨리 보고 싶으면:
```powershell
python -m pytest tests/integration/test_personalization_v96.py tests/integration/test_v96_reinforcement.py -q
```

---

## 4. (선택) 개인화 적응 루프를 스크립트로 한 번에 보기
PowerShell/터미널에서:
```powershell
cd "C:\cogdrill 팀1 ML\stepback"
python - <<'PY'
import sys; sys.path.insert(0,"ml_service")
from app.core import personalization as pz
print("처음:", {k:round(v,2) for k,v in pz.bonus_map("demo").items()})
for _ in range(5):
    pz.record_offer("demo","self_compassion"); pz.record_outcome("demo","self_compassion",completed=True,helpful=True)
for _ in range(3):
    pz.record_offer("demo","grounding"); pz.record_reject("demo","grounding")
print("학습 후:", {k:round(v,2) for k,v in pz.bonus_map("demo").items()})
print("가장 잘 맞은:", pz.top_helpful_category("demo")["label_ko"])
PY
```
→ self_compassion 가산점이 grounding보다 커지고, "가장 잘 맞은: 자기 자비"가 나오면 개인화가 정상 작동.

---

## 5. (인프라 담당과 함께) GCP에 ML 올리기
```bash
cd stepback
gcloud auth login
gcloud config set project <프로젝트ID>
bash ml_service/deploy_gcp.sh
```
→ 끝에 출력되는 URL을 BE의 `ML_BASE_URL`로 설정. (실 Gemini 쓰려면 배포 시 `FORCE_MOCK=false` + `GEMINI_API_KEY` 주입)

---

## 막히면
- Swagger `/docs`에서 모든 엔드포인트의 정확한 입력/응답 형태를 바로 볼 수 있어.
- 한글 깨지면 `scripts\Setup-Env.ps1`을 먼저 실행(UTF-8 설정).
- 포트 충돌나면 `--port 8002`처럼 바꿔서 실행.
