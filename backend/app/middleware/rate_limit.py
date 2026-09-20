"""Sliding-window rate limiting middleware."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter.

    * Default: 60 requests / minute
    * ``/api/agent/*`` endpoints: 20 requests / minute
    """

    AGENT_PREFIX = "/api/agent/"

    def __init__(
        self,
        app,
        default_limit: int = 60,
        agent_limit: int = 20,
        window: float = 60.0,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.agent_limit = agent_limit
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _limit_for(self, path: str) -> int:
        if path.startswith(self.AGENT_PREFIX):
            return self.agent_limit
        return self.default_limit

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting when explicitly disabled (e.g. for integration tests)
        if os.getenv("DISABLE_RATE_LIMIT") == "1":
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()
        limit = self._limit_for(request.url.path)

        # Evict expired timestamps
        self._hits[ip] = [t for t in self._hits[ip] if now - t < self.window]

        if len(self._hits[ip]) >= limit:
            retry_after = int(self.window - (now - self._hits[ip][0])) + 1
            logger.warning(
                "Rate limit exceeded for %s on %s (%d/%d)",
                ip,
                request.url.path,
                len(self._hits[ip]),
                limit,
            )
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._hits[ip].append(now)
        return await call_next(request)
