"""Tests for DB path resolution — AI_VIDEO_DB_PATH / Settings.DB_PATH isolation."""

from __future__ import annotations

import pytest

import backend.app.db.connection as conn_mod
from backend.app.config import reset_settings


@pytest.fixture(autouse=True)
def _clean_db_state():
    """Reset cached path/connection and settings around every test."""
    conn_mod.close_connection()
    original = conn_mod._DB_PATH
    conn_mod._DB_PATH = None
    reset_settings()
    yield
    conn_mod.close_connection()
    conn_mod._DB_PATH = original
    reset_settings()


class TestDbPathResolution:
    def test_default_path_uses_project_data_dir(self):
        path = conn_mod._get_db_path()
        assert path.name == "ai_video_create.db"
        assert path.parent.name == "data"

    def test_env_var_selects_db_path(self, tmp_path, monkeypatch):
        target = tmp_path / "isolated" / "e2e.db"
        monkeypatch.setenv("AI_VIDEO_DB_PATH", str(target))
        reset_settings()
        conn_mod._DB_PATH = None

        path = conn_mod._get_db_path()
        assert path == target
        assert path.parent.is_dir()

    def test_settings_db_path_honored(self, tmp_path, monkeypatch):
        """Settings.DB_PATH is read when AI_VIDEO_DB_PATH env is absent."""
        monkeypatch.delenv("AI_VIDEO_DB_PATH", raising=False)
        target = tmp_path / "from-settings.db"
        monkeypatch.setenv("AI_VIDEO_DB_PATH", str(target))
        reset_settings()

        conn_mod._DB_PATH = None
        path = conn_mod._get_db_path()
        assert path == target

    def test_relative_custom_path_resolves_against_project_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_VIDEO_DB_PATH", "data/custom_e2e.db")
        reset_settings()
        conn_mod._DB_PATH = None

        path = conn_mod._get_db_path()
        assert path.name == "custom_e2e.db"
        assert not str(path).startswith("data/")
        assert path.is_absolute()
