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
    dashscope_key: str | None = None,
    dashscope_url: str = "https://dashscope.aliyuncs.com/api/v1",
    dashscope_image_model: str = "qwen-image-3.0",
    dashscope_default_config: dict | None = None,
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

    if comfyui_url:
        try:
            from backend.app.providers.comfyui_provider import ComfyUIProvider
            register_provider(ComfyUIProvider(api_url=comfyui_url))
        except Exception as e:
            logger.warning(f"Failed to register ComfyUI provider: {e}")
