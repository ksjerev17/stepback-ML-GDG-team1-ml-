# Step Back — 제출용 최종 보고서 (PII 제거판)

> CLAUDE.md §8.W7 DoD #6. P1 작성, 학교 제출용.
> 사용자 이름·연락처·학번 일체 제외. user_id는 hash로만 언급.

## 요약

Step Back은 한국 학부생을 위한 감정·행동 기반 드릴 추천 도구다. 사용자가 한 줄 한국어 텍스트를 작성하면 대형 언어 모델이 인지 왜곡 6항목, 행동 신호 2항목, 감정 5항목을 0~1 점수로 라벨링하고, 학술 출처가 검증된 드릴 77개 중 한 개를 5단계 라우팅으로 추천한다. 7주 프로젝트로 학부 5인 팀이 개발했으며, ML 파트는 본 보고서 작성자가 담당했다.

## 1. 문제 정의

한국 학부생의 정신 건강 관리는 자기 진단 단계에서 멈추는 경우가 많다. 검색·체크리스트·라벨링 단계까지 도달해도 실제 행동 변화로 이어지는 경로가 약하다. Step Back은 인지 왜곡만 보지 않고 회피·무기력 같은 행동 신호를 1급 라벨링 차원으로 다루며, 학술 기반 드릴을 짧은 호흡(1~5분)으로 제공한다.

## 2. 라벨링 차원 (taxonomy v7)

- 인지 6 (Beck 1976; J.Beck 2020; Ellis 1962 REBT): 미래예측, 독심술, 자기비난, 이분법, 당위진술, 과잉일반화
- 행동 2 (Martell, Dimidjian & Herman-Dunn 2010): 회피미루기, 동기저하
- 감정 5 (PANAS-X; Tangney 2002): 불안, 우울, 분노, 죄책, 중립

부가 필드: intensity, confidence, evidence_span, crisis_detected.

## 3. 후처리·정밀화

- **길이 기반 confidence 보정**: 15자 미만 최대 0.40, 15~29자 최대 0.55, 80자 초과 +0.05 (상한 0.95).
- **evidence_span fuzzy 매칭**: ratio ≥ 0.7 시 원문 substring으로 보정.
- **객관식 정밀화**: confidence < 0.6 또는 top-1·top-2 차이 < 0.15일 때 2차 호출로 두 패턴 중 더 강한 신호 1개 선택.

## 4. 드릴 카탈로그 v6.3 (77개)

| 카테고리 | 개수 | 학술 근거 |
|---|---|---|
| cognitive_restructuring | 22 | Beck CT / Burns / Ellis REBT |
| behavioral_activation | 22 | Martell BA / Hayes ACT / Lewinsohn |
| habit_design | 15 | Allen GTD / Gollwitzer / Fogg / Clear |
| grounding | 9 | Najavits / DBT TIP / Kabat-Zinn MBSR |
| self_compassion | 5 | Neff / Gilbert |
| sleep_circadian | 4 | Walker / Huberman / Chang |

행동·습관 비중 48%는 의도된 설계: 회피·무기력이 풀려야 인지 작업이 작동한다는 Martell et al. (2010) 행동 활성화 연구를 반영.

## 5. 라우팅 5단계

```
Step 1. crisis_detected → crisis_card (1393/1388/1577-0199). 일반 드릴 차단.
Step 2. max(patterns) ≥ 0.4 AND max(behaviors) < 0.5 → cognitive_restructuring
Step 3. behaviors[회피미루기] ≥ 0.5 → behavioral_activation
Step 4. behaviors[동기저하] ≥ 0.5 → habit_design
Step 5. 모든 신호 < 0.3:
        - self_condition ≤ 2 → grounding
        - sleep_hours < 5 → sleep_circadian
        - social = 갈등 → self_compassion
        - self_condition ≥ 3 → positive_card (드릴 X)
        - 그 외 → ask_user
Step 6. fallback: 0.35×인지 + 0.40×행동 + 0.25×맥락
```

핵심 설계: 인지 신호와 회피 신호가 동시에 강할 때 회피 라우팅이 인지보다 우선. 회피가 풀려야 인지 재구성 드릴이 실제 실행된다.

## 6. 데이터 측정 4 메커니즘 (사용자 비공개)

성장은 LLM이 추론하지 않는다. 점수를 사용자에게 노출하지 않는다 (Hawthorne 효과 회피).

1. **드릴 평가 누적**: helpful / meh / unhelpful. 당일 수정 가능, 다음날 거부. 학습 데이터로만.
2. **컨디션 추세**: 주간 평균 자기 컨디션 1~5 시계열.
3. **주기 자가평가**: 주간 리포트의 4지선다 ("모르겠다" 포함). 메타인지 격차를 측정.
4. **행동 실천 추적**: 추천 → 시작 → 완료 비율. 측정 정직 (했거나 안 했거나).

## 7. 카피·표현 정책

진단·치료 단어, "X 유형입니다" 단정, 인과 단정, 압박·응원 표현, 자가진단 퀴즈 정답 판정 표현을 모두 금지. 자동 lint(`scripts/lint_copy.py`)로 PR 차단.

## 8. 보안·프라이버시

- 사용자 텍스트는 BE DB에만 저장. ML은 hash + 길이 + 라벨 요약만 audit log.
- LLM 호출 직전 PII 마스킹 (URL, 이메일, 전화, 학번, 호칭+이름, 일반 성씨+이름).
- 외부 통신은 Gemini API 한 곳만. 모든 다른 외부 호출 차단.
- 90일 자동 삭제. 사용자 요청 시 30일 이내 회수.

## 9. W1 라벨링 합치율

50문장 / 5명 멤버 분담 / 86% 합치율 (PASSED 34 + WARNING_MISMATCH 14). 후처리·정밀화 적용 전후 비교는 `docs/labeling_analysis.md`에서 자동 분석.

## 10. 학술적 한계 (솔직 공개)

| 한계 | 의미 |
|---|---|
| LLM 라벨링 ≠ 진단 | 단서 추출일 뿐 임상 판정 아님. |
| 50문장 표본 작음 | 200+ 문장 재검증 필요. |
| 베타 8~12명 ≠ 임상 시험 | IRB 없는 학부 운영. 결과 일반화 X. |
| 모델 변동성 | Gemini 모델 버전·tier 별 신호 강도 차이가 라벨링 일관성에 영향. |
| Mock 폴백 측정 미실시 | API 키 미발급 기간의 어휘 매칭 결과는 실 LLM과 다를 수 있음. |

## 11. 향후 과제

1. 본격 라벨링 — 200+ 문장으로 합치율 재측정.
2. 드릴 카탈로그 확장 — 100~150개 (P5 검수).
3. 베타 8~12명 2주 운영 — 컨디션 추세 + 실천율 + 자가평가 격차 데이터 수집.
4. 다국어 지원 — taxonomy 재작성.
5. 임상 협력 IRB 신청 후 본격 평가.

---

**제출일**: 2026-05-22 · **버전**: W7 final v1.0 (PII 제거판)
