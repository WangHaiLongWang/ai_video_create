import base64
from pathlib import Path

import httpx
import pytest

from backend.app.providers.wan3_provider import Wan3VideoProvider


@pytest.mark.asyncio
async def test_first_frame_video_uses_480p_defaults(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"png-image")
    polls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        if request.url.path.endswith("/video-generation/video-synthesis"):
            payload = __import__("json").loads(request.content)
            assert request.headers["X-DashScope-Async"] == "enable"
            assert payload["model"] == "wan3.0-video"
            assert payload["parameters"]["resolution"] == "480P"
            assert payload["parameters"]["ratio"] == "adaptive"
            assert payload["parameters"]["duration"] == 5
            assert payload["parameters"]["audio"] is True
            assert payload["input"]["media"][0]["type"] == "first_frame"
            assert payload["input"]["media"][0]["url"].startswith("data:image/png;base64,")
            return httpx.Response(200, json={"output": {"task_id": "video-task"}})
        if request.url.path.endswith("/tasks/video-task"):
            polls += 1
            if polls == 1:
                return httpx.Response(200, json={"output": {"task_status": "RUNNING"}})
            return httpx.Response(200, json={"output": {
                "task_status": "SUCCEEDED", "video_url": "https://example.test/result.mp4"
            }})
        if request.url.path == "/result.mp4":
            return httpx.Response(200, content=b"video-bytes")
        return httpx.Response(404)

    provider = Wan3VideoProvider("test-key")
    transport = httpx.MockTransport(handler)
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v1", transport=transport
    )

    original_client = httpx.AsyncClient

    class DownloadClient:
        def __init__(self, *args, **kwargs):
            self.client = original_client(transport=transport)
        async def __aenter__(self):
            return self.client
        async def __aexit__(self, *args):
            await self.client.aclose()

    import backend.app.providers.wan3_provider as module
    module.httpx.AsyncClient = DownloadClient
    try:
        result = await provider.generate_video(
            str(image), "镜头缓慢推进", {"poll_interval": 0}
        )
        assert result == b"video-bytes"
    finally:
        module.httpx.AsyncClient = original_client
        await provider.close()


@pytest.mark.parametrize("config", [
    {"resolution": "360P"},
    {"ratio": "2:1"},
    {"duration": 1},
    {"duration": 31},
    {"seed": -2},
])
@pytest.mark.asyncio
async def test_invalid_options_are_rejected(config: dict) -> None:
    provider = Wan3VideoProvider("test-key")
    with pytest.raises(Exception):
        await provider.generate_video("", "test prompt", config)
