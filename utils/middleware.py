"""Middleware de trazabilidad y timing para FastAPI."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("billing_pro")


class TimingMiddleware(BaseHTTPMiddleware):
    """Logea tiempo de respuesta y asigna request_id por request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.time()

        response = await call_next(request)

        duration = time.time() - start
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        method = request.method
        path = request.url.path
        status = response.status_code
        logger.info(f"[{request_id}] {method} {path} {status} — {duration:.3f}s")

        return response
