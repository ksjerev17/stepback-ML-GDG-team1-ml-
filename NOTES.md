# P1 인계 노트 — 자율 구축 v2.0 후 확인·결정 필요 사항

> 명세서 v9.4.3 풀스택 구현 후. 이 문서는 P1이 직접 처리할 항목 모음.

## 1. 결정 필요 (P1 직접 판단)

| # | 항목 | 추천 행동 |
|---|---|---|
| **D1** | **Gemini API 키 발급** | 1. Google AI Studio에서 키 발급. 2. `.env`에 `GEMINI_API_KEY=AIza...` 입력. 3. `FORCE_MOCK=false`로 변경. 4. `pip install google-generativeai==0.8.3`. 5. `app/infra/llm_client.py`의 `initialize()`/`label()` 메서드 안에 W1 `model_router.py`의 `ModelRouter().initialize()` 호출 + `call_primary()` 사용으로 연결. Mock 모드와 실제 모드는 응답 스키마 동일하므로 BE/FE 영향 0. |
| **D2** | **W1 라벨링 결과 파일 배치** | `w1/labeling_results_v1.json` (또는 `labeling_audit_v1.json`)을 폴더에 넣으면 `scripts/analyze_labeling.py`가 자동으로 부록 D 8 항목 보고. 현재는 결과 파일 없음 → placeholder만 생성. |
| **D3** | **git init + private repo** | 폴더는 아직 git 저장소 아님. `cd stepback && git init && git add . && git commit -m "chore: v2.0 풀스택 자율 구축"`. private repo로 push. CLAUDE.md §13.4 GitHub 설정 (branch protection, secret scanning, push protection) 수동 적용. |
| **D4** | **베타 동의서 초안** | P5 작성, P1 검토. `handoff/content_guide.md §5` 참조. 학교 IRB 가이드 확인 필요. |
| **D5** | **Logistic Regression v2** (§10.3) | 베타 W5~W6 동안 200개 피드백 누적 후 `scikit-learn`으로 학습. 현재는 미구현 (NOTES만). Features 약 30개 (인지 6 + 행동 2 + 감정 5 + 맥락 4 + 카테고리 6 + baseline 7). target = `feedbacks.helpful`. 사용자별 또는 통합 모델 선택. |
| **D6** | **이메일 발송 (§4.6)** | BE(P2) 영역이지만 ML이 `POST /reports`로 일요일 cron시 row 생성. 메일 게이트웨이 (학교 SMTP / SendGrid 무료) BE에서 선택. |
| **D7** | **드릴 카탈로그 확장** | 현재 77개. 100~150개로 확장 시 P5 검수 + 학술 출처 확인 + PR. behavior 비중 50% 목표 유지. 카테고리 분포는 `w1/drills_seed_v6_3.json`이 정본 (인지 22/행동 22/습관 15/그라운딩 9/자기자비 5/수면 4). **명세서 §6.3 (인지 31/행동 14/습관 12/그라운딩 10/자기자비 6/수면 4)와 차이가 있음** — JSON 정본 우선 적용. |

## 2. 명세서 vs 구현 — 의도적 차이 (검토 필요)

| 항목 | 명세서 | 현재 구현 | 사유 |
|---|---|---|---|
| 드릴 카탈로그 카운트 | 인지 31 / 행동 14 / 습관 12 / 그라운딩 10 / 자기자비 6 / 수면 4 (§6.3) | JSON 정본은 인지 22 / 행동 22 / 습관 15 / 그라운딩 9 / 자기자비 5 / 수면 4 | W1 정본(JSON) 우선. 명세서 표는 v6 초기 추산일 가능성. P5 확인 필요. |
| insights 토글 UI 카테고리 | "인지 패턴 / 행동 신호 / 감정 / 맥락 상관" (§9.4) | `cognitive / behavior / emotion / context / drill` (drill 추가) | 효과적 드릴 발견 (§8.4 #3)을 위해 `drill` 카테고리 추가. |
| Step 4 (명세서 §6.2) | 모든 신호 0.3~0.5 시 객관식 정밀화 | `ask_user` 형식으로 후보 2 + "비슷해요" 노출 | clarification_loop이 LLM 객관식 호출이라면, FE에 직접 묻는 형식으로 변환 (사용자 직접 선택). |
| baseline 사용 | "평소보다 X 30% 높음" (§10.2) | 10%p 이상 차이 시 카드 노출 | 30% 임계가 너무 높음 → 10%p로 완화. 베타 데이터로 조정 권장. |

## 3. Mock 폴백 한계 (실 LLM 받으면 자동 해결)

| 한계 | 원인 | 해결 |
|---|---|---|
| `공부해야 하는데 일어나지 못해서 하기 싫어` S005 케이스가 Mock에서 ask_user (0.3~0.5 경계선) | 어휘 단서 단순 매칭으로 0.4 점수 | 실 Gemini는 의미 기반 → 0.7+. API 활성화 후 자동 해결. |
| 인지 패턴(당위진술 등) Mock에서 약하게 잡힘 | linguistic_cues 매칭 부족 | 실 LLM 후 재측정. |
| Mock confidence 0.4~0.6 균일 | 점수 산식 | 실 LLM 자연스러운 0.3~0.9 분포. |

## 4. 환경 미설치 — 본 자율 모드 스킵

| 도구 | 처리 |
|---|---|
| `ruff`, `black`, `mypy` | `pip install -r requirements-dev.txt` 후 수동 실행 권장. |
| `pytest-cov` | 환경에 미설치. 핵심 모듈은 207 PASS (v9.5)로 직접 검증. |
| `pre-commit`, `detect-secrets`, `gitleaks` | git init 후 일괄 설치. CLAUDE.md §13.2 참조. |

## 5. CLAUDE.md와 코드 위치 차이

- CLAUDE.md는 `step-back/` 가정. 현재 `stepback/`. 사실상 동일.
- CLAUDE.md `.claude/skills`, `.claude/agents`, `.mcp.json`, root `pyproject.toml`, `.pre-commit-config.yaml`은 본 모드 범위 외. 필요 시 `이거야3/step-back-master-v3.1`에서 복사.

## 6. 외부 통신 안전 확인

- `app/infra/llm_client.py` 현재 Mock 전용. `google.generativeai` import 0건.
- `httpx`/`requests` 외부 호출 0건.
- 모든 데이터는 폴더 안에만. 외부 git remote 없음.

§0.13 외부 통신 0 원칙 준수.

## 7. 18 엔드포인트 — 구현 상태

| Method | Path | 상태 | 호출자 |
|---|---|---|---|
| GET | /healthz | ✓ | BE/devops |
| POST | /label | ✓ | BE |
| POST | /recommend | ✓ | BE |
| POST | /feedback | ✓ | BE |
| GET | /feedback | ✓ (점수 비공개) | BE |
| GET | /weekly | ✓ (데모) | FE 직접/BE |
| POST | /weekly | ✓ | BE |
| PATCH | /weekly/quiz | ✓ | BE |
| POST | /weekly/condition_flow | ✓ | BE |
| POST | /weekly/pattern_diff | ✓ | BE |
| POST | /baseline/recompute | ✓ | BE 일별 cron |
| GET | /baseline | ✓ | BE |
| POST | /insights | ✓ | BE |
| GET | /insights | ✓ | BE |
| POST | /reject | ✓ | BE |
| POST | /reports | ✓ | BE 일요일 cron |
| GET | /reports/pending | ✓ | BE |
| PATCH | /reports/{id}/read | ✓ | BE |
| POST | /calendar | ✓ | BE |
| POST | /daily | ✓ (helpful 비공개) | BE |
| GET | /drills/{id} | ✓ | BE/FE |
| GET | /drills | ✓ | BE |
| GET | /export | ✓ | BE |
| DELETE | /users/{user_id}/data | ✓ | BE |

## 8. 다음 권장 단계 우선순위

1. **API 키 발급 + 실 LLM 전환** → 합치율 재측정
2. **git init + private repo + branch protection**
3. **BE(P2) HANDOFF_TO_BE.md 전달 + 통합 테스트**
4. **P5 검수 — 카탈로그·카피·동의서**
5. **W3 동안 베타 사용자 8~12명 모집**
6. **W5 베타 200 샘플 누적 → logistic regression 학습**

## 9. 빠른 실행 체크

```powershell
cd "c:/cogdrill 팀1 ML/stepback/ml_service"
python -X utf8 -m pytest tests/ -q       # 207 PASS (v9.5)
python -X utf8 scripts/pre_demo_check.py # 5/5 PASS
python -X utf8 scripts/lint_copy.py app/ # PASS
uvicorn app.main:app --host 127.0.0.1 --port 8001
# http://127.0.0.1:8001/docs (Swagger)
```
