"""Root conftest for backend tests.

Provides shared fixtures and skip markers for tests that depend on
external binaries (FFmpeg, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that ``backend`` is importable
# when running tests from within the ``backend/`` directory.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# FFmpeg availability
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ffmpeg_path() -> str | None:
    """Return the path to the ffmpeg binary, or None if unavailable.

    Session-scoped so the discovery cost is paid only once per test run.
    """
    from backend.app.services.ffmpeg import get_ffmpeg_path
    return get_ffmpeg_path()


@pytest.fixture(scope="session")
def ffmpeg_available(ffmpeg_path: str | None) -> bool:
    """Return True if ffmpeg was found on this system.

    Session-scoped; depends on ``ffmpeg_path``.
    """
    return ffmpeg_path is not None


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests marked ``@pytest.mark.external`` when the
    required external binary is not available on the system.
    """
    from backend.app.services.ffmpeg import is_ffmpeg_available

    ffmpeg_missing = not is_ffmpeg_available()
    if not ffmpeg_missing:
        return

    skip_external = pytest.mark.skip(reason="FFmpeg not available on this system")
    for item in items:
        if "external" in item.keywords:
            item.add_marker(skip_external)
