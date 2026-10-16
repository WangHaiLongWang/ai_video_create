"""安全测试共享 fixtures — 重置速率限制器状态。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers
from backend.app.db.connection import close_connection, init_db
import backend.app.db.connection as conn_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()
    yield
    close_connection()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """每个测试前重置速率限制器状态。"""
    # 找到 SecurityMiddleware 实例并清空请求计数
    for middleware in app.user_middleware:
        if hasattr(middleware, "cls") and middleware.cls.__name__ == "SecurityMiddleware":
            # 中间件是延迟实例化的，需要通过 app 的 middleware stack 获取
            break
    # 直接通过 app 的 middleware stack 获取实例
    if hasattr(app, "middleware_stack") and app.middleware_stack:
        _reset_middleware_rate_limiters(app.middleware_stack)
    yield


def _reset_middleware_rate_limiters(middleware):
    """递归重置中间件栈中的速率限制器。"""
    if hasattr(middleware, "_request_counts"):
        middleware._request_counts.clear()
    if hasattr(middleware, "app"):
        _reset_middleware_rate_limiters(middleware.app)
    if hasattr(middleware, "inner"):
        _reset_middleware_rate_limiters(middleware.inner)


@pytest.fixture
def client():
    """创建测试客户端并重置 providers。"""
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    # 重置速率限制器
    if hasattr(app, "middleware_stack") and app.middleware_stack:
        _reset_middleware_rate_limiters(app.middleware_stack)
    with TestClient(app) as c:
        yield c
    clear_providers()
