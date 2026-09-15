"""Configurable OpenAI-compatible text generation provider."""

from __future__ import annotations

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


class OpenAICompatProvider(BaseProvider):
    """Text-only Chat Completions provider with configurable authentication."""

    name = "openai_compat"
    capabilities = ProviderCapabilities(text=True, image=False, video=False)
    TOKEN_PARAMS = {"max_tokens", "max_completion_tokens"}

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str,
        *,
        display_name: str = "OpenAI Compatible",
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        max_tokens_param: str = "max_tokens",
        default_config: dict[str, Any] | None = None,
    ) -> None:
        if not api_key:
            raise ProviderNotConfiguredError(self.name, "api_key")
        if not api_url.startswith(("https://", "http://")):
            raise ProviderError(self.name, "api_url must use http or https")
        if not model.strip():
            raise ProviderNotConfiguredError(self.name, "model")
        if not auth_header.strip() or "\r" in auth_header or "\n" in auth_header:
            raise ProviderError(self.name, "invalid auth_header")
        if max_tokens_param not in self.TOKEN_PARAMS:
            raise ProviderError(
                self.name,
                f"max_tokens_param must be one of {sorted(self.TOKEN_PARAMS)}",
            )
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.display_name = display_name
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme.strip()
        self.max_tokens_param = max_tokens_param
        self.default_config = default_config or {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            auth_value = (
                f"{self.auth_scheme} {self.api_key}"
                if self.auth_scheme else self.api_key
            )
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    self.auth_header: auth_value,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(
                    float(self.default_config.get("timeout", 120)), connect=10
                ),
            )
        return self._client

    async def generate_text(
        self, prompt: str, config: dict[str, Any] | None = None
    ) -> str:
        config = {**self.default_config, **(config or {})}
        messages: list[dict[str, str]] = []
        if config.get("system_prompt"):
            messages.append({"role": "system", "content": str(config["system_prompt"])})
        messages.append({"role": "user", "content": prompt})

        token_param = str(config.get("max_tokens_param", self.max_tokens_param))
        if token_param not in self.TOKEN_PARAMS:
            raise ProviderError(self.name, f"unsupported token parameter: {token_param}")
        payload: dict[str, Any] = {
            "model": config.get("model", self.model),
            "messages": messages,
            "temperature": float(config.get("temperature", 1.0)),
            "top_p": float(config.get("top_p", 0.95)),
            token_param: int(config.get("max_tokens", 4096)),
            "stream": False,
        }
        for key in ("frequency_penalty", "presence_penalty", "stop"):
            if key in config:
                payload[key] = config[key]

        try:
            client = await self._get_client()
            response = await client.post("/chat/completions", json=payload)
            if response.status_code == 429:
                retry = response.headers.get("retry-after")
                raise ProviderRateLimitError(
                    self.name, float(retry) if retry else None
                )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"].get("content")
            if content is None:
                raise ProviderError(self.name, "response contains no message content")
            return str(content)
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(self.name, self.api_url, exc) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                self.name, f"HTTP error: {exc.response.status_code}", exc
            ) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, f"Text generation failed: {exc}", exc) from exc

    async def generate_image(
        self, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        raise ProviderError(self.name, "OpenAI-compatible text provider does not generate images")

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        raise ProviderError(self.name, "OpenAI-compatible text provider does not generate videos")

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

