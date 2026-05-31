# FE 팀원에게 보낼 메시지 (그대로 복사 → 전송)

---

안녕하세요! ML 정리되어서 프론트 반영하면 좋은 부분 우선순위대로 공유드려요 🙂 (3주 일정 고려)

**1. 추천 카드 = 2종류만 분기**
정책이 "항상 드릴 추천"이라 `drill`·`crisis_card` 두 가지만 보시면 됩니다. (`positive_card`/`ask_user`/`skip` 안 옴)
- 컨디션 아주 좋은 날도 `drill` + `tone:"positive"` (밝은 톤 변형 1개만).

**2. 드릴 카드의 `why` — 우리 차별 포인트 (evidence 강화됨)**
```jsonc
"why": {
  "text": "어젯밤 잠이 부족해서, '미래예측' 생각이 자주 보여서, 방금 쓰신 '망할 것 같아' 표현도 함께 보여서 골랐어요.",
  "expected_benefit": "꼬리를 무는 생각에서 한 걸음 떨어져 보는 데 도움이 돼요.",   // 효용
  "mechanism": "인지행동치료(CBT) 생각 재구성 기법에 기반해요.",              // 근거(신뢰감)
  "factors": [
    {"kind":"context","label":"수면 부족","detail":"4시간"},
    {"kind":"pattern","label":"미래예측","friendly":"미리 결론 내리기","detail":"자주","score_raw":0.75},
    {"kind":"evidence","quote":"망할 것 같아","why_evidence":"'미리 결론 내리기'의 단서가 보이는 말이라서"}
  ]
}
```
화면 권장: ① `text`(왜) ② `expected_benefit`(도움) ③ `mechanism`(작게, 근거).
- **evidence factor**: 와이어프레임처럼 사용자 원문을 그대로 인용(`quote`)하고, 옆/아래에 `why_evidence`(왜 이게 근거인지)를 작게. → "내 말을 읽고 골랐구나" 체감 = GPT 단독 대비 차별점.
- 패턴 칩: `friendly`("미리 결론 내리기")가 있으니 임상용어 대신 이걸 노출 권장. (둘 다 응답에 있음 — 표기는 나중에 골라도 됨) `score_raw`(0.75)는 화면에 X, `detail`("자주") 사용.

**3. 드릴 색상 — 프론트가 표로 관리 (요청 반영)**
카테고리 기반 6색이에요. ML은 `drill.id`/`drill.category`만 보냄. 첨부 `drill_color_table.json`(id→색) + `drill_color_spec.md`(6색표). 가장 단순: `category → hex` 6줄 맵.

**4. 주간 리포트 — 경향(tendencies) 중심 + 상태·다음초점은 약하게**
`GET /weekly`·`/monthly`의 `weekly_coaching`:
- **메인**: "이런 경향이 보였어요" = `tendencies[]` (각 `text` + 신뢰도 `strength`: 뚜렷한 관찰/관찰/약한 관찰).
- 상태(`state.label` "소진기")는 **배지보다 `summary` 한 줄 위주**로 부드럽게. 다음 초점(`next_week_focus`)은 **제안 톤**으로 약하게. (지시·진단 느낌 줄이기)
- `insufficient:true`(4일 미만)면 "며칠 더 모이면 보여드릴게요" 빈 상태 1종.
- 와이어프레임의 "오늘의 상태(수면/운동/컨디션/사교)" 입력값은 BE가 저장 → 이게 주간 경향의 재료예요.

**5. 감정 오각형 / 캘린더 / 인증**
- emotion_pentagon 유지, **주 전반/후반 비교 차트 생략 OK**.
- 캘린더 색 = `drill_calendar_color` 토큰 → hex 매핑(`calendar_color_spec.md`). (드릴 색과 별개)
- 인증 **JWT 그대로**, Google OAuth는 MVP 이후.

급한 건 1·2·4예요. `/docs`에서 실제 응답 확인돼요. 감사합니다!
