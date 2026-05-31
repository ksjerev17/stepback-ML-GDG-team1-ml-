# Step Back ML — 실행 & 직접 확인 가이드 (v9.6)

> 팀 누구나 보고 따라 할 수 있게 만든 문서야. **PowerShell에 한 줄씩 복붙**하면 돼.
> 목표: ① 내 PC에서 ML 서버 띄우기(실제 Gemini), ② 모든 기능을 눈으로 확인, ③ 테스트 254+ 통과 확인.
>
> 아직 코드를 처음 보는 팀원이라면 **0~4단계만** 따라 해도 서버가 떠. 그 뒤 6단계에서 기능을 하나씩 눌러보면 돼.

---

## 0. 폴더 위치 확인 (제일 먼저)

압축 푼 폴더로 이동:
```powershell
cd "C:\cogdrill 팀1 ML\stepback_v9.6_complete"
dir
```
여기서 두 경우 중 하나야:
- **(가)** `ml_service`, `w1`, `handoff` 가 바로 보임 → 여기가 작업 폴더. 그대로 진행.
- **(나)** `stepback` 폴더 하나만 보임 → 한 칸 더 들어가기:
  ```powershell
  cd stepback
  dir
  ```
**`ml_service` 와 `w1` 이 같이 보이는 위치**가 맞는 자리. 이 위치에서 아래를 계속한다.

> 💡 앞으로 이 문서에서 "작업 폴더"라고 하면 = `ml_service`와 `w1`이 보이는 그 폴더.

---

## 1. 파이썬 확인 (최초 1회)

```powershell
python --version
```
- `Python 3.10` 이상이면 OK (3.11~3.12 권장).
- "인식할 수 없습니다" 가 나오면 파이썬 미설치 → https://www.python.org/downloads/ 에서 설치할 때 **"Add Python to PATH" 체크** 후 다시 0단계부터.

---

## 2. 패키지 설치 (최초 1회)

```powershell
pip install -r ml_service\requirements.txt
```
- `Successfully installed ...` 나오면 완료. (1~2분 소요)
- 빨간 에러가 나면 그 메시지를 팀에 공유.

---

## 3. 환경변수 설정 (이 창에서만 유효)

> ⚠️ 중요: 환경변수는 **지금 연 PowerShell 창에서만** 살아있다. 창을 새로 열면 이 3단계를 다시 쳐야 한다.

### 3-A. 실제 Gemini로 돌리려면 (최종 산출물 방식)
```powershell
chcp 65001 > $null
$env:PYTHONUTF8 = "1"
$env:FORCE_MOCK = "false"
$env:GEMINI_API_KEY = "여기에_AIza로_시작하는_키_붙여넣기"
$env:AUDIT_SALT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa32자이상아무문자열"
$env:ADMIN_TOKEN = "dev_token_local"
```
- `GEMINI_API_KEY` 의 따옴표는 그대로 두고, AIza... 부분만 네 키로 교체.
- 키가 아직 없으면: **aistudio.google.com → 로그인 → 좌측 "Get API key" → "Create API key"** (무료, 카드 필요 없음). 자세한 건 `GCP_Gemini_가이드.md` 참고.

### 3-B. 키 없이 Mock으로 먼저 보고 싶으면 (기능 확인용으로 충분)
```powershell
chcp 65001 > $null
$env:PYTHONUTF8 = "1"
$env:FORCE_MOCK = "true"
$env:ADMIN_TOKEN = "dev_token_local"
```
> Mock이어도 추천/주간코칭/개인화 등 전 기능이 똑같이 동작한다. "실제 Gemini 호출"만 안 할 뿐.

---

## 4. 서버 실행

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
```
- `Application startup complete` 가 보이면 성공. **이 창은 끄지 말 것**(서버가 살아있는 창).
- 브라우저에서 **http://127.0.0.1:8001/docs** 열기 → 한국어 입력 가능한 Swagger 화면.
- 서버 종료: 그 창에서 `Ctrl + C`. / 포트 충돌 시 `--port 8002` 로 변경.

---

## 5. Gemini로 진짜 떴는지 확인

서버 창은 그대로 두고, **PowerShell 창을 하나 더 열어서**:
```powershell
curl.exe -H "x-admin-token: dev_token_local" http://127.0.0.1:8001/healthz/detail
```
응답에서 확인:
- `"is_mock": false` → **실제 Gemini로 동작 중** ✅ (3-B Mock으로 켰으면 여기 `true`가 정상)
- `"primary_model": "gemini-..."` → 잡힌 모델명

> `is_mock`이 의도와 다르면: 3단계 환경변수를 넣은 **그 창에서** 4단계를 실행했는지 확인(창을 새로 열었으면 변수가 날아감).

---

## 6. 핵심 기능 직접 확인 (Swagger `/docs`)

각 항목은 `/docs`에서 해당 엔드포인트 → **"Try it out" → 값 입력 → "Execute"**.

### ① 설명가능 추천 (why) — 우리 차별 포인트
`POST /entries`:
```json
{ "text": "내일 발표 망할 것 같아 너무 불안해",
  "user_id": "me_test",
  "context": { "self_condition": 2, "sleep_hours": 4.0 } }
```
확인: `recommendation.type` = `"drill"`, 그리고
`recommendation.why.text` = **"어젯밤 잠이 부족해서, '미래예측' 생각이 자주 보여서… 골랐어요."**
+ `recommendation.drill.id`(정수), `drill_category`, `drill_calendar_color`.

### ② 항상 드릴 + 안정적인 날 톤
`POST /entries` 에 `text: "오늘은 잔잔하고 평온했어"`, `context: {"self_condition":5,"sleep_hours":8}`.
확인: `type` = `"drill"`, `tone` = `"positive"`, copy가 "오늘은 신호가 잔잔한 하루네요…".
> 어떤 입력을 넣어도 `ask_user`/`positive_card`/`skip`은 안 나오고 `drill` 또는 `crisis_card`만 나온다.

### ③ 위기 안전망 (반드시 확인)
`POST /entries` 에 위기 표현(예: `"죽고 싶어"`).
확인: `type` = `"crisis_card"` + 전화번호(1393/1388/1577-0199) 안내, 드릴 추천 안 됨.
> 이 경우 위기 텍스트는 **Gemini로 전송되지 않고** 서버 안에서 차단된다(안전 설계).

### ④ 개인화가 "나에게 맞춰 변하는지" — 가장 인상적인 데모
같은 사용자로 순서대로:
1. `GET /personalization/profile?user_id=me_test` → 처음엔 `total_offers` 작고 `is_learning_active=false`.
2. `POST /feedback` 를 같은 카테고리로 3~4번 "helpful"로 전송:
```json
{ "user_id":"me_test", "drill_id": 50, "rating":"helpful", "recommended_at":"2026-05-29" }
```
   (drill_id는 ①~③에서 받은 id 사용. recommended_at은 오늘 날짜)
3. 다시 `GET /personalization/profile?user_id=me_test` → 그 카테고리 `n_helpful`↑, `reward_estimate`↑, `ucb_bonus`↑, `is_learning_active=true`.
4. `GET /personalization/next_focus?user_id=me_test&state_key=stable` → 그 카테고리가 다음 초점으로.
→ "내 선택이 추천을 바꾼다"가 보이면 성공.

### ⑤ 주간 코칭 (상태 + 다변량 경향 + 다음 초점)
`GET /weekly?user_id=me_test&week=2026-W21`
확인: `weekly_coaching` 안에
- `state.label`(예: "소진기") + `summary`
- `tendencies[]` — "수면이 점점 줄어드는 흐름", "사람과 갈등이 있던 날엔 컨디션이 더 낮았던 편" 등 여러 개 + 신뢰도 `strength`
- `next_week_focus.label_ko` + `reason`

### ⑥ 월간 코칭
`GET /monthly?user_id=me_test&month=2026-05` → `monthly_coaching` 이 ⑤와 같은 구조로 존재.

---

## 7. 테스트 전부 통과 확인 (코드 검증)

서버는 꺼도 됨. 작업 폴더에서:
```powershell
cd ml_service
$env:ADMIN_TOKEN = "dev_token_local"
python -m pytest -q
```
- **`256 passed`** 가 나오면 완성. (ADMIN_TOKEN을 안 넣으면 admin 4개가 skip/일부 fail로 보이는데, 코드 문제 아님 — 넣으면 전부 통과)
- 다시 상위 폴더로: `cd ..`

특정 영역만 빠르게:
```powershell
python -m pytest tests/integration/test_personalization_v96.py tests/integration/test_v96_reinforcement.py -q
```

---

## 8. (선택) 개인화 적응 루프를 스크립트로 한 번에 보기

작업 폴더에서:
```powershell
python - << 'PY'
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
→ self_compassion 가산점이 grounding보다 커지고 "가장 잘 맞은: 자기 자비"가 나오면 개인화 정상.

---

## 9. 자주 막히는 곳

| 증상 | 원인 / 해결 |
|---|---|
| `python` 인식 안 됨 | 파이썬 미설치 또는 PATH 미등록 → 1단계 |
| 한글 깨짐 | 3단계의 `chcp 65001` + `$env:PYTHONUTF8="1"` 를 먼저 실행 |
| `is_mock: true` 인데 Gemini 쓰고 싶음 | 키 넣은 **그 창**에서 서버를 띄웠는지 확인(새 창이면 변수 날아감) |
| 포트 충돌 | `--port 8002` 처럼 바꿔 실행 |
| `ModuleNotFoundError` | 2단계 `pip install` 다시 / `--app-dir ml_service` 빠졌는지 확인 |
| pytest에서 admin 테스트 실패 | `$env:ADMIN_TOKEN="dev_token_local"` 설정 후 재실행 |

---

## 10. 한눈에 요약 (실제 Gemini로 띄우는 최소 절차)

```powershell
cd "C:\cogdrill 팀1 ML\stepback_v9.6_complete"      # (나)면 cd stepback 추가
pip install -r ml_service\requirements.txt          # 최초 1회
chcp 65001 > $null; $env:PYTHONUTF8="1"
$env:FORCE_MOCK="false"; $env:GEMINI_API_KEY="AIza...키..."; $env:AUDIT_SALT="32자이상문자열"; $env:ADMIN_TOKEN="dev_token_local"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service
# 새 창에서:  curl.exe -H "x-admin-token: dev_token_local" http://127.0.0.1:8001/healthz/detail
# 브라우저:   http://127.0.0.1:8001/docs
```
