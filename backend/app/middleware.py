"""Security middleware — request limits, security headers."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件 — 添加安全头、请求大小限制、简单速率限制。"""

    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024, rate_limit: int = 100):
        """
        Args:
            app: ASGI app
            max_body_size: 最大请求体大小 (bytes), 默认 10MB
            rate_limit: 每分钟每 IP 最大请求数
        """
        super().__init__(app)
        self.max_body_size = max_body_size
        self.rate_limit = rate_limit
        self._request_counts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # 1. 安全响应头
        client_ip = request.client.host if request.client else "unknown"

        # 2. 速率限制 (简单滑动窗口)
        now = time.time()
        window = 60.0  # 1 分钟窗口

        # 清理过期记录
        self._request_counts[client_ip] = [
            t for t in self._request_counts[client_ip] if now - t < window
        ]

        if len(self._request_counts[client_ip]) >= self.rate_limit:
            return JSONResponse(
                {"detail": "请求过于频繁，请稍后重试"},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        self._request_counts[client_ip].append(now)

        # 3. 请求体大小限制 (仅对 POST/PUT)
        if request.method in ("POST", "PUT"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_body_size:
                return JSONResponse(
                    {"detail": f"请求体过大，最大 {self.max_body_size // (1024*1024)}MB"},
                    status_code=413,
                )

        # 4. 执行请求
        response = await call_next(request)

        # 5. 添加安全响应头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class InputSanitizeMiddleware(BaseHTTPMiddleware):
    """输入清理中间件 — 清理危险字符。"""

    # 危险模式
    DANGEROUS_PATTERNS = [
        "<script",
        "javascript:",
        "onerror=",
        "onload=",
        "eval(",
        "exec(",
    ]

    async def dispatch(self, request: Request, call_next):
        # 检查查询参数
        for key, value in request.query_params.items():
            if self._contains_dangerous(value):
                return JSONResponse(
                    {"detail": "请求包含不安全内容"},
                    status_code=400,
                )

        response = await call_next(request)
        return response

    def _contains_dangerous(self, value: str) -> bool:
        """检查值是否包含危险模式。"""
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in self.DANGEROUS_PATTERNS)
