# Step Back — 최종 보고서 (ML 파트, P1)

> 7주 프로젝트 W7 산출물. CLAUDE.md §16.4 학술적 한계 솔직 공개 포함.

## 1. 한 줄 정의

**한국 학부생이 한 줄 텍스트를 쓰면 LLM이 인지 6 + 행동 2 + 감정 5 차원을 라벨링하고, 학술 기반 드릴 1개를 추천하며, 누적 데이터로 메타인지 격차를 측정하는 자기 발견 도구.**

## 2. 본질 4가지

1. **자기 발견 > 진단**: 도구가 "당신은 X 유형" 단정 X. "이런 신호가 보여요" 질문형.
2. **상관 관찰 > 인과 단정**: "수면 ↓ 와 우울 ↑ 가 같이 나타남" — "수면 부족이라 우울" X.
3. **행동 중심 > 인지 중심**: 회피·동기저하 풀려야 인지 작업 작동. 카탈로그 48%가 행동·습관.
4. **사용자 검열 불신뢰**: 성장은 LLM이 판정 X. 4 누적 메커니즘 (드릴 평가 / 컨디션 추세 / 주기 자가평가 / 행동 실천).

## 3. 합치율 — W1 실측

- **86% 합치율** (PASSED 34 + WARNING_MISMATCH 14 / 50 문장)
- 라벨링 풀: 5명 멤버 분담 + P1 통합
- 데이터 정본: `w1/labeling_results_v1.json` (배치 필요), `w1/seed_sentences_50_v3.json` 50 문장
- 분석 자동화: `scripts/analyze_labeling.py` → `docs/labeling_analysis.md`

## 4. 라우팅 5단계

`app/core/recommender.py`:

1. **위기**: `crisis_detected=true` → crisis_card (1393/1388/1577-0199). 일반 드릴 절대 X.
2. **인지**: `max(patterns) ≥ 0.4 AND max(behaviors) < 0.5` → cognitive_restructuring.
3. **회피**: `behaviors[회피미루기] ≥ 0.5` → behavioral_activation. **인지보다 우선** (S005 회귀).
4. **동기저하**: `behaviors[동기저하] ≥ 0.5` → habit_design.
5. **약신호 분기** (모든 신호 < 0.3):
   - self_condition ≤ 2 → grounding
   - sleep_hours < 5 → sleep_circadian
   - social = 갈등 → self_compassion
   - self_condition ≥ 3 → positive_card
   - 그 외 → ask_user
6. **fallback**: 점수 공식 `0.35 × 인지 + 0.40 × 행동 + 0.25 × 맥락`.

## 5. 데이터 측정 4 메커니즘 (비공개)

성장은 LLM이 추론하지 않음. 사용자에게 점수 노출 X.

1. **드릴 평가 누적** — 👍 / 👌 / 👎. 당일 수정 가능. 사용자에게 비공개 (Hawthorne 회피).
2. **컨디션 추세** — 주간 평균 변화. 캘린더 dominant 색 분포.
3. **주기 자가평가** — 주간 리포트 4지선다 ("모르겠다" 포함). 메타인지 격차 측정.
4. **행동 실천 추적** — 추천 → 시작 → 완료. 인지보다 측정 정직 (했거나 안 했거나).

## 6. 카피 정책 (§2.3 절대 금지 표현)

- 진단·치료 표현 0
- "당신은 X 유형" 0
- 인과 단정 0
- 압박·응원 표현 0
- 자가진단 퀴즈 "맞췄어요/틀렸어요" 0

`scripts/lint_copy.py` 자동 검출 + pre-commit 차단.

## 7. 윤리·법·안전

- **베타 동의서**: 익명·90일 자동 삭제·진단 아님 명시·위기 시 1393 안내.
- **위기 응답 프로토콜** (`handoff/crisis_response_protocol.md`): LLM 응답 변형 절대 금지.
- **데이터 최소화**: 입력 텍스트는 BE DB만. ML은 hash + 길이 + 라벨 요약만 audit log.
- **외부 통신 0**: Gemini API 1곳 외 모든 외부 호출 차단. 학부 MVP는 로컬 우선.
- **데이터 회수**: 30일 이내 처리. user_id로 hash 조회 → 모든 로그·DB row 삭제.

## 8. 학술적 한계 (솔직 공개)

| 한계 | 의미 |
|---|---|
| LLM 라벨링 ≠ 진단 | 단서 추출일 뿐. 임상 판정 아님. |
| 50 문장 통계적 신뢰성 부족 | sample size 작음. 본격 평가 위해 200+ 필요. |
| 베타 12명 ≠ 임상 시험 | IRB 없는 학부 운영. 결과를 일반화 X. |
| ModelRouter 발견 | Gemini 모델별 신호 강도 차이 — 안정 모델 선택 후에도 변동성 남음. |
| Mock 폴백의 합치율 미측정 | 현재 API 키 미발급으로 Mock 어휘 매칭 사용. 실 Gemini 합치율과 직접 비교 필요. |
| 7주 후 베타 확장성 | 8~12명 한도 + 분 1 / 시 3 / 일 3 quota. 본격 운영 시 인프라 재설계 필요. |

## 9. 향후 과제

1. **API 키 발급 후 실 라벨링 합치율 재측정** — Mock 대비 정확도 향상폭 확인.
2. **드릴 카탈로그 확장** — 현재 77개 → P5 검수 후 100~150개. behavior 비중 50% 유지.
3. **베타 8~12명 2주 운영** — 컨디션 추세 + 실천율 + 자가평가 격차 데이터 수집.
4. **다국어 지원** — 현재 한국어 only. 영어/일본어 추가 시 taxonomy 재작성 필요.
5. **임상 협력 IRB 신청** — 본격 평가 단계.

## 10. 폴더 산출물

- `ml_service/` — FastAPI 서비스 (W2~W6)
- `w1/` — 라벨링 데이터·후처리·정밀화 (읽기 전용)
- `handoff/` — P2~P5 계약 (api_contract, error_codes, crisis_response_protocol, be/fe/calendar/content guide, changelog)
- `docs/` — w2~w7 완료 보고서, labeling_analysis, demo_script, final_report
- 테스트 89 PASS

## 11. 데이터 회수 절차 (사용자가 요청 시)

1. P1이 `python -X utf8 scripts/purge_old_data.py` 또는 user_id 인자 추가 버전 실행
2. user_id → SHA256 hash 계산
3. `logs/audit-*.jsonl`에서 hash 일치 row 삭제
4. `ml_service/data/feedback.db`의 feedback table에서 hash 일치 row DELETE
5. BE DB는 P2에게 user_id 전달 (별도 처리)
6. 30일 이내 사용자에게 메일 통보

---

**작성자**: P1 (학부생) · **작성일**: 2026-05-22
**문서 버전**: W7 final v1.0
