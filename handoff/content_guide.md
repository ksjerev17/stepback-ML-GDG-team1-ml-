# 콘텐츠 가이드 (P5) — v9.5

## 1. 카피 정본

### ML 응답에 박힌 카피 (변경 시 P1 협의)
| 카드 | 정본 위치 |
|---|---|
| `drill.copy.line1/2/3` | `ml_service/app/core/recommender.py` `_build_copy()` — confidence < 0.5 시 추측형 톤 자동 |
| `crisis_card.user_message` | `ml_service/app/core/crisis_card.py` — 변형 절대 X |
| `positive_card.message` | `ml_service/app/core/positive_card.py` `POSITIVE_MESSAGES` (4종 로테이션) |
| `ask_user.question` (일반) | `ml_service/app/core/ask_user.py` `ASK_QUESTION` |
| `ask_user.question` (v9.4.4 ask-first) | `ml_service/app/core/ask_user.py` `_DRILL_OFFER_CONFIG` (3 템플릿) |
| `skip.message` | `ml_service/app/core/ask_user.py` `build_skip` |
| 자가진단 퀴즈 | `ml_service/app/core/self_check_quiz.py` |
| 발견 카드 4종 | `ml_service/app/core/auto_discovery.py` |

### v9.4.4 ask-first 3 템플릿 (P5 윤문 권장)

```python
low_condition:   "텍스트는 잔잔한데 컨디션이 좀 낮으시네요 ({value}점). 잠시 그라운딩 해보실래요?"
short_sleep:     "텍스트는 괜찮은데 어젯밤 잠이 짧으셨네요 ({value}시간). 수면 루틴 드릴 받아보실래요?"
social_conflict: "텍스트는 잔잔한데 오늘 사람 관계가 좀 힘드셨네요. 자기 자비 드릴 받아보실래요?"
```

검수 포인트:
- "잔잔한데" 자연스러운가?
- `{value}점` / `{value}시간` 포맷 명확한가?
- "받아보실래요?" 자기 결정권 강조 톤 OK?

수정 제안 → P1 → ML 코드 갱신.

## 2. 윤문 가능 위치

- 드릴 카탈로그 `instruction` / `title` / `source_short` — `w1/drills_seed_v6_3.json`은 읽기 전용. **v9.5: drill_id INT 마이그레이션 완료** (예: `1, 2, ..., 77`). 변경 시 PR + W1 데이터 버전 업.
- 긍정 카드 4종 로테이션 → `positive_card.py POSITIVE_MESSAGES` (확장 권장)
- ask_user 일반 + v9.4.4 ask-first 3 템플릿 → `ask_user.py`

## 3. 절대 금지 표현 (§2.3)

| ❌ | ✅ |
|---|---|
| "당신은 X 유형입니다" | "이번 주에 X가 자주 보였어요" |
| "잘못된 생각이에요" | "이런 생각이 보여요" |
| "좋아졌어요" / "성장했어요" | "지난주보다 평균 컨디션이 0.3 높았어요" |
| 진단·치료·환자·우울증·불안장애 | 단어 사용 X |
| "X 때문에 Y" | "X 와 Y가 같이 나타났어요" |
| "꼭 ~ 해야" / "반드시" | "~ 해볼 수 있어요" |
| "맞췄어요/틀렸어요" (퀴즈) | "정답: X · 비율 32%" |
| "잘하고 있어요" / "파이팅" | 응원·평가 0 |
| 이모지 1줄 2개 이상 | 사실만 |

자동 검출: `python -X utf8 ml_service/scripts/lint_copy.py app/`

## 4. 새 드릴 추가 절차 (v9.5)

1. 학술 출처 1차 확인 (Beck/Burns/Ellis/Martell/Neff/Walker/Huberman/Fogg 등)
2. `w1/drills_seed_v6_3.json`에 추가:
   ```json
   {
     "id": 78,                          // v9.5: 정수 ID (다음 빈 번호)
     "legacy_id": "D78",                // 옵션 — 옛 데이터 호환용
     "title": "...",                    // 12자 이내 권장
     "instruction": "...",
     "duration_min": 5,
     "category": "cognitive_restructuring",
     "patterns": {...},
     "behaviors": {...},
     "emotions": {...},
     "context_affinity": {...},
     "source_primary": "Beck, J. S. (2020). ...",
     "source_short": "Beck(2020) CBT 11장",
     "evidence_level": "primary",
     "quality_audit": "approved"
   }
   ```
3. PR → P1 검토 → 머지
4. `category_distribution`, `behavior_category_ratio` 갱신
5. 시뮬레이션: `python -X utf8 ml_service/scripts/simulate_recommend.py`

행동·습관 비중 50% 목표 유지.

## 5. 베타 동의서 12개 필수 항목

```
[Step Back 베타 사용 동의서]

1. 익명 사용 (실명·학번·연락처 X — google_sub만)
2. 90일 보관 후 자동 삭제
3. 회원 탈퇴 시 30일 이내 전체 삭제
4. 외부 LLM (Gemini) 사용 명시
5. PII 자동 마스킹 (URL/이메일/전화/학번/이름) 명시
6. 위기 시 1393/1388/1577-0199 안내 명시
7. 도구 한계: 의학적 진단·치료 아님 명시
8. LLM 라벨링은 단서 추출 — 임상 판정 아님
9. 학부 졸업 프로젝트 — 베타 12명 비통계적 평가 명시
10. 본인 데이터 JSON export 권리
11. 데이터 삭제 요청 권리 (30일 이내)
12. 동의 시점 timestamp 기록

[동의합니다]
```

학교 IRB 가이드 확인 후 P1 검토.

## 6. v9.5 신규 카피 검수 — drill_category 한국어 라벨

`app/schemas/common.py` `CATEGORY_LABEL_KO`:

```
cognitive_restructuring → "생각 전환"
behavioral_activation → "산책"
habit_design → "긍정 확언"
grounding → "마음 챙김"
self_compassion → "자기 자비"
sleep_circadian → "수면 정돈"
```

검수: 사용자에게 카테고리 표시 시 한국어 라벨이 의미 정확한가?

## 7. v9.5 신규 — calendar_dominant 한국어 라벨

`app/schemas/common.py` `CALENDAR_DOMINANT_LABEL_KO`:

```
crisis → "주의"
cognitive_dominant → "사고 패턴"
behavior_dominant → "회피·미루기"
emotion_anger → "분노"
emotion_anxiety → "불안"
emotion_depression → "우울"
emotion_guilt → "죄책"
weak_signal_positive → "안정"
weak_signal_low → "잔잔"
```

## 8. 위기 응답 — 변형 절대 금지

```
"지금 많이 힘드신 것 같아요. 혼자 견디지 마세요."

24시간 무료 상담:
  · 자살예방상담 1393
  · 청소년상담 1388
  · 정신건강위기상담 1577-0199
```

P5는 이 카피를 변경하지 않음. 다른 카피와 일관성 검토만.

## 9. 다음 단계

1. lint_copy 통과 확인 (현재 PASS)
2. 77 드릴 instruction 윤문 (v9.5 INT ID 확인)
3. v9.4.4 ask-first 3 템플릿 검수
4. 베타 동의서 초안 → 학생상담센터 검토
5. 새 드릴 추가 제안 (행동 비중 50% 목표)
6. 카탈로그 v6.4 (확장판) 협업
