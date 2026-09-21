"""Provider registry — register and retrieve AI providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Provider registry: name -> provider instance
_providers: dict[str, BaseProvider] = {}


def register_provider(provider: BaseProvider) -> None:
    """Register a provider instance."""
    _providers[provider.name] = provider
    logger.info(f"Registered provider: {provider.name}")


def get_provider(name: str) -> BaseProvider | None:
    """Get a registered provider by name."""
    return _providers.get(name)


def list_providers() -> list[dict]:
    """List all registered providers with their capabilities."""
    result = []
    for name, provider in _providers.items():
        result.append({
            "name": name,
            "display_name": getattr(provider, "display_name", name),
            "capabilities": provider.capabilities.model_dump(),
        })
    return result


def clear_providers() -> None:
    """Clear all registered providers (for testing)."""
    _providers.clear()


def init_providers(
    mock: bool = True,
    ollama_url: str | None = None,
    openai_key: str | None = None,
    openai_url: str = "https://api.openai.com/v1",
    openai_model: str = "gpt-4",
    openai_image_model: str = "dall-e-3",
    openai_compat_key: str | None = None,
    openai_compat_url: str = "",
    openai_compat_model: str = "",
    openai_compat_name: str = "OpenAI Compatible",
    openai_compat_auth_header: str = "Authorization",
    openai_compat_auth_scheme: str = "Bearer",
    openai_compat_max_tokens_param: str = "max_tokens",
    openai_compat_default_config: dict | None = None,
    dashscope_key: str | None = None,
    dashscope_url: str = "https://dashscope.aliyuncs.com/api/v1",
    dashscope_image_model: str = "qwen-image-3.0",
    dashscope_default_config: dict | None = None,
    wan3_key: str | None = None,
    wan3_url: str = "https://dashscope.aliyuncs.com/api/v1",
    wan3_model: str = "wan3.0-video",
    wan3_default_config: dict | None = None,
    doubao_key: str | None = None,
    doubao_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    doubao_image_model: str = "doubao-seedream-5-0-pro-260628",
    doubao_video_model: str = "doubao-seedance-2-5-260628",
    doubao_default_config: dict | None = None,
    comfyui_url: str | None = None,
) -> None:
    """Initialize and register providers based on configuration.

    Args:
        mock: If True, register mock provider
        ollama_url: Ollama API URL (if provided, register Ollama provider)
        openai_key: OpenAI API key (if provided, register OpenAI provider)
        comfyui_url: ComfyUI API URL (if provided, register ComfyUI provider)
    """
    from backend.app.providers.base import ProviderCapabilities

    if mock:
        from backend.app.providers.mock_provider import MockProvider
        register_provider(MockProvider())

    if ollama_url:
        try:
            from backend.app.providers.ollama_provider import OllamaProvider
            register_provider(OllamaProvider(api_url=ollama_url))
        except Exception as e:
            logger.warning(f"Failed to register Ollama provider: {e}")

    if openai_key:
        try:
            from backend.app.providers.openai_provider import OpenAIProvider
            register_provider(OpenAIProvider(
                api_key=openai_key,
                api_url=openai_url,
                model=openai_model,
                image_model=openai_image_model,
            ))
        except Exception as e:
            logger.warning(f"Failed to register OpenAI provider: {e}")

    if openai_compat_key:
        try:
            from backend.app.providers.openai_compat_provider import OpenAICompatProvider
            register_provider(OpenAICompatProvider(
                api_key=openai_compat_key,
                api_url=openai_compat_url,
                model=openai_compat_model,
                display_name=openai_compat_name,
                auth_header=openai_compat_auth_header,
                auth_scheme=openai_compat_auth_scheme,
                max_tokens_param=openai_compat_max_tokens_param,
                default_config=openai_compat_default_config,
            ))
        except Exception as e:
            logger.warning(f"Failed to register OpenAI-compatible provider: {e}")

    if dashscope_key:
        try:
            from backend.app.providers.dashscope_provider import DashScopeProvider
            register_provider(DashScopeProvider(
                api_key=dashscope_key,
                api_url=dashscope_url,
                image_model=dashscope_image_model,
                default_config=dashscope_default_config,
            ))
        except Exception as e:
            logger.warning(f"Failed to register DashScope provider: {e}")

    if wan3_key:
        try:
            from backend.app.providers.wan3_provider import Wan3VideoProvider
            register_provider(Wan3VideoProvider(
                api_key=wan3_key,
                api_url=wan3_url,
                model=wan3_model,
                default_config=wan3_default_config,
            ))
        except Exception as e:
            logger.warning(f"Failed to register Wan3 provider: {e}")

    if doubao_key:
        try:
            from backend.app.providers.doubao_provider import DoubaoProvider
            register_provider(DoubaoProvider(
                api_key=doubao_key,
                api_url=doubao_url,
                image_model=doubao_image_model,
                video_model=doubao_video_model,
                default_config=doubao_default_config,
            ))
        except Exception as e:
            logger.warning(f"Failed to register Doubao provider: {e}")

    if comfyui_url:
        try:
            from backend.app.providers.comfyui_provider import ComfyUIProvider
            register_provider(ComfyUIProvider(api_url=comfyui_url))
        except Exception as e:
            logger.warning(f"Failed to register ComfyUI provider: {e}")
