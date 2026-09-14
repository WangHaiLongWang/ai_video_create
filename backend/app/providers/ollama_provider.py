"""Ollama provider — local LLM text generation."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
    ProviderNotConfiguredError,
)

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama provider for local LLM text generation.

    Uses the Ollama REST API to generate text with local models.
    """

    name = "ollama"
    capabilities = ProviderCapabilities(text=True, image=False, video=False)

    def __init__(self, api_url: str = "http://localhost:11434", model: str = "llama3.2"):
        """Initialize Ollama provider.

        Args:
            api_url: Ollama API base URL
            model: Model name to use for generation
        """
        self.api_url = api_url.rstrip("/")
        self.model = model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """Generate text using Ollama API.

        Args:
            prompt: Input prompt
            config: Optional config (temperature, max_tokens, etc.)

        Returns:
            Generated text

        Raises:
            ProviderError: If generation fails
        """
        config = config or {}

        payload = {
            "model": config.get("model", self.model),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config.get("temperature", 0.7),
                "num_predict": config.get("max_tokens", 2048),
            },
        }

        try:
            client = await self._get_client()
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except httpx.ConnectError as e:
            raise ProviderConnectionError(self.name, self.api_url, e)
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"HTTP error: {e.response.status_code}", e)
        except Exception as e:
            raise ProviderError(self.name, f"Text generation failed: {e}", e)

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        """Ollama does not support image generation."""
        raise ProviderError(self.name, "Ollama does not support image generation")

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        """Ollama does not support video generation."""
        raise ProviderError(self.name, "Ollama does not support video generation")

    async def health_check(self) -> bool:
        """Check if Ollama server is reachable.

        Returns:
            True if healthy
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models.

        Returns:
            List of model names
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models]
        except Exception:
            return []

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
