import json

import httpx
import pytest

from backend.app.providers.openai_compat_provider import OpenAICompatProvider


@pytest.mark.asyncio
async def test_mimo_preset_uses_api_key_and_completion_token_parameter() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["api-key"] == "sk-test"
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        assert payload["model"] == "mimo-v2.5-pro"
        assert payload["max_completion_tokens"] == 1024
        assert "max_tokens" not in payload
        assert payload["temperature"] == 1.0
        assert payload["top_p"] == 0.95
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "MiMo OK"}}]
        })

    provider = OpenAICompatProvider(
        api_key="sk-test",
        api_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2.5-pro",
        display_name="Xiaomi MiMo",
        auth_header="api-key",
        auth_scheme="",
        max_tokens_param="max_completion_tokens",
        default_config={"temperature": 1.0, "top_p": 0.95},
    )
    provider._client = httpx.AsyncClient(
        base_url="https://api.xiaomimimo.com/v1",
        headers={"api-key": "sk-test"},
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await provider.generate_text("请介绍自己", {"max_tokens": 1024})
        assert result == "MiMo OK"
    finally:
        await provider.close()


def test_rejects_unknown_token_parameter() -> None:
    with pytest.raises(Exception, match="max_tokens_param"):
        OpenAICompatProvider(
            api_key="sk-test",
            api_url="https://example.test/v1",
            model="model",
            max_tokens_param="output_tokens",
        )


def test_supports_bearer_style_custom_provider() -> None:
    provider = OpenAICompatProvider(
        api_key="secret",
        api_url="https://example.test/v1",
        model="custom-model",
        auth_header="Authorization",
        auth_scheme="Bearer",
    )
    assert provider.auth_header == "Authorization"
    assert provider.auth_scheme == "Bearer"


def test_registry_builds_custom_text_provider() -> None:
    from backend.app.providers import clear_providers, get_provider, init_providers

    clear_providers()
    try:
        init_providers(
            mock=False,
            openai_compat_key="tp-test",
            openai_compat_url="https://token-plan-cn.xiaomimimo.com/v1",
            openai_compat_model="mimo-v2.5-pro",
            openai_compat_name="Xiaomi MiMo",
            openai_compat_auth_header="api-key",
            openai_compat_auth_scheme="",
            openai_compat_max_tokens_param="max_completion_tokens",
        )
        provider = get_provider("openai_compat")
        assert provider is not None
        assert provider.capabilities.text is True
        assert provider.capabilities.image is False
        assert provider.display_name == "Xiaomi MiMo"
    finally:
        clear_providers()
