"""OpenAI provider — GPT text and DALL-E image generation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI provider for text and image generation.

    Uses OpenAI API for GPT text and DALL-E image generation.
    """

    name = "openai"
    capabilities = ProviderCapabilities(text=True, image=True, video=False)

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        image_model: str = "dall-e-3",
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            api_url: API base URL
            model: Text model (e.g., gpt-4)
            image_model: Image model (e.g., dall-e-3)
        """
        if not api_key:
            raise ProviderNotConfiguredError(self.name, "api_key")

        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.image_model = image_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth headers."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """Generate text using Chat Completions API.

        Args:
            prompt: Input prompt
            config: Optional config (temperature, max_tokens, system_prompt, etc.)

        Returns:
            Generated text

        Raises:
            ProviderError: If generation fails
        """
        config = config or {}

        messages = []
        if "system_prompt" in config:
            messages.append({"role": "system", "content": config["system_prompt"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": config.get("model", self.model),
            "messages": messages,
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
        }

        try:
            client = await self._get_client()
            response = await client.post("/chat/completions", json=payload)

            if response.status_code == 429:
                retry_after = None
                if "retry-after" in response.headers:
                    retry_after = float(response.headers["retry-after"])
                raise ProviderRateLimitError(self.name, retry_after)

            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except httpx.ConnectError as e:
            raise ProviderConnectionError(self.name, self.api_url, e)
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"HTTP error: {e.response.status_code}", e)
        except ProviderRateLimitError:
            raise
        except Exception as e:
            raise ProviderError(self.name, f"Text generation failed: {e}", e)

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        """Generate image using DALL-E API.

        Args:
            prompt: Image description prompt
            config: Optional config (size, quality, style, etc.)

        Returns:
            Image data as bytes (PNG)

        Raises:
            ProviderError: If generation fails
        """
        config = config or {}

        payload = {
            "model": config.get("image_model", self.image_model),
            "prompt": prompt,
            "n": 1,
            "size": config.get("size", "1792x1024"),
            "quality": config.get("quality", "hd"),
            "style": config.get("style", "vivid"),
            "response_format": "b64_json",
        }

        try:
            client = await self._get_client()
            response = await client.post("/images/generations", json=payload)

            if response.status_code == 429:
                retry_after = None
                if "retry-after" in response.headers:
                    retry_after = float(response.headers["retry-after"])
                raise ProviderRateLimitError(self.name, retry_after)

            response.raise_for_status()

            result = response.json()
            import base64
            b64_data = result["data"][0]["b64_json"]
            return base64.b64decode(b64_data)

        except httpx.ConnectError as e:
            raise ProviderConnectionError(self.name, self.api_url, e)
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"HTTP error: {e.response.status_code}", e)
        except ProviderRateLimitError:
            raise
        except Exception as e:
            raise ProviderError(self.name, f"Image generation failed: {e}", e)

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        """OpenAI does not natively support video generation."""
        raise ProviderError(self.name, "OpenAI does not support video generation")

    async def health_check(self) -> bool:
        """Check if API key is valid by listing models.

        Returns:
            True if healthy
        """
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
