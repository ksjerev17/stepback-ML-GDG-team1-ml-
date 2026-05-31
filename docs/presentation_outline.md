# 발표 outline — 10슬라이드

> 3분 시연 포함 총 12~15분 발표. CLAUDE.md §17.3 시연 시나리오 연동.

---

## Slide 1 — 표지
- 제목: **Step Back — 한 줄로 시작하는 자기 발견**
- 부제: 한국 학부생을 위한 감정·행동 기반 드릴 추천
- 팀: 5명 (P1~P5)
- 7주 프로젝트 W7

## Slide 2 — 우리가 풀려는 문제
- 한국 학부생 정신건강: 검색 → 자기 진단 → 무한 라벨링 → 행동 변화 X
- 기존 도구의 함정: "당신은 우울증" 단정 / 인지 왜곡만 / 평가는 노출되어 Hawthorne 효과
- 우리의 차별점: **자기 발견 + 행동 중심 + 사용자 검열 불신뢰**

## Slide 3 — 본질 4가지 (한 슬라이드 4박스)
1. 자기 발견 > 진단
2. 상관 관찰 > 인과 단정
3. 행동 중심 > 인지 중심 (카탈로그 48% 행동)
4. 사용자 검열 불신뢰 → 4 누적 메커니즘

## Slide 4 — 라벨링 차원 (taxonomy v7)
- 인지 6 (Beck/Ellis): 미래예측·독심술·자기비난·이분법·당위진술·과잉일반화
- 행동 2 (Martell BA): 회피미루기·동기저하
- 감정 5 (PANAS-X): 불안·우울·분노·죄책·중립
- 부가: intensity / confidence / evidence_span / crisis_detected
- **W1 실측 합치율 86%**

## Slide 5 — 드릴 카탈로그 v6.3 (77개, 학술 정본)
- cognitive_restructuring 22 (Beck CT / Burns / Ellis REBT)
- behavioral_activation 22 (Martell / Hayes / Lewinsohn)
- habit_design 15 (Allen GTD / Gollwitzer / Fogg / Clear)
- grounding 9 (Najavits / DBT / MBSR)
- self_compassion 5 (Neff / Gilbert)
- sleep_circadian 4 (Walker / Huberman)
- **행동·습관 48%** — 실행 중심

## Slide 6 — 라우팅 5단계 + 약신호 분기
1. 위기 → crisis_card
2. 인지 ≥ 0.4 → cognitive_restructuring
3. 회피 ≥ 0.5 → behavioral_activation (S005: 인지+행동 동시 시 행동 우선)
4. 동기저하 ≥ 0.5 → habit_design
5. 약신호 → 컨디션·수면·사교로 보조 드릴 / positive_card / ask_user

## Slide 7 — 시연 (3분)
- 정상 / 행동 / 위기 / 약신호 평온 / 약신호 보조
- 시연 시 위기 입력은 워터마크 "시연 예제" 명시

## Slide 8 — 데이터 측정 4 메커니즘 (비공개)
- 드릴 평가 누적 (사용자 비공개 — Hawthorne 회피)
- 컨디션 추세 (주간 평균)
- 주기 자가평가 (4지선다 + "모르겠다")
- 행동 실천 추적 (시작·완료)

## Slide 9 — 윤리·안전
- 베타 동의서 (익명·90일 자동 삭제·진단 아님)
- 위기 응답 프로토콜 (변형 절대 금지)
- 외부 통신 0 (Gemini 1곳만, PII 마스킹 후)
- 데이터 회수 30일 이내

## Slide 10 — 학술적 한계 + 향후
- LLM 라벨링은 진단 아님 (단서 추출)
- 50 문장은 통계적 신뢰성 부족
- 베타 12명 ≠ 임상 시험
- 향후: 카탈로그 확장 / 합치율 200+ 재측정 / IRB 신청

## Q&A
- ML 파트 (라벨링·라우팅·후처리) — P1
- 백엔드 (API·DB) — P2
- 프론트엔드 — P3
- 캘린더·시각화 — P4
- 콘텐츠·UX — P5
