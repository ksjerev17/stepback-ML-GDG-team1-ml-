# FE 통합 가이드 (P3 — Next.js) v9.5

## 1. 호출 경로

FE → BE → ML. **FE → ML 직접 호출 X** (CORS·보안).
BE가 ML 응답을 그대로 전달하므로 FE는 ML 명세를 거의 그대로 받음.

## 2. 응답 type 분기 (v9.6 — 단순화)

> **v9.6 정책 변경 (팀 결정):** 항상 드릴을 추천한다. `ask_user`·`positive_card`·`skip`는 정상 흐름에서 더 이상 반환되지 않음. **FE는 `drill`과 `crisis_card` 두 가지만 분기하면 됨.**

`/api/entries` 또는 `/api/recommend` 응답 `type` 별 UI:

| type | UI |
|---|---|
| `drill` | 카드: copy.line1/2/3 + **why.text("왜 이 드릴")** + [시작하기] [아닌 것 같아요] + 학술 출처. `tone:"positive"`면 축하/유지 톤으로 표시(아래 4 참고) |
| `crisis_card` | 위기 카드: user_message + 3 전화번호 (1393/1388/1577-0199) + [전화 걸기] OS 다이얼러 |
| ~~`positive_card`~~ | (폐지) 안정적인 날도 `drill` + `tone:"positive"`로 옴 |
| ~~`ask_user`~~ | (폐지) 경계선·약신호도 바로 `drill` |
| ~~`skip`~~ | (폐지) |

### "왜 이 드릴인지" 카드 (v9.6 신규 — 차별점)
`drill` 응답에 `why` 객체가 옴:
```jsonc
"why": {
  "text": "어젯밤 잠이 부족해서, '미래예측' 생각이 자주 보여서 이 드릴을 골랐어요.",
  "factors": [
    {"kind":"context","label":"수면 부족","detail":"4시간"},
    {"kind":"pattern","label":"미래예측","detail":"0.70"},
    {"kind":"evidence","label":"망할 것 같아"}
  ],
  "tone": "neutral"   // 또는 "positive"
}
```
- `why.text`를 드릴 카드에 한 줄로 노출 → "이 앱은 내 맥락을 보고 골랐구나" 체감(설명가능 AI = GPT 단독 대비 차별점).
- `factors[]`는 칩/아이콘으로 표시하면 더 풍부(선택). `kind`로 아이콘 매핑(context=🌙/😴, pattern=💭, behavior=🧩, emotion=💗, evidence="…").

### tone="positive" (안정적인 날)
- `type`은 여전히 `drill`이지만 `tone:"positive"`. copy/why가 축하·유지 톤("오늘은 신호가 잔잔한 하루네요…").
- 별도 카드 컴포넌트 필요 없음 — 드릴 카드에 살짝 다른 색/문구만.

### 드릴 색·아이콘
`drill.id`(정수) + `drill.category` + (entries 응답의) `drill_calendar_color`로 FE가 색/아이콘 매핑. id가 항상 오므로 드릴별 아이콘 지정 가능.

## 3. (폐지) ask-first 흐름

> v9.6에서 always-drill로 전환되어 `ask_user`/`/recommend/after_ask` 흐름은 **FE에서 더 이상 호출하지 않음.** (엔드포인트는 하위호환용으로 서버에 남아있음.)

## 4. evidence_span 강조

`copy.line1`에 `'..'`로 따옴표된 substring이 사용자 원문 인용. 원문 입력란에도 동일 부분 굵게 표시.

## 5. 카피 변경 금지

`copy.line1/line2/line3`는 ML 응답값을 그대로 사용. FE에서 문구 추가·변형 X. P5 윤문은 ML 측에서.

## 6. 위기 카드 — 변형 절대 금지

`crisis_resources`의 전화번호는 그대로. 카피 ("힘내세요" 등 추가 X). 일반 드릴 분기·다른 화면 이동 0. §16.2.

## 7. 주간 리포트 (v9.5)

`GET /api/weekly?user_id=&week=YYYY-Www`:
- **5블록** — overview / dominant_pattern / drill_action / self_check_quiz / calendar_distribution
- **시각화 3종** — `condition_flow` (7일 라인) / `pattern_diff` (이번주 vs 지난주 막대 + up/down/flat) / `emotion_pentagon` (5감정 radar)
- **발견 카드** — `discoveries[]` 4 알고리즘 (자주 보인 표현 / 맥락-패턴 상관 / 효과적 드릴 / 주간 회복 패턴)
- **baseline 비교** — `baseline_card.top_increase.card`에 "평소보다 X 표현이 N%p 더 보였어요"
- Quiz: `options` 4개 그대로. `correct_value`는 응답에 **없음** (보안 — server cache only). `PATCH /api/weekly/quiz` 호출 후 응답에서 받음.

### 7.1 Emotion Pentagon (5각형 radar chart)
- `axes`는 항상 5개 — 불안 / 우울 / 분노 / 죄책 / 중립 (순서 고정)
- 각 `value`는 0~1 (주차 7 entries 평균 — v9.5 일 1회 정책)
- recharts `RadarChart` 또는 d3 radar
- dominant 축 별도 강조 (큰 점)

### 7.2 Weekly Recovery 카드 (v9.5)
- `discoveries[]`에서 `pattern_type` 필드가 있는 카드 별도 색·아이콘
- 4 종류: `recovery` (주 후반 회복 ↑) / `fatigue` (주 후반 소진 ↓) / `early_load` (주 전반 무거움) / `late_load` (주 후반 무거움)
- 일 1회 입력 정책의 가치를 사용자에게 직접 보여주는 핵심 UI
- 이전 v9.4.x의 `morning_load` / `evening_load`는 폐기 (옛 데이터는 무시)

## 8. 월간 리포트 (v9.5 신규)

`GET /api/monthly?user_id=&month=YYYY-MM`:
- **6 블록** — overview / dominant_pattern / calendar_distribution / emotion_pentagon / condition_trend (4~5주차) / drill_action
- 진입 메뉴: 주간 리포트의 [월간 보기] 또는 별도 탭

```typescript
type MonthlyReport = {
  month: string;
  user_id: string;
  overview: { recorded_days: number; total_entries: number; avg_self_condition: number };
  dominant_pattern: { dominant_key: string; ratio_percent: number; occurrences: number; total_strong: number };
  calendar_distribution: { distribution: Record<string, number> };
  emotion_pentagon: { axes: {label: string; value: number}[]; dominant: string; entries_used: number };
  condition_trend: { weeks: { week_in_month: number; avg_condition: number | null; count: number }[] };
  drill_action: { recommended_count: number; practiced_count: number; practice_rate: number };
};
```

## 9. 나의 발견 (v9.5 신규)

주간 리포트 Step 3에서 사용자가 직접 발견을 입력 → `POST /api/insights/user_discovery`:

```typescript
await fetch("/api/insights/user_discovery", {
  method: "POST",
  body: JSON.stringify({
    user_id: userId,
    discoveries: ["잠을 충분히 잔 날은 마음이 가벼워요", "감사한 일 한 가지 적기가 도움돼요"]
  }),
});
```

다음 추천 시 ML이 자동 매칭 → 같은 카테고리 드릴 affinity 가산. FE는 추가 처리 X.

조회:
```http
GET /api/insights/user_discovery?user_id=&limit=5
```

## 10. 인증 (v9.6 — 팀 결정)

- **JWT 토큰 방식 그대로 사용** (이미 구현됨). AccessToken을 별도 쿠키/NextAuth로 바꾸지 않음.
- **Google OAuth는 MVP 이후** 시간 남으면 추가 (NextAuth Google provider). 지금은 이메일/비번 + JWT로 진행.
- ML 영역과 무관 (ML은 user_id 문자열만 받음).

## 11. 캘린더 색

`/api/entries` 응답의 `drill_calendar_color` 또는 `/recommend` 응답의 `drill.category` → FE 색 매핑 (P4 영역 — `calendar_color_spec.md`).

6 카테고리 → 색 키:
- `cognitive_restructuring` → `pink_soft`
- `behavioral_activation` → `white_soft`
- `habit_design` → `pink_warm`
- `grounding` → `green_calm`
- `self_compassion` → `lavender`
- `sleep_circadian` → `blue_night`

월간 캘린더는 `calendar_dominant` 9 enum (P4 영역).

## 12. 입력 정책 (v9.5)

- **하루 1회 입력** (이전 3회 폐기)
- 텍스트 1~200자
- self_condition 매번 (1~5)
- sleep/social/exercise는 일 첫 입력만 (BE가 캐시 — FE는 첫 입력 화면에서만 표시)
- 같은 날 두 번째 시도 시 BE가 409 → FE는 "오늘 이미 기록하셨어요. 덮어쓸까요?" 안내

## 13. 에러 처리

| 상태 | FE 동작 |
|---|---|
| 400 INVALID_INPUT | 사용자에게 안내 |
| 422 VALIDATION_ERROR | 입력 검증 안내 ("텍스트 1~200자") |
| 429 QUOTA_EXCEEDED | "오늘 1번 다 쓰셨어요" + retry_after 카운트다운 |
| 503 ML_UNAVAILABLE | "지금 라벨링이 어려워요" 카드 |
| 500 INTERNAL_ERROR | 일반 에러 카드 + request_id (디버깅용) |
