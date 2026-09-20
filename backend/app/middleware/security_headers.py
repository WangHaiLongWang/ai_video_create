"""ASGI middleware that attaches security headers to every response.

Usage::

    from backend.app.middleware.security_headers import SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware)
"""

from __future__ import annotations

import uuid
from typing import Callable

# The middleware is framework-agnostic ASGI (not Starlette-specific), so
# the only import needed is ``typing``.


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware that adds standard security response headers.

    Features:
    * Adds a ``X-Request-ID`` (UUID4) to every response.
    * Skips header injection for health-check endpoints (``/health``, ``/``).
    * Conditionally includes ``Strict-Transport-Security`` only when the
      connection appears to use HTTPS (``X-Forwarded-Proto`` header or
      ``scope["type"]`` inspection).
    """

    # Paths that should not receive security headers (health checks).
    _SKIP_PATHS: frozenset[str] = frozenset({"/", "/health", "/api/health"})

    def __init__(
        self,
        app,  # ASGIApp type -- kept untyped to avoid starlette import
        *,
        hsts_max_age: int = 31536000,
        csp: str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
    ) -> None:
        self.app = app
        self._hsts_max_age = hsts_max_age
        self._csp = csp

    # ------------------------------------------------------------------
    # ASGI interface
    # ------------------------------------------------------------------

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path: str = scope.get("path", "")
        if path in self._SKIP_PATHS:
            return await self.app(scope, receive, send)

        async def send_wrapper(message: dict) -> None:
            if message["type"] != "http.response.start":
                return await send(message)

            # --- build headers ---
            headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))

            header_map = {
                b"x-content-type-options": b"nosniff",
                b"x-frame-options": b"DENY",
                b"x-xss-protection": b"1; mode=block",
                b"referrer-policy": b"strict-origin-when-cross-origin",
                b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                b"content-security-policy": self._csp.encode(),
                b"x-request-id": str(uuid.uuid4()).encode(),
            }

            # Conditional HSTS -- only when the connection looks like HTTPS
            is_https = _is_https(scope)
            if is_https:
                header_map[b"strict-transport-security"] = (
                    f"max-age={self._hsts_max_age}; includeSubDomains".encode()
                )

            # Replace any existing security headers we set, then append new ones.
            existing_keys = {k for k, _ in headers}
            new_headers: list[tuple[bytes, bytes]] = []
            for key, value in header_map.items():
                if key in existing_keys:
                    headers = [(k, v) for k, v in headers if k != key]
                new_headers.append((key, value))

            message["headers"] = headers + new_headers
            return await send(message)

        return await self.app(scope, receive, send_wrapper)


def _is_https(scope: dict) -> bool:
    """Heuristic: check forwarded proto or ASGI server scheme."""
    # ASGI 3.0 servers may set ``scheme`` in scope
    if scope.get("scheme") == "https":
        return True

    # Look at headers for X-Forwarded-Proto
    headers: dict[bytes, bytes] = dict(scope.get("headers", []))
    proto = headers.get(b"x-forwarded-proto", b"").decode().strip().lower()
    return proto == "https"
