"""CORS configuration — reads allowed origins from environment / settings."""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


def get_cors_origins() -> List[str]:
    """Build the list of allowed CORS origins.

    Priority:
    1. ``CORS_ALLOWED_ORIGINS`` env var (comma-separated)
    2. If ``AI_VIDEO_DEBUG`` is truthy or ``AI_VIDEO_ENV=dev`` → localhost defaults
    3. Empty list (no cross-origin allowed)
    """
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        logger.debug("CORS origins from env: %s", origins)
        return origins

    debug = os.environ.get("AI_VIDEO_DEBUG", "").lower() in ("1", "true", "yes")
    env = os.environ.get("AI_VIDEO_ENV", "").lower()
    if debug or env in ("dev", "development"):
        dev_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        logger.debug("CORS dev defaults: %s", dev_origins)
        return dev_origins

    return []


def get_cors_config() -> dict:
    """Return a dict suitable for ``CORSMiddleware`` keyword arguments."""
    origins = get_cors_origins()
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Request-ID"],
        "max_age": 600,
    }
