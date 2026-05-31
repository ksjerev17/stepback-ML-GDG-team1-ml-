# 출처: CLAUDE.md §11, §13
"""앱 설정 — 환경 변수 로드."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
W1_DIR = REPO_ROOT / "w1"
DATA_DIR = Path(__file__).resolve().parent / "data"
LOGS_DIR = REPO_ROOT / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    audit_salt: str = "dev_salt_change_me_change_me_change_me"
    force_mock: bool = True
    ml_host: str = "127.0.0.1"
    ml_port: int = 8001

    # ── v9.6: 배포 연동 설정 ─────────────────────────────────────────────
    # BE(Spring Boot)·DB(PostgreSQL) 서버. ML은 BE를 직접 호출하지 않지만
    # CORS 허용·헬스 표기·문서화를 위해 보관.
    be_host: str = "119.201.125.216"
    be_port: int = 8080
    db_host: str = "119.201.125.216"
    db_port: int = 5432
    # ML이 외부(GCP)에서 뜰 때 0.0.0.0 바인딩 + BE 출처 CORS 허용 여부.
    deploy_mode: bool = False
    # 추가로 허용할 CORS 출처 (콤마 구분). 예: "https://app.stepback.kr"
    extra_cors_origins: str = ""

    quota_per_minute: int = 1
    quota_per_hour: int = 3
    quota_per_day: int = 3

    llm_call_gap_seconds: float = 6.0
    llm_retry_max: int = 2
    llm_timeout_label: float = 30.0
    llm_timeout_clarify: float = 10.0


def get_settings() -> Settings:
    return Settings()


def allowed_cors_origins() -> list[str]:
    """v9.6: 로컬 + BE 서버(119.201.125.216:8080) + 추가 출처를 CORS 허용 목록으로.

    deploy_mode=True 면 BE 서버 출처를 자동 포함 (GCP에서 ML이 떠 있을 때
    실제 BE가 호출할 수 있도록). 로컬 출처는 항상 허용 (개발 편의).
    """
    s = get_settings()
    origins = [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        # BE 서버 (Spring Boot) — 로컬·배포 모두 호출 가능하도록 항상 포함
        f"http://{s.be_host}:{s.be_port}",
        f"https://{s.be_host}:{s.be_port}",
    ]
    if s.extra_cors_origins:
        origins.extend(o.strip() for o in s.extra_cors_origins.split(",") if o.strip())
    # 중복 제거 (순서 보존)
    seen: set[str] = set()
    out: list[str] = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


def should_force_mock() -> bool:
    """Mock 사용 여부 결정 (v9.7: 기본값 = 키 있으면 Gemini).

    우선순위:
    1) 환경변수 FORCE_MOCK 가 명시되면 그대로 따른다 (true→Mock, false→Gemini).
    2) 그 외에는 Gemini 키가 있으면 실 Gemini, 없으면 Mock.
       (즉 '키만 넣으면 자동으로 Gemini' — 최종 산출물 기본 동작)
    """
    settings = get_settings()
    env = os.environ.get("FORCE_MOCK", "").strip().lower()
    if env in ("true", "1", "yes"):
        return True
    if env in ("false", "0", "no"):
        # 명시적으로 실 LLM 요청 — 단 키 없으면 안전하게 Mock 폴백
        return not bool(settings.gemini_api_key)
    # 미지정: 키가 있으면 Gemini, 없으면 Mock
    return not bool(settings.gemini_api_key)
