"""Persistent provider settings and encrypted secret tests (HARD-301/302)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import backend.app.db.connection as db
from backend.app.config import get_settings, reset_settings
from backend.app.main import app
from backend.app.repositories.configs import get_raw


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db.close_connection()
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "settings.db")
    monkeypatch.setattr(db, "_CONNECTION", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "test-master-key")
    reset_settings()
    db.init_db()
    yield
    db.close_connection()
    reset_settings()


def test_settings_update_persists_across_settings_restart_without_key_echo(monkeypatch):
    monkeypatch.delenv("AI_VIDEO_DISABLE_PERSISTED_SETTINGS", raising=False)
    client = TestClient(app)
    response = client.put("/api/config/settings", json={
        "default_image_provider": "dashscope",
        "dashscope_image_model": "qwen-image-test",
        "dashscope_api_key": "secret-dashscope-key",
    })
    assert response.status_code == 200
    assert get_raw("provider.dashscope_api_key").startswith("enc:v1:")

    reset_settings()
    restored = get_settings()
    assert restored.DEFAULT_IMAGE_PROVIDER.value == "dashscope"
    assert restored.DASHSCOPE_IMAGE_MODEL == "qwen-image-test"
    assert restored.DASHSCOPE_API_KEY == "secret-dashscope-key"

    body = client.get("/api/config/settings").json()
    assert "dashscope_api_key" not in body
    assert "secret-dashscope-key" not in str(body)


def test_invalid_legacy_mimo_token_limit_is_safely_normalized(monkeypatch):
    monkeypatch.setenv("AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS", "1048576")
    reset_settings()
    assert get_settings().OPENAI_COMPAT_MAX_TOKENS == 4096


def test_settings_api_rejects_mimo_limit_above_model_bound():
    response = TestClient(app).put(
        "/api/config/settings",
        json={"openai_compat_max_tokens": 131073},
    )
    assert response.status_code == 400
