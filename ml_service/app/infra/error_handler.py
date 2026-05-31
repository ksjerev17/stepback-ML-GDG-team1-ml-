# 출처: handoff/error_codes.md — 5 코드 통일 응답
"""모든 예외를 {detail: {code, message, ...}} 형태로 통일."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infra.quota_manager import QuotaExceededError
from app.infra.request_context import get_request_id


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(QuotaExceededError)
    async def quota_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "QUOTA_EXCEEDED",
                    "message": str(exc),
                    "scope": exc.scope,
                    "retry_after_seconds": exc.retry_after_seconds,
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # v9.4.3: pydantic ValidationError ctx 안의 Exception 객체는 JSON 직렬화 안 됨.
        # str()로 변환해서 직렬화 가능한 형태로.
        safe_errors = []
        for err in exc.errors():
            safe_err = dict(err)
            if "ctx" in safe_err and isinstance(safe_err["ctx"], dict):
                safe_err["ctx"] = {
                    k: (str(v) if isinstance(v, Exception) else v)
                    for k, v in safe_err["ctx"].items()
                }
            # url도 객체일 수 있음
            if "url" in safe_err:
                safe_err["url"] = str(safe_err["url"])
            safe_errors.append(safe_err)
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "VALIDATION_ERROR",
                    "message": "입력 검증 실패",
                    "errors": safe_errors,
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 기존 라우터가 이미 {detail:{code,message}} 형식으로 raise한 경우 그대로 전달
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            payload = dict(exc.detail)
            payload.setdefault("request_id", get_request_id())
            return JSONResponse(status_code=exc.status_code, content={"detail": payload})

        code = "INVALID_INPUT" if exc.status_code < 500 else "INTERNAL_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": {
                    "code": code,
                    "message": str(exc.detail),
                    "request_id": get_request_id(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "INTERNAL_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                    "request_id": get_request_id(),
                }
            },
        )
