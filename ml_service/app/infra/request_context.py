# 출처: 운영 보강 — 요청 추적용 request_id 미들웨어
"""각 요청에 X-Request-ID 부여 → 응답 헤더 + audit_log에 노출."""
from __future__ import annotations

import contextvars
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    return _request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """X-Request-ID 헤더 → 없으면 uuid4 발급. 응답 헤더에도 반영."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = _request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
