# BE 팀원에게 보낼 메시지 (그대로 복사 → 전송)

---

안녕하세요! ML 정리되어서 BE에서 반영/확인 부탁드릴 부분 정리했어요. 대부분 자동이라 작업은 많지 않아요 🙂 (3주 일정 고려해 최소화)

**1. `entries` 테이블 컬럼 — 주간 맞춤형의 핵심 (제일 중요)**
ERD를 보니 아래가 빠져 있어요. 이게 없으면 주간 리포트의 상태·경향 분석이 전부 비어요.
```sql
ALTER TABLE entries ADD COLUMN context_json       JSONB;    -- 수면·사교·운동·컨디션 묶음
ALTER TABLE entries ADD COLUMN label_result_json  JSONB;    -- ML이 돌려준 13차원 + evidence_span
ALTER TABLE entries ADD COLUMN drill_completed     BOOLEAN DEFAULT FALSE;
ALTER TABLE entries ADD COLUMN helpful             BOOLEAN;  -- NULL=미평가
```
- `context_json`: 와이어프레임의 "수면 7h 30m / 운동 1h / 컨디션 4단계 / 사교 중" **입력 UI는 이미 있으니, 그 값을 ML `/entries` 응답의 `context_used` 형태로 저장**만 해주시면 됩니다. → 주간 "수면 점감", "사교↔컨디션" 경향이 여기서 나와요.
- `label_result_json`: ML 응답의 `label_result`(점수 + `evidence_span`) 저장. → "컨디션 낮은 날 미래예측↑", "힘든 날 '망할 것 같아' 인용" 경향이 여기서 나와요.
- `drill_completed`·`helpful`: 와이어프레임 "도움돼요/도움안돼요" 버튼 + "완료 6/7"용.
- 자세한 점검표: 첨부 `주간_ERD_점검.md`.

**2. 매일 흐름 / 주간 흐름**
- 매일: `POST /entries` (텍스트 + context) → ML이 추천+라벨 반환 → BE가 위 컬럼에 저장.
- 주간: BE가 그 주 `entries` 7일치를 모아 `POST /weekly` 로 ML에 전달 → ML이 코칭 계산. (ML은 stateless, DB 직접 접근 안 함)

**3. 개인화는 자동 학습 (추가 작업 거의 없음)**
이미 호출하는 엔드포인트가 알아서 갱신해요: `POST /entries`·`/recommend`(노출), `POST /feedback`(도움/완료), `POST /reject`(거부). → 사용자가 완료/평가하면 다음 추천이 그 사람에 맞춰져요.

**4. 추천 응답 (스키마 호환)**
- 정상 흐름은 `drill`만, 위기 시 `crisis_card`만. `ask_user`/`positive_card`/`skip` 없음.
- `recommendation.drill.id`(정수 1~118), `recommendation.why`(왜+효용+근거+evidence 인용) 그대로 저장/전달.
- `/weekly`·`/monthly`에 `weekly_coaching`/`monthly_coaching` 추가 — 추가 필드라 기존 파싱 안 깨져요. passthrough만.

**5. ML 실행 = Gemini 기본**
- `GEMINI_API_KEY` 환경변수만 있으면 자동으로 실제 Gemini. 없으면 Mock 폴백(안 죽음). `FORCE_MOCK=true`로 강제 Mock 가능.
- ML이 BE `119.201.125.216:8080` / DB `5432` 인지 + CORS 자동 포함. 배포 URL을 BE `ML_BASE_URL`로.

**6. (선택)** 주간/월간 야간 배치로 미리 계산해 `reports_weekly/monthly`에 저장하면 빨라져요. 여유 될 때.

꼭 필요한 건 **1번(컬럼)**이에요. 감사합니다!
