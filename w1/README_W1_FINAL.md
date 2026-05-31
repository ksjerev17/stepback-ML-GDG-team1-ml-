# Step Back W1 최종 — 분류 체계 검증 + 시범 라벨링 (v9.4.3)

W1 (분류 체계 v7 + 드릴 카탈로그 v6.3 + 50문장 시범 라벨링)의 모든 산출물.
**v9.4.3 기획서 기준 W2 진입 직전 상태**.

---

## 1. 한 줄 정리

- **분류 체계 v7**: LLM 라벨링 = 6 인지 + 2 행동 + 5 감정 (13항목)
- **드릴 카탈로그 v6.3**: 77개. 행동·습관 강화 (실행 중심 48%)
- **시드 50문장**: 한국 학부생 시나리오. 패턴별 균등 분포 + 위기 1개
- **5명 분담**: 각 멤버 10문장씩
- **W2 진입 판정**: 라벨링 결과 분석 후 결정

---

## 2. 폴더 구조

```
w1_v943/
├── 분류 체계 + 카탈로그
│   ├── taxonomy_v7.json              # 분류 체계 (16KB, 8필드 풀 정의)
│   ├── drills_seed_v6_3.json          # 드릴 77개 (82KB, 풀 학술 메타)
│   └── seed_sentences_50_v3.json      # 시드 50문장 + 분포 설계
│
├── 라벨링 코드 (Python)
│   ├── run_labeling.py                # 메인 (분할 모드 자동 감지)
│   ├── run_labeling.bat               # Windows 더블클릭
│   ├── model_router.py                # Gemini tier 분기
│   ├── label_postprocess.py           # confidence 길이 + evidence_span fuzzy
│   ├── clarification_loop.py          # 2차 객관식 정밀화
│   ├── apply_postprocess.py           # 후처리 일괄 적용
│   ├── clean_failed.py                # FAILED만 제거
│   └── merge_results.py               # 5명 결과 통합
│
├── 프롬프트 + 가이드
│   ├── labeling_prompt_v3.md          # Gemini 시스템 프롬프트
│   ├── README_W1_FINAL.md             # 이 문서 (P1용 마스터)
│   └── README_MEMBER.md               # 각 멤버용 실행 가이드
│
├── 5명 분담 패키지
│   ├── member1_package.zip ~ member5_package.zip
│   ├── build_member_packages.py
│   ├── split_for_5members.py
│   └── split_for_5members/
│       └── seed_split_member1.json ~ member5.json
│
└── 환경
    ├── .env.example
    └── requirements.txt
```

---

## 3. 분류 체계 (taxonomy_v7.json)

LLM이 라벨링하는 13개 차원:

### 인지 패턴 6개 (Beck CBT + Burns + Ellis REBT)
- 미래예측 — 근거 없이 부정적 미래를 단정
- 독심술 — 타인 마음을 단정 추측
- 자기비난 — 외부 사건 책임을 본인에게 과도 귀속
- 이분법 — 회색 없이 흑백 판단
- 당위진술 — '반드시 ~해야 한다' 절대 명제
- 과잉일반화 — 한 사건으로 전체 단정

### 행동 상태 2개 (Hayes ACT + Martell BA)
- 회피미루기 — 해야 할 일을 회피 (대상 있음)
- 동기저하 — 의욕·에너지 떨어짐 (대상 불특정)

### 감정 5개 (PANAS-X)
- 불안, 우울, 분노, 죄책, 중립 (안전판)

### LLM이 라벨링하지 않는 차원
- **맥락 4개**: 자기 상태(self_condition) · 수면 · 사교 · 운동 — 사용자 슬라이더 입력
- **성장**: 드릴 평가 누적 + 컨디션 추세 + 자가 진단 + 행동 실천 (4 메커니즘)

---

## 4. 드릴 카탈로그 v6.3 (drills_seed_v6_3.json)

77개. 카테고리별 분포 + 행동·습관 강화:

| 카테고리 | 개수 | 비율 | 주요 학술 근거 |
|---|---|---|---|
| cognitive_restructuring | 22 | 29% | Beck CT, Burns 인지 왜곡, Ellis REBT |
| behavioral_activation | 22 | 29% | Martell BA, Hayes ACT, Lewinsohn |
| habit_design | 15 | 19% | Fogg Tiny Habits, Gollwitzer II, Clear |
| grounding | 9 | 12% | Najavits, Kabat-Zinn MBSR, DBT TIP |
| self_compassion | 5 | 6% | Neff, Gilbert |
| sleep_circadian | 4 | 5% | Walker, Huberman, Chang |

**행동 + 습관 = 48%** (실행 중심).

---

## 5. 시드 50문장 (seed_sentences_50_v3.json)

5명에게 10문장씩 분담:

| 멤버 | 문장 ID | 주요 패턴·신호 |
|---|---|---|
| member1 | S001~S010 | 인지 패턴 6 + 행동 신호 일부 |
| member2 | S011~S020 | 인지 + 감정 혼합 |
| member3 | S021~S030 | 행동 신호 중심 |
| member4 | S031~S040 | 약신호 + 맥락 다양 |
| member5 | S041~S050 | 강한 감정 + 위기 1개 (S050) |

상세 분할은 `split_for_5members/seed_split_member{1~5}.json` 참고.

---

## 6. 라벨링 워크플로우

### 6.1 5명에게 zip 배포
```
member1_package.zip → 멤버1
member2_package.zip → 멤버2
...
member5_package.zip → 멤버5
```

각 zip 약 40KB. 카카오톡·디스코드·메일 어디로든 전달.

### 6.2 각 멤버 실행
멤버는 `README_MEMBER.md`만 따라 하면 됨. P1이 별도 지원 X 가정.

### 6.3 5명 결과 회신
각 멤버가 다음 2개 파일을 P1에게 회신:
- `labeling_results_member{N}.json`
- `labeling_audit_member{N}.md`

### 6.4 P1 통합
받은 5개 결과를 한 폴더에 모은 후:

```bash
python3 merge_results.py
```

→ `labeling_results_v1.json` + `labeling_audit_v1.md` 자동 생성.

### 6.5 후처리 + 합치율 분석

```bash
# 후처리 (confidence 보정, evidence_span fuzzy)
python3 apply_postprocess.py

# FAILED 케이스 제거
python3 clean_failed.py
```

목표: **정상 동작률 ≥ 80%**, 위기 신호 (S050) 정상 감지.
지난 1차 결과: **86% 합치율 / 4% false positive / 50문장 통합 완료**.

---

## 7. v9.4.3 변경사항 (W2 진입 시 적용)

W1 라벨링 자체는 변경 없음 (taxonomy v7 / catalog v6.3 / 50문장 그대로).
그러나 W2부터 다음이 반영됨 — 라벨링과 추천 라우팅에 영향 있음:

### 입력 정책 (v9.5)
- 일일 입력: **하루 1회** (v9.4.x의 3회 정책 폐기 — 깊은 자기 발견 도구로 전환)
- 텍스트: 1~500자 (자유 일기형)
- quota: 분/시/일 모두 1회 — 한 번에 깊이 적도록 유도

### 맥락 변수 (4개 모두 필수)
- `self_condition` (1~5) — 매 입력마다, 기본값 3
- `sleep_hours` (0~12h) — 하루 첫 입력만, 기본값 7h, 같은 날 2·3번째는 자동 재사용
- `social_today` (좋음/보통/갈등) — 첫 입력만, 기본값 보통, 자동 재사용
- `exercise_today` (0~12h) — 첫 입력만, 기본값 0h, 자동 재사용

### 추천 라우팅 (Step 5 약신호 분기 신규)
- 모든 신호 < 0.3 + 컨디션 ≥ 3 → **positive_card** (드릴 X, 양호 안내)
- 모든 신호 < 0.3 + 컨디션 < 3 → **ask_user** (\"드릴 받을래요? 기록만 할래요?\")
- 사용자가 \"받기\" → 상태값 기반 보조 드릴 + 이유 명시
- \"기록만\" → skip

### 드릴 카드
- **3 버튼** (4 → 3): [시작하기] [아닌 것 같아요] [지금은 괜찮아요]
- \"다른 드릴\" 버튼 제거

### 캘린더 색 (dominant 차원 8색)
- 🟢 평온 (약신호 + 컨디션 ≥ 3)
- 🔘 무거움 (약신호 + 컨디션 ≤ 2)
- 🔴 분노 / 🟡 불안 / 🔵 우울 / 🟣 죄책 (감정 dominant)
- 🟠 인지 dominant / 🟤 행동 dominant

### 알림
- 푸시 X
- 메일 + 인앱 상단 팝업 (주간 리포트 — 매주 일요일 8시 KST)

### 인증
- Google OAuth 우선
- 비밀번호 찾기 기능 제거

### ERD (5 테이블)
- `users` (`confirmed_at` 추가 — 동의문 서약일)
- `entries` (feedbacks 흡수, `feedback_at` 추가)
- `reports` (주간 리포트 발송 상태)
- `insights` (`report_id` FK → reports, 토글 UI 정렬)
- `baselines` (W5 이후, AI 학습 전용, 사용자 노출 X)

상세: `StepBack_v9.4.3_명세서.docx`.

---

## 8. W2 진입 판정 기준

W1 완료 → W2 진입 가능 여부:

- [ ] 정상 동작률 ≥ 80%
- [ ] 위기 신호 (S050) 정상 감지
- [ ] 인지 패턴 6개 모두 한 번 이상 검출
- [ ] 행동 신호 2개 모두 한 번 이상 검출
- [ ] 5명 멤버 모두 라벨링 완료 회신
- [ ] FAILED 케이스 0 (quota·parse error 모두 해결)

모두 통과하면 W2로 — **ML 서비스 골격 + FastAPI + Spring Boot 연동**.

---

## 9. P1 운영 체크리스트

### 배포 전
- [ ] 5개 zip 파일 무결성 확인 (각 ~40KB)
- [ ] 멤버 5명에게 zip + README_MEMBER 메시지 전달
- [ ] Gemini API key 발급 가이드 공유

### 회신 받은 후
- [ ] 5명 결과 파일 모두 도착 확인
- [ ] `merge_results.py` 실행 → 통합 JSON 생성
- [ ] `apply_postprocess.py` 실행 → confidence 보정
- [ ] `clean_failed.py` 실행 → FAILED 제거
- [ ] 합치율 분석 후 W2 진입 판정

### 문제 발생 시
- 멤버 quota 0 → 24시간 후 재실행 안내
- LLM이 위기 신호 인식 못 함 → `labeling_prompt_v3.md` 수정 필요
- 합치율 < 80% → seed 정정 vs 프롬프트 보정 P1 결정

---

**문서 버전**: W1 v9.4.3 · 2026-05-21
**다음 단계**: W2 ML 서비스 골격 (FastAPI + PII 마스킹 + Quota + ModelRouter)
