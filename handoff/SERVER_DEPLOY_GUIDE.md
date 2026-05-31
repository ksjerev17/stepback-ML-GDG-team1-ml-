# BE 서버에 ML 상시 띄우기 — 처음부터 따라 하기

> 목표: BE 서버(`119.201.125.216`)에 ML을 한 번 올려두고, **서버가 재부팅돼도 자동으로 다시 뜨게** 만들기. 그러면 BE 팀원이 더는 "ML 떠있냐"를 안 물어봐도 됩니다.
>
> 두 가지 길이 있어요: **Docker 방식(추천, 깔끔)** / **systemd 방식(Docker 없을 때)**. 서버에 Docker가 있는지부터 확인하고 갈게요.

---

## 0. 사전 지식 (1분)

- **SSH** = 내 PC에서 멀리 있는 서버에 원격 접속하는 것. 터미널(PowerShell/맥 터미널)에 명령을 치면 그게 **서버에서** 실행돼요.
- **포트 8001** = ML이 듣는 문. BE는 `http://<서버>:8001` 로 ML을 호출.
- 이 작업은 **서버 SSH 접속 권한**이 필요해요. 권한이 BE/인프라 담당에게 있으면 이 문서를 그분과 같이 보세요.

---

## 1. 서버 접속 (SSH)

내 PC 터미널(PowerShell)에서:
```bash
ssh 사용자명@119.201.125.216
```
- `사용자명`은 서버 계정 (예: `ubuntu`, `root`, 또는 팀이 만든 계정).
- 비밀번호를 묻거나, 키 파일이 필요하면: `ssh -i 키파일.pem 사용자명@119.201.125.216`
- 접속되면 프롬프트가 서버 것으로 바뀌어요 (예: `ubuntu@server:~$`). 이제부터 치는 건 다 서버에서 실행돼요.

> 접속 정보(계정/비번/키)는 BE 담당이 알고 있을 거예요. 모르면 그분께 먼저 받으세요.

---

## 2. Docker 있는지 확인

서버에서:
```bash
docker --version
```
- **버전이 나오면** → 3-A (Docker 방식)으로.
- **"command not found"** 나오면 → Docker 설치하거나(아래 박스), 3-B (systemd 방식)으로.

<details>
<summary>Docker 설치 (Ubuntu, 선택)</summary>

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # sudo 없이 docker 쓰려면 (재로그인 필요)
```
</details>

---

## 3. 코드를 서버에 올리기

### git을 쓰는 경우
```bash
git clone <레포_주소>
cd stepback        # ml_service, w1 이 보이는 폴더
```

### zip을 올리는 경우
내 PC(서버 아님)에서 zip을 서버로 복사:
```bash
# 내 PC 터미널에서 (서버 아님!)
scp stepback_v9.7_FINAL.zip 사용자명@119.201.125.216:~/
```
그 다음 다시 서버에서:
```bash
unzip stepback_v9.7_FINAL.zip
cd stepback        # 폴더 구조에 따라 cd stepback/stepback 일 수도
ls                 # ml_service, w1, handoff 가 보이면 정위치
```

---

## 3-A. Docker 방식 (추천)

`ml_service`, `w1` 이 보이는 `stepback/` 폴더에서:

```bash
# (1) 이미지 빌드 — 1~3분 걸림
docker build -t stepback-ml -f ml_service/Dockerfile .

# (2) 실행 — 실제 Gemini로 상시 가동
docker run -d --restart=always --name stepback-ml \
  -p 8001:8001 \
  -e GEMINI_API_KEY="AIza...여기에_너의_Gemini_키" \
  -e AUDIT_SALT="아무_32자_이상_랜덤문자열_바꾸세요_0123456789" \
  -e ADMIN_TOKEN="팀이_정한_관리_토큰" \
  stepback-ml
```

각 옵션 뜻:
- `-d` : 백그라운드 실행 → **SSH 끊어도 계속 떠있음**.
- `--restart=always` : **서버 재부팅돼도 자동으로 다시 뜸** (이게 핵심!).
- `--name stepback-ml` : 컨테이너 이름 (나중에 관리용).
- `-p 8001:8001` : 서버 8001 포트 → 컨테이너 8001 (Dockerfile이 8001로 듣게 돼 있음).
- `-e ...` : 환경변수. Gemini 키 없이 **Mock으로 먼저** 띄우려면 `GEMINI_API_KEY` 줄만 빼면 됨.

확인:
```bash
docker ps                              # stepback-ml 이 "Up" 이면 성공
curl http://127.0.0.1:8001/healthz     # {"status":"ok","drills_loaded":100}
```

자주 쓰는 관리 명령:
```bash
docker logs -f stepback-ml             # 로그 실시간 보기 (Ctrl+C로 빠져나옴)
docker restart stepback-ml             # 코드 바꾼 뒤 재시작
docker stop stepback-ml                # 멈추기
docker rm -f stepback-ml               # 지우기 (다시 docker run 하려면 먼저 이거)
```

---

## 3-B. systemd 방식 (Docker 없을 때)

```bash
cd stepback
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml_service/requirements.txt
```

서비스 파일 작성:
```bash
sudo nano /etc/systemd/system/stepback-ml.service
```
아래 내용 붙여넣기 (경로의 `사용자명`을 실제 계정으로):
```ini
[Unit]
Description=Step Back ML
After=network.target

[Service]
WorkingDirectory=/home/사용자명/stepback
Environment="GEMINI_API_KEY=AIza...너의_키"
Environment="AUDIT_SALT=아무_32자_이상_랜덤문자열_바꾸세요"
Environment="ADMIN_TOKEN=팀이_정한_관리_토큰"
Environment="PYTHONPATH=/home/사용자명/stepback/ml_service"
ExecStart=/home/사용자명/stepback/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --app-dir ml_service
Restart=always

[Install]
WantedBy=multi-user.target
```
저장: `Ctrl+O` → Enter → `Ctrl+X`.

등록 & 시작:
```bash
sudo systemctl daemon-reload
sudo systemctl enable stepback-ml      # 부팅 시 자동 시작
sudo systemctl start stepback-ml
sudo systemctl status stepback-ml      # "active (running)" 이면 성공
curl http://127.0.0.1:8001/healthz
```

관리 명령:
```bash
journalctl -u stepback-ml -f           # 로그 실시간
sudo systemctl restart stepback-ml     # 코드 바꾼 뒤 재시작
```

---

## 4. 실제 Gemini로 떴는지 확인
```bash
curl -H "x-admin-token: 팀이_정한_관리_토큰" http://127.0.0.1:8001/healthz/detail
```
응답에서:
- `"is_mock": false` + `"primary_model": "gemini-..."` → **실제 Gemini로 가동 중** ✅
- `"is_mock": true` → 키가 안 먹은 것. `GEMINI_API_KEY` 환경변수 확인 후 재시작.

---

## 5. BE 연결
ML이 같은 서버에 떴으니, BE 환경변수만 맞추면 끝:
```
ML_BASE_URL = http://127.0.0.1:8001
```
(BE와 ML이 같은 서버라 `127.0.0.1`. 다른 서버면 그 서버 IP.)

그리고 BE 호출부는 **ML이 죽어도 BE가 안 터지게** try-catch 권장 (특히 회원 탈퇴):
```java
try {
    mlClientService.deleteUserData(userId);
} catch (Exception e) {
    log.warn("ML 미연결 — 나중에 재시도: {}", userId);
}
userRepository.delete(user);   // BE DB 삭제는 항상 진행
```

---

## 6. 자주 막히는 곳

| 증상 | 해결 |
|---|---|
| `curl: connection refused` | 컨테이너/서비스 안 떠있음 → `docker ps` / `systemctl status` 확인 |
| 포트 8001 충돌 | `-p 8002:8001` 로 바꾸고 BE `ML_BASE_URL`도 8002로 |
| `is_mock: true` 인데 Gemini 원함 | 환경변수에 키 들어갔는지 확인 후 재시작 |
| 다른 서버의 BE가 접속 안 됨 | 방화벽에서 8001 포트 열기 (같은 서버면 불필요) |
| 빌드 중 네트워크 에러 | 서버가 pypi 접근 가능한지 확인 |

---

## 7. 정직한 한계
- 이 작업은 **서버 SSH 접속 권한**이 있어야 가능해요. ML/AI가 대신 못 띄웁니다 — 권한 가진 사람이 위를 실행해야 해요.
- 한 번 `--restart=always`(Docker) 또는 `systemctl enable`(systemd)로 띄워두면, 그 뒤로는 서버가 살아있는 한 ML도 계속 떠있어요. → "ML 떠있냐" 질문이 사라집니다.
