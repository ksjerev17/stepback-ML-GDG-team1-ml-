# 출처: CLAUDE.md §7, §13.3
"""FastAPI 앱 부트. 127.0.0.1만 listen (§13.3) + CORS는 localhost만 허용."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    calendar as cal_api,
    drills as drills_api,
    entries,   # v9.5
    feedback,
    health,
    insights,
    label,
    monthly,   # v9.5
    personalization,   # v9.6
    recommend,
    reports,
    weekly,
)
from app.config import allowed_cors_origins
from app.infra.error_handler import install_handlers
from app.infra.request_context import RequestIDMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="Step Back ML",
        description="감정·인지·행동 라벨링 + 학술 드릴 추천 + 개인화 코칭.",
        version="0.3.0",
    )

    # CORS — 로컬 BE/FE + BE 서버(119.201.125.216:8080) 허용 (§13.3, v9.6)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_cors_origins(),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    # 요청 추적
    app.add_middleware(RequestIDMiddleware)

    # 통일된 에러 응답
    install_handlers(app)

    # 라우터
    for router in (
        health.router,
        label.router,
        entries.router,   # v9.5
        recommend.router,
        feedback.router,
        weekly.router,
        monthly.router,   # v9.5 — 월간 리포트
        personalization.router,   # v9.6 — 개인화 프로파일
        insights.router,
        reports.router,
        drills_api.router,
        cal_api.router,
        admin.router,
    ):
        app.include_router(router)

    return app


app = create_app()
