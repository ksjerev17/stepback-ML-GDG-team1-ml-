# 캘린더 색 매핑 (P4) — v9.5

> ML이 두 종류 키 반환 → FE가 색 매핑.
> 1) `calendar_dominant` (9 enum) — 라벨링 기반 캘린더 점 색
> 2) `drill_category` (6 enum) — 추천 드릴 기반 캘린더 화면 카테고리 색

## 1. calendar_dominant (월간 캘린더 점)

ML의 `LabelResult.calendar_dominant` 자동 산출 — FE가 색 매핑:

| dominant 키 | 색 | 조건 |
|---|---|---|
| `crisis` | 회색 (어두움) | crisis_detected=true |
| `cognitive_dominant` | 주황 | max(patterns) ≥ 0.5 AND max(behaviors) < 0.5 |
| `behavior_dominant` | 갈색 | max(behaviors) ≥ 0.5 |
| `emotion_anger` | 빨강 | 분노 ≥ 0.5 AND 다른 모든 차원 < 0.4 |
| `emotion_anxiety` | 노랑 | 불안 ≥ 0.5 AND 다른 모든 차원 < 0.4 |
| `emotion_depression` | 파랑 | 우울 ≥ 0.5 AND 다른 모든 차원 < 0.4 |
| `emotion_guilt` | 보라 | 죄책 ≥ 0.5 AND 다른 모든 차원 < 0.4 |
| `weak_signal_positive` | 초록 | 모든 신호 < 0.3 AND self_condition ≥ 3 |
| `weak_signal_low` | 회색 (옅음) | 모든 신호 < 0.3 AND self_condition < 3 |

동률 시 우선: `crisis > emotion > behavior > cognitive > weak_signal`.

## 2. drill_category → 캘린더 색 (v9.5 신규)

`/api/entries` 응답의 `drill_calendar_color` (FE 매핑 키):

| drill_category | drill_calendar_color | 권장 hex (소프트 톤) |
|---|---|---|
| `cognitive_restructuring` (생각 전환) | `pink_soft` | `#FFE0EC` |
| `behavioral_activation` (산책) | `white_soft` | `#F8F8F8` |
| `habit_design` (긍정 확언) | `pink_warm` | `#FFB6C1` |
| `grounding` (마음 챙김) | `green_calm` | `#C8E6C9` |
| `self_compassion` (자기 자비) | `lavender` | `#E1BEE7` |
| `sleep_circadian` (수면 정돈) | `blue_night` | `#B3E5FC` |

`drill_category_label` 한국어:
- cognitive_restructuring → "생각 전환"
- behavioral_activation → "산책"
- habit_design → "긍정 확언"
- grounding → "마음 챙김"
- self_compassion → "자기 자비"
- sleep_circadian → "수면 정돈"

## 3. 시각화

### 월 캘린더 (v9.5 일 1회 정책)
- 일자별 1개 점 (옛 데이터 호환을 위해 slots list 유지하지만 일반적으로 길이 1)
- 점 색 = `calendar_dominant` 매핑 (위 1번)
- 클릭 시 일별 상세 모달 — 입력 텍스트 + 드릴 + 완료 여부 (✓ / —)
- **`helpful` 필드 절대 노출 X** (§9.1 사용자 비공개)

### 일별 상세 모달 (POST /daily 응답)
```json
{
  "entries": [{
    "text": "...",
    "self_condition": 3,
    "calendar_dominant": "emotion_anxiety",
    "drill_id": 1,
    "drill_title": "증거 2:2 적기",
    "drill_complete": true
  }]
}
```

## 4. 주간 리포트 분포

`/api/weekly` 응답:
- `calendar_distribution.distribution`: dominant 키별 카운트. 도넛/막대 차트 권장
- `emotion_pentagon.axes`: 5감정 평균 (radar chart — recharts `RadarChart`)
- `pattern_diff`: 이번주 vs 지난주 막대 + up/down/flat 화살표
- `condition_flow.points`: 월~일 7일 라인 차트
- `discoveries[].pattern_type` (있는 경우): `recovery` / `fatigue` / `early_load` / `late_load` — 별도 강조 카드

## 5. 월간 리포트 (v9.5 신규)

`/api/monthly` 응답:
- `condition_trend.weeks` — 1~5주차 평균 라인 차트
- `emotion_pentagon` — 30개 entries 평균
- `calendar_distribution` — 한 달 dominant 분포

## 6. 다크 모드 (선택)

9 dominant + 6 drill_category 모두 다크 모드 페어 색 정의 권장. FE 디자인 시스템 (Tailwind config 또는 디자인 토큰).
