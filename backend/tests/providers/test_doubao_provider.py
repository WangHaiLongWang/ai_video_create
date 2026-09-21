import base64
import json
from pathlib import Path

import httpx
import pytest

from backend.app.providers.doubao_provider import DoubaoProvider
from backend.app.providers import clear_providers, get_provider, init_providers
from backend.app.config import ProviderType, Settings


@pytest.mark.asyncio
async def test_seedream_text_to_image_contract() -> None:
    expected = b"seedream-image"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/images/generations")
        payload = json.loads(request.content)
        assert payload["model"] == "image-endpoint-id"
        assert payload["prompt"] == "cinematic ski lesson"
        assert payload["size"] == "1280x720"
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})

    provider = DoubaoProvider("test-key", image_model="image-endpoint-id")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v3", transport=httpx.MockTransport(handler)
    )
    try:
        assert await provider.generate_image("cinematic ski lesson") == expected
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_seedance_image_to_video_contract(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"png")
    polls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["model"] == "seedance-2.5-endpoint-id"
            assert payload["duration"] == 5
            assert payload["resolution"] == "720p"
            assert payload["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
            return httpx.Response(200, json={"id": "task-123"})
        polls += 1
        if polls == 1:
            return httpx.Response(200, json={"id": "task-123", "status": "running"})
        return httpx.Response(200, json={
            "id": "task-123", "status": "succeeded", "content": {"video_url": "https://cdn.test/video.mp4"}
        })

    provider = DoubaoProvider("test-key", video_model="seedance-2.5-endpoint-id")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v3", transport=httpx.MockTransport(handler)
    )

    async def fake_download(url: str, timeout: float) -> bytes:
        assert url == "https://cdn.test/video.mp4"
        return b"seedance-video"

    provider._download = fake_download  # type: ignore[method-assign]
    try:
        result = await provider.generate_video(str(image), "slow camera push", {"poll_interval": 0})
        assert result == b"seedance-video"
        assert provider.get_external_job_id() == "task-123"
    finally:
        await provider.close()


@pytest.mark.parametrize("config", [
    {"duration": 3}, {"resolution": "4k"}, {"ratio": "2:1"},
])
@pytest.mark.asyncio
async def test_seedance_rejects_invalid_options(config: dict) -> None:
    provider = DoubaoProvider("test-key")
    with pytest.raises(Exception):
        await provider.generate_video("", "test", config)


def test_provider_registry_and_settings_contract() -> None:
    clear_providers()
    try:
        init_providers(
            mock=False,
            doubao_key="test-key",
            doubao_image_model="image-endpoint",
            doubao_video_model="video-endpoint",
        )
        provider = get_provider("doubao")
        assert provider is not None
        assert provider.capabilities.image is True
        assert provider.capabilities.video is True

        settings = Settings(DOUBAO_API_KEY="test-key")
        config = settings.get_provider_config(ProviderType.DOUBAO)
        assert config.api_url.endswith("/api/v3")
        assert config.extra_params["image_model"] == "doubao-seedream-5-0-pro-260628"
    finally:
        clear_providers()
