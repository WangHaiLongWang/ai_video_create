import base64
import json

import httpx
import pytest

from backend.app.providers.dashscope_provider import DashScopeProvider


@pytest.mark.asyncio
async def test_qwen_image_async_task_and_base64_result() -> None:
    expected = b"qwen-image"
    polls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        if request.url.path.endswith("/image-generation/generation"):
            payload = json.loads(request.content)
            assert payload["model"] == "qwen-image-3.0"
            assert payload["parameters"]["size"] == "1280*720"
            assert request.headers["X-DashScope-Async"] == "enable"
            return httpx.Response(200, json={"output": {"task_id": "task-1", "task_status": "PENDING"}})
        if request.url.path.endswith("/tasks/task-1"):
            polls += 1
            if polls == 1:
                return httpx.Response(200, json={"output": {"task_status": "RUNNING"}})
            return httpx.Response(200, json={"output": {
                "task_status": "SUCCEEDED",
                "results": [{"b64_json": base64.b64encode(expected).decode()}],
            }})
        return httpx.Response(404)

    provider = DashScopeProvider("test-key")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v1",
        transport=httpx.MockTransport(handler),
        headers={"X-DashScope-Async": "enable"},
    )
    try:
        result = await provider.generate_image(
            "future city", {"size": "1280x720", "poll_interval": 0, "use_async": True}
        )
        assert result == expected
        assert polls == 2
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_failed_task_is_reported() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"output": {"task_id": "failed-task"}})
        return httpx.Response(200, json={
            "output": {"task_status": "FAILED"},
            "message": "invalid image size",
        })

    provider = DashScopeProvider("test-key")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception, match="invalid image size"):
            await provider.generate_image("future city", {"poll_interval": 0})
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_uses_official_sync_endpoint_by_default() -> None:
    expected = b"sync-image"
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/multimodal-generation/generation")
        assert request.headers.get("X-DashScope-Async") is None
        return httpx.Response(200, json={"output": {
            "results": [{"b64_json": base64.b64encode(expected).decode()}]
        }})

    provider = DashScopeProvider("test-key")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await provider.generate_image("future city")
        assert result == expected
        assert calls == 1
    finally:
        await provider.close()


@pytest.mark.parametrize("size", ["100x100", "99999x99999", "invalid"])
@pytest.mark.asyncio
async def test_rejects_invalid_size_before_request(size: str) -> None:
    provider = DashScopeProvider("test-key")
    with pytest.raises(Exception, match="size|pixels"):
        await provider.generate_image("future city", {"size": size})
