# 깃허브에 올리기 — 복사해서 그대로 쓰기

> 두 가지 방법을 다 적었어요. **방법 1**은 터미널에서 직접 git 명령(가장 확실), **방법 2**는 Claude Code 같은 AI 에이전트에게 시키는 프롬프트.

---

## 준비: 한글 파일명/깨짐 이미 정리됨
- 한글 파일명 → 전부 영문으로 변경 완료 (예: `ML_최종_인계.md` → `ML_FINAL_HANDOFF.md`).
- 모든 .md는 UTF-8 정상. `.gitignore`로 캐시·키·DB 제외됨.
- 깃허브에서 한글 **내용**은 정상 표시됩니다 (UTF-8). 깨졌던 건 **파일명**이 원인이었어요.

---

## 방법 1. 터미널에서 직접 (권장 · 가장 확실)

압축 푼 `stepback/` 폴더(= `ml_service`, `w1`이 보이는 곳)에서 터미널 열고, 아래를 **위에서부터 한 줄씩**:

```bash
# 1) git 시작 (이미 .git 있으면 건너뜀)
git init

# 2) 한글 파일명/메시지 깨짐 방지 설정 (중요!)
git config core.quotepath false
git config i18n.commitEncoding utf-8
git config i18n.logOutputEncoding utf-8

# 3) 전체 추가 + 커밋
git add .
git commit -m "Step Back ML v9.7 - 100 drills, explainable recommendation, weekly coaching"

# 4) 메인 브랜치 이름 통일
git branch -M main

# 5) 깃허브 원격 연결 (★ 아래 URL을 본인 저장소로 바꾸세요)
git remote add origin https://github.com/사용자명/저장소명.git

# 6) 업로드
git push -u origin main
```

**5번 URL 만드는 법**: 깃허브에서 New repository → 이름 입력 → Create → 나오는 `https://github.com/.../....git` 복사.

**로그인 창이 뜨면**: 비밀번호 대신 **Personal Access Token**이 필요할 수 있어요. (깃허브 → Settings → Developer settings → Personal access tokens → 토큰 생성 → 그 토큰을 비밀번호 자리에 붙여넣기)

---

## 방법 2. Claude Code(또는 AI 에이전트)에게 시키기 — 프롬프트 복사

`stepback/` 폴더에서 Claude Code를 열고 아래를 그대로 붙여넣으세요:

```
이 폴더(stepback)를 깃허브에 올려줘. 조건:

1. git이 아직 없으면 git init 으로 시작해줘.
2. 한글 파일명/커밋메시지가 깨지지 않게 먼저 이 설정을 적용해:
   git config core.quotepath false
   git config i18n.commitEncoding utf-8
   git config i18n.logOutputEncoding utf-8
3. .gitignore가 이미 있으니 그대로 쓰고, __pycache__·.venv·*.db·logs·.env 는 절대 커밋하지 마.
4. 모든 파일을 추가하고, 커밋 메시지는 다음으로:
   "Step Back ML v9.7 - 100 drills, explainable recommendation, weekly coaching"
5. 브랜치는 main 으로 하고, 내가 알려줄 원격 저장소로 push 해줘.
   원격 URL: https://github.com/사용자명/저장소명.git
   (이 URL은 내 실제 저장소 주소로, 내가 알려주면 그걸 써)
6. push 전에 .env 나 API 키가 커밋에 포함되지 않았는지 반드시 확인하고 알려줘.
7. 다 되면 깃허브에서 한글이 안 깨지고 잘 보이는지 README 기준으로 확인해줘.

내 깃허브 저장소 URL은: (여기에 본인 저장소 주소 붙여넣기)
```

---

## ⚠️ 올리기 전 꼭 확인 (보안)

**API 키가 깃허브에 올라가면 안 돼요.** 다음을 확인하세요:
- `.env` 파일이 있다면 → `.gitignore`에 이미 포함됨 (안 올라감). 혹시 키를 코드에 직접 박았다면 빼세요.
- `deploy_gcp.sh`, `START_HERE.bat` 등에 실제 키를 적어뒀다면 → `AIza...` 같은 실제 키를 지우고 `여기에_키` 같은 placeholder로 바꾸세요. (지금은 placeholder 상태입니다)
- 커밋 후 확인: `git log -p | grep -i "AIza"` → 아무것도 안 나오면 안전.

---

## 다음에 또 업로드할 때 (수정 후)
```bash
git add .
git commit -m "수정 내용 한 줄 설명"
git push
```
