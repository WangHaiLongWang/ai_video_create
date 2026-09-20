"""Tests for backend.app.middleware.security_headers."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.middleware.security_headers import SecurityHeadersMiddleware


# ---------------------------------------------------------------------------
# Minimal ASGI app for testing
# ---------------------------------------------------------------------------

async def _minimal_app(scope, receive, send):
    """Bare-bones ASGI app returning 200 for every request."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


async def _health_app(scope, receive, send):
    """Simulates a health-check endpoint."""
    path = scope.get("path", "")
    status = 200 if path in ("/", "/health", "/api/health") else 404
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


# ---------------------------------------------------------------------------
# Helper to build a wrapped app
# ---------------------------------------------------------------------------

def _make_client(app=None, **mw_kwargs):
    target = app or _minimal_app
    mw = SecurityHeadersMiddleware(target, **mw_kwargs)
    return AsyncClient(transport=ASGITransport(app=mw), base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_expected_headers_present():
    client = _make_client()
    resp = await client.get("/api/test")
    assert resp.status_code == 200

    expected = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "x-xss-protection": "1; mode=block",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=(), microphone=(), geolocation=()",
    }
    for header, value in expected.items():
        assert resp.headers.get(header) == value, f"Missing or wrong {header}"


@pytest.mark.asyncio
async def test_request_id_generated():
    client = _make_client()
    resp = await client.get("/api/test")
    request_id = resp.headers.get("x-request-id")
    assert request_id is not None
    # Should be a valid UUID4
    parsed = uuid.UUID(request_id)
    assert parsed.version == 4


@pytest.mark.asyncio
async def test_health_endpoint_skips_headers():
    """Health check endpoints should NOT receive security headers."""
    client = _make_client(app=_health_app)

    for path in ("/", "/health", "/api/health"):
        resp = await client.get(path)
        assert resp.status_code == 200
        # X-Request-ID should be absent (headers were not injected)
        assert resp.headers.get("x-request-id") is None
        assert resp.headers.get("x-content-type-options") is None


@pytest.mark.asyncio
async def test_csp_header_correct():
    client = _make_client()
    resp = await client.get("/api/test")
    csp = resp.headers.get("content-security-policy")
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp


@pytest.mark.asyncio
async def test_custom_csp():
    custom = "default-src 'none'"
    client = _make_client(csp=custom)
    resp = await client.get("/api/test")
    assert resp.headers.get("content-security-policy") == custom


@pytest.mark.asyncio
async def test_hsts_absent_for_http():
    """HSTS header should NOT appear for plain HTTP connections."""
    client = _make_client()
    resp = await client.get("/api/test")
    assert resp.headers.get("strict-transport-security") is None


@pytest.mark.asyncio
async def test_hsts_present_for_https():
    """HSTS header SHOULD appear when X-Forwarded-Proto indicates HTTPS."""

    async def https_app(scope, receive, send):
        # Inject forwarded-proto header
        scope["headers"] = [[b"x-forwarded-proto", b"https"]]
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    mw = SecurityHeadersMiddleware(https_app)
    client = AsyncClient(transport=ASGITransport(app=mw), base_url="http://testserver")
    resp = await client.get("/api/test")
    hsts = resp.headers.get("strict-transport-security")
    assert hsts is not None
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_non_http_scope_passthrough():
    """Non-HTTP ASGI scopes (e.g. websocket) should pass through unchanged."""
    called = []

    async def ws_app(scope, receive, send):
        called.append(True)
        await send({"type": "websocket.accept"})

    async def noop_send(message):
        pass

    mw = SecurityHeadersMiddleware(ws_app)
    await mw(
        {"type": "websocket", "path": "/ws"},
        None,
        noop_send,
    )
    assert called
