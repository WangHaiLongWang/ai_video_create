"""Canonical application version shared by API health and release tooling."""

from pathlib import Path


def _read_version() -> str:
    # backend/app/version.py -> repository root / VERSION
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        value = "1.0.0-rc.1"
    return value or "1.0.0-rc.1"


APP_VERSION = _read_version()
