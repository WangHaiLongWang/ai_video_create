from backend.app.main import app, health
from backend.app.version import APP_VERSION
import asyncio
from pathlib import Path


def test_fastapi_and_health_use_canonical_version():
    assert APP_VERSION == (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
    assert app.version == APP_VERSION


def test_health_uses_canonical_version():
    payload = asyncio.run(health())
    assert payload["version"] == APP_VERSION
    assert payload["ffmpeg"] is True
