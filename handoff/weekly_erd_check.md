# 주간 맞춤형 ↔ ERD 점검 (BE에게 전달용)

> 주간 리포트의 맞춤형(상태·다변량 경향·다음 초점·개인화 노트)이 동작하려면, 사용자가 매일 입력한 것이 DB에 남아 ML로 전달돼야 합니다. 아래는 그 필드들이 현재 ERD에 있는지 점검한 결과입니다.

## 결론 먼저
주간 맞춤형은 **`entries` 테이블의 3개 컬럼**에 의존합니다. 이 중 **`context_json`이 ERD에 없을 가능성이 높아** 추가가 필요합니다. 나머지는 ERD에 있거나 ML이 자체 보관합니다.

## 필드별 점검

| 맞춤형 기능 | 필요한 데이터 | ERD 위치 | 상태 |
|---|---|---|---|
| 상태("소진기") + 컨디션 흐름 | `self_condition` (1~5) | `entries.self_condition` | ✅ 있음 (와이어프레임의 "컨디션 4단계") |
| 경향: 수면 점감, 수면↔패턴 | `sleep_hours` | `entries.context_json` | 🔴 **누락 — 추가 필요** |
| 경향: 사교↔컨디션/감정 | `social_today` (좋음/보통/갈등) | `entries.context_json` | 🔴 **누락 — 추가 필요** |
| 경향: 운동↔컨디션 | `exercise_today` | `entries.context_json` | 🔴 **누락 — 추가 필요** |
| 경향: 컨디션↔'미래예측' 등 | 그날의 13차원 라벨 | `entries.label_result_json` (또는 분해 저장) | 🟡 저장 방식 확인 필요 |
| 경향: 힘든 날 '망할 것 같아' 인용 | `evidence_span` | `entries.label_result_json` 내 | 🟡 위와 동일 |
| 다음 초점 + 개인화 노트 | 카테고리별 학습 통계 | (ML이 자체 SQLite로 보관) | ✅ BE 불필요 |

## BE에 요청할 것 (정리)

**1. `entries`에 컬럼 추가 (핵심)**
```sql
ALTER TABLE entries ADD COLUMN context_json JSONB;
-- 안에 { "sleep_hours": 7.5, "social_today": "갈등", "exercise_today": 1.0, "self_condition": 4 }
-- ML /entries 응답의 context_used 를 그대로 저장하면 됩니다.
```
와이어프레임에 이미 "수면 시간 7h 30m / 운동 시간 1h / 컨디션 4단계 / 사교 활동 중" 입력 UI가 있으니, **그 입력값을 `context_json`에 담아 저장**해주시면 됩니다. (입력 UI는 이미 설계됨 — 저장만 연결)

**2. 그날의 라벨 결과 저장 확인**
ML `/entries` 응답의 `label_result`(13차원 점수 + `evidence_span`)를 `entries`에 저장하고 있는지 확인 부탁드립니다. 없으면:
```sql
ALTER TABLE entries ADD COLUMN label_result_json JSONB;  -- ML 응답의 label_result 그대로
```
이게 있어야 "컨디션 낮은 날 미래예측↑", "힘든 날 '망할 것 같아' 표현" 같은 경향이 계산됩니다.

**3. 주간 호출 시 7일치 전달**
주간 리포트는 BE가 그 주 `entries` 7일치를 모아 `POST /weekly`로 ML에 넘기면 계산됩니다. (ML은 stateless — DB 직접 접근 안 함)
```
POST /weekly  body: { user_id, week, entries: [ {created_at, self_condition, context_json, label_result_json}, ... ] }
```

## 정리
- ERD에 **확실히 추가 필요**: `entries.context_json` (수면·사교·운동·컨디션 묶음)
- **확인 필요**: 그날 라벨(`label_result_json`)을 저장하고 있는지
- **불필요**: 개인화 학습 통계는 ML이 자체 보관하므로 ERD 변경 없음
- 입력 UI는 이미 와이어프레임에 있으므로, **저장 연결만** 하면 주간 맞춤형이 다 동작합니다.
