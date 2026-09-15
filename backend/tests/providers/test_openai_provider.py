import base64

import httpx
import pytest

from backend.app.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_generate_image_accepts_base64_response() -> None:
    expected = b"test-image"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/generations"
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})

    provider = OpenAIProvider("test-key", image_model="dall-e-3")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await provider.generate_image("a scene") == expected
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_generate_qwen_image_accepts_url_response_without_dalle_fields() -> None:
    expected = b"qwen-image"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/images/generations":
            payload = __import__("json").loads(request.content)
            assert payload["model"] == "qwen-image-3.0"
            assert "quality" not in payload
            assert "style" not in payload
            assert "response_format" not in payload
            return httpx.Response(200, json={"data": [{"url": "https://example.test/files/image.png"}]})
        if request.url.path == "/files/image.png":
            return httpx.Response(200, content=expected, headers={"content-type": "image/png"})
        return httpx.Response(404)

    provider = OpenAIProvider("test-key", image_model="qwen-image-3.0")
    provider._client = httpx.AsyncClient(
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert await provider.generate_image("a scene", {"size": "1280x720"}) == expected
    finally:
        await provider.close()
