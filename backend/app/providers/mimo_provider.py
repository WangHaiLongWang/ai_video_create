"""MiMo text provider -- wraps an OpenAI-compatible endpoint for MiMo models."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.providers.base import BaseProvider, ProviderCapabilities, ProviderError

logger = logging.getLogger(__name__)


class MiMoTextProvider(BaseProvider):
    """Provider for MiMo models via OpenAI-compatible API."""

    name = "mimo"
    capabilities = ProviderCapabilities(text=True, image=False, video=False)

    def __init__(
        self,
        api_key: str = "",
        api_url: str = "https://api.mimo.com/v1",
        model: str = "MiMo-7B-RL",
        display_name: str = "MiMo",
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.display_name = display_name

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """Generate text via MiMo API (OpenAI-compatible chat endpoint)."""
        import httpx

        config = config or {}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise ProviderError(self.name, f"Text generation failed: {exc}", cause=exc)

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        raise ProviderError(self.name, "Image generation not supported")

    async def generate_video(self, image_path: str, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        raise ProviderError(self.name, "Video generation not supported")
