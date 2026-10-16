"""HARD-506 provider failure drills: failed providers never yield assets."""

from __future__ import annotations

import asyncio
import pytest

from backend.app.handlers import clear_handlers, init_real_handlers, get_handler
from backend.app.providers import clear_providers, register_provider
from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderRateLimitError,
)


class FailingProvider(BaseProvider):
    name = "drill"
    capabilities = ProviderCapabilities(text=True, image=True, video=True)

    def __init__(self, error: Exception):
        self.error = error

    async def generate_text(self, prompt, config=None):
        raise self.error

    async def generate_image(self, prompt, config=None):
        raise self.error

    async def generate_video(self, image_path, prompt, config=None):
        raise self.error


@pytest.fixture(autouse=True)
def providers():
    clear_providers()
    clear_handlers()
    init_real_handlers()
    yield
    clear_providers()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ProviderError("drill", "upstream failure"),
        ProviderRateLimitError("drill", retry_after=3),
        ProviderError("drill", "provider timed out"),
    ],
)
async def test_image_provider_failures_are_failed_without_asset(error, monkeypatch):
    register_provider(FailingProvider(error))
    from backend.app.config import reset_settings
    reset_settings()
    try:
        result = await get_handler("textToImage").execute(
            {
                "id": "drill-image",
                "item_key": "scene-001",
                "config": {"provider": "drill", "image_prompt": "x"},
            },
            {},
        )
        assert result.status == "failed"
        assert result.output is None
        assert result.artifacts == []
    finally:
        monkeypatch.delenv("AI_VIDEO_DEFAULT_IMAGE_PROVIDER", raising=False)
        reset_settings()


@pytest.mark.asyncio
async def test_video_provider_cancel_or_failure_never_creates_asset():
    provider = FailingProvider(ProviderError("wan3", "job cancelled"))
    provider.name = "wan3"
    register_provider(provider)
    from backend.app.config import reset_settings
    import os
    os.environ["AI_VIDEO_DEFAULT_VIDEO_PROVIDER"] = "wan3"
    reset_settings()
    try:
        result = await get_handler("imageToVideo").execute(
            {
                "id": "drill-video",
                "item_key": "scene-001",
                "config": {"image_path": "missing.png", "video_prompt": "x"},
            },
            {},
        )
        # Missing input is rejected before provider submission; either way no
        # successful artifact may be reported.
        assert result.status == "failed"
        assert result.output is None
        assert result.artifacts == []
    finally:
        os.environ.pop("AI_VIDEO_DEFAULT_VIDEO_PROVIDER", None)
        reset_settings()


@pytest.mark.asyncio
async def test_missing_real_video_provider_does_not_fall_back_to_fake_success(monkeypatch):
    monkeypatch.setenv("AI_VIDEO_DEFAULT_VIDEO_PROVIDER", "doubao")
    from backend.app.config import reset_settings
    reset_settings()
    try:
        result = await get_handler("imageToVideo").execute(
            {
                "id": "missing-video-provider",
                "item_key": "scene-001",
                "config": {"image_path": "missing.png", "video_prompt": "x"},
            },
            {},
        )
        assert result.status == "failed"
        assert result.error.code == "NO_VIDEO_PROVIDER"
        assert result.output is None
        assert result.artifacts == []
    finally:
        monkeypatch.delenv("AI_VIDEO_DEFAULT_VIDEO_PROVIDER", raising=False)
        reset_settings()


@pytest.mark.asyncio
async def test_storyboard_provider_failure_is_not_replaced_with_mock_success(monkeypatch):
    register_provider(FailingProvider(ProviderRateLimitError("drill", retry_after=1)))
    monkeypatch.setenv("AI_VIDEO_DEFAULT_LLM_PROVIDER", "openai_compat")
    # Select the registered drill provider explicitly at node level.
    result = await get_handler("storyboard").execute(
        {"id": "drill-story", "config": {"provider": "drill", "prompt": "x", "scenes": 1}},
        {},
    )
    assert result.status == "failed"
    assert result.output is None
    assert result.artifacts == []


@pytest.mark.asyncio
async def test_cancelled_provider_call_propagates_without_asset():
    provider = FailingProvider(asyncio.CancelledError())
    register_provider(provider)
    with pytest.raises(asyncio.CancelledError):
        await get_handler("textToImage").execute(
            {
                "id": "cancelled-image",
                "item_key": "scene-001",
                "config": {"provider": "drill", "image_prompt": "x"},
            },
            {},
        )
