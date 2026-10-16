"""Factory for persisted provider profiles."""
from __future__ import annotations

from typing import Any


def build_configured_provider(config_id: str):
    from backend.app.repositories.provider_configs import (
        ProviderConfigNotFoundError,
        get_provider_config,
        get_secret,
    )

    try:
        profile = get_provider_config(config_id)
    except ProviderConfigNotFoundError:
        return None
    if not profile["enabled"]:
        return None
    kind = profile["provider_type"]
    config: dict[str, Any] = profile["config"]
    api_url = config.get("api_url", "")
    api_key = get_secret(config_id, "api_key") or ""

    if kind == "mock":
        from .mock_provider import MockProvider
        provider = MockProvider(delay=float(config.get("delay", 0)))
    elif kind == "ollama":
        from .ollama_provider import OllamaProvider
        provider = OllamaProvider(api_url=api_url or "http://localhost:11434", model=config.get("model", "llama3.2"))
    elif kind == "openai":
        from .openai_provider import OpenAIProvider
        provider = OpenAIProvider(api_key=api_key, api_url=api_url or "https://api.openai.com/v1", model=config.get("model", "gpt-4"), image_model=config.get("image_model", "dall-e-3"))
    elif kind == "openai_compat":
        from .openai_compat_provider import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key=api_key, api_url=api_url, model=config.get("model", ""), display_name=profile["name"], auth_header=config.get("auth_header", "Authorization"), auth_scheme=config.get("auth_scheme", "Bearer"), max_tokens_param=config.get("max_tokens_param", "max_tokens"), default_config=config.get("default_config", {}))
    elif kind == "dashscope":
        from .dashscope_provider import DashScopeProvider
        provider = DashScopeProvider(api_key=api_key, api_url=api_url or "https://dashscope.aliyuncs.com/api/v1", image_model=config.get("model", config.get("image_model", "qwen-image-3.0")), default_config=config.get("default_config", {}))
    elif kind == "wan3":
        from .wan3_provider import Wan3VideoProvider
        provider = Wan3VideoProvider(api_key=api_key, api_url=api_url or "https://dashscope.aliyuncs.com/api/v1", model=config.get("model", "wan3.0-video"), default_config=config.get("default_config", {}))
    elif kind == "doubao":
        from .doubao_provider import DoubaoProvider
        provider = DoubaoProvider(api_key=api_key, api_url=api_url or "https://ark.cn-beijing.volces.com/api/v3", image_model=config.get("image_model", ""), video_model=config.get("video_model", ""), default_config=config.get("default_config", {}))
    elif kind == "comfyui":
        from .comfyui_provider import ComfyUIProvider
        provider = ComfyUIProvider(api_url=api_url or "http://localhost:8188")
    else:
        return None

    # Registry keys may be profile IDs; provider.name remains its adapter type
    # for errors and observability.
    setattr(provider, "config_id", config_id)
    setattr(provider, "configured_models", config.get("models", []))
    return provider
