"""Tests for security middleware: rate limiter and CORS configuration."""

from __future__ import annotations

import importlib
import os
import sys
import time
from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------

from backend.app.middleware.rate_limit import RateLimitMiddleware


async def _ok(request):
    return Response("OK")


def _app_with_limiter(default_limit: int = 60, agent_limit: int = 20, path: str = "/"):
    app = Starlette(routes=[Route(path, _ok)])
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=default_limit,
        agent_limit=agent_limit,
    )
    return app


def test_rate_limit_allows_under_threshold():
    # Temporarily enable rate limiting for this test
    old = os.environ.pop("DISABLE_RATE_LIMIT", None)
    try:
        app = _app_with_limiter(default_limit=5, agent_limit=3)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        for _ in range(4):
            r = client.get("/")
            assert r.status_code == 200
    finally:
        client.__exit__(None, None, None)
        if old is not None:
            os.environ["DISABLE_RATE_LIMIT"] = old


def test_rate_limit_blocks_at_threshold():
    # Temporarily enable rate limiting for this test
    old = os.environ.pop("DISABLE_RATE_LIMIT", None)
    try:
        app = _app_with_limiter(default_limit=3, agent_limit=2)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        for _ in range(3):
            r = client.get("/")
            assert r.status_code == 200

        r = client.get("/")
        assert r.status_code == 429
        assert "Retry-After" in r.headers
    finally:
        client.__exit__(None, None, None)
        if old is not None:
            os.environ["DISABLE_RATE_LIMIT"] = old


def test_rate_limit_agent_stricter():
    """Agent endpoints use the lower agent_limit."""
    old = os.environ.pop("DISABLE_RATE_LIMIT", None)
    try:
        app = _app_with_limiter(default_limit=60, agent_limit=2, path="/api/agent/chat")
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        for _ in range(2):
            r = client.get("/api/agent/chat")
            assert r.status_code == 200

        r = client.get("/api/agent/chat")
        assert r.status_code == 429
    finally:
        client.__exit__(None, None, None)
        if old is not None:
            os.environ["DISABLE_RATE_LIMIT"] = old


def test_rate_limit_disabled_env_skips_rate_limiting():
    """DISABLE_RATE_LIMIT=1 must disable RateLimitMiddleware entirely."""
    old = os.environ.get("DISABLE_RATE_LIMIT")
    os.environ["DISABLE_RATE_LIMIT"] = "1"
    try:
        app = _app_with_limiter(default_limit=2, agent_limit=1)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        # Far past the limit — must never 429 while the flag is set.
        for _ in range(20):
            r = client.get("/")
            assert r.status_code == 200
    finally:
        client.__exit__(None, None, None)
        if old is None:
            os.environ.pop("DISABLE_RATE_LIMIT", None)
        else:
            os.environ["DISABLE_RATE_LIMIT"] = old


# ---------------------------------------------------------------------------
# SecurityMiddleware rate limiter — must honour the same DISABLE_RATE_LIMIT flag
# ---------------------------------------------------------------------------

from backend.app.middleware import SecurityMiddleware


def _app_with_security(rate_limit: int):
    app = Starlette(routes=[Route("/", _ok)])
    app.add_middleware(SecurityMiddleware, rate_limit=rate_limit)
    return app


def test_security_middleware_rate_limit_blocks_over_threshold():
    """SecurityMiddleware throttles at its own threshold (main.py uses 200)."""
    old = os.environ.pop("DISABLE_RATE_LIMIT", None)
    try:
        app = _app_with_security(rate_limit=3)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        for _ in range(3):
            assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429
    finally:
        client.__exit__(None, None, None)
        if old is not None:
            os.environ["DISABLE_RATE_LIMIT"] = old


def test_security_middleware_respects_disable_rate_limit():
    """Regression: both limiters must honour DISABLE_RATE_LIMIT.

    Setting the flag used to disable only RateLimitMiddleware, so
    SecurityMiddleware still returned 429 and broke the E2E suite.
    """
    old = os.environ.get("DISABLE_RATE_LIMIT")
    os.environ["DISABLE_RATE_LIMIT"] = "1"
    try:
        app = _app_with_security(rate_limit=3)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()

        for _ in range(20):
            assert client.get("/").status_code == 200
    finally:
        client.__exit__(None, None, None)
        if old is None:
            os.environ.pop("DISABLE_RATE_LIMIT", None)
        else:
            os.environ["DISABLE_RATE_LIMIT"] = old


# ---------------------------------------------------------------------------
# CORS configuration tests
# ---------------------------------------------------------------------------

from backend.app.config.cors import get_cors_origins, get_cors_config


def test_cors_config_returns_dict():
    cfg = get_cors_config()
    assert isinstance(cfg, dict)
    assert "allow_origins" in cfg
    assert "allow_credentials" in cfg
    assert cfg["allow_credentials"] is True


def test_cors_env_override(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com, https://b.com")
    monkeypatch.delenv("AI_VIDEO_DEBUG", raising=False)
    monkeypatch.delenv("AI_VIDEO_ENV", raising=False)
    origins = get_cors_origins()
    assert origins == ["https://a.com", "https://b.com"]


def test_cors_dev_defaults(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("AI_VIDEO_DEBUG", "true")
    origins = get_cors_origins()
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_cors_empty_when_not_dev(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("AI_VIDEO_DEBUG", raising=False)
    monkeypatch.delenv("AI_VIDEO_ENV", raising=False)
    origins = get_cors_origins()
    assert origins == []
