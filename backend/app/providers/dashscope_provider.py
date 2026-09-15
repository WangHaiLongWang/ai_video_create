"""DashScope provider for asynchronous Qwen image generation."""

from __future__ import annotations

import asyncio
import base64
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


class DashScopeProvider(BaseProvider):
    """Generate Qwen images through DashScope's native async API."""

    name = "dashscope"
    capabilities = ProviderCapabilities(text=False, image=True, video=False)

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://dashscope.aliyuncs.com/api/v1",
        image_model: str = "qwen-image-3.0",
        default_config: dict[str, Any] | None = None,
    ) -> None:
        if not api_key:
            raise ProviderNotConfiguredError(self.name, "api_key")
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.image_model = image_model.lower()
        self.default_config = default_config or {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        raise ProviderError(self.name, "DashScope image provider does not generate text")

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        raise ProviderError(self.name, "DashScope image provider does not generate video")

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        config = {**self.default_config, **(config or {})}
        if not prompt.strip():
            raise ProviderError(self.name, "Image prompt must not be empty")
        size = str(config.get("size", "1280x720")).replace("×", "*").replace("x", "*")
        self._validate_size(size)
        model = str(config.get("image_model", self.image_model)).lower()
        if model not in {"qwen-image-3.0", "qwen-image-3.0-pro"}:
            raise ProviderError(self.name, f"Unsupported Qwen Image 3.0 model: {model}")
        parameters: dict[str, Any] = {
            "size": size,
            "prompt_extend": config.get("prompt_extend", True),
            "prompt_extend_mode": config.get("prompt_extend_mode", "direct"),
            "enable_thinking": config.get("enable_thinking", True),
            "watermark": config.get("watermark", False),
        }
        if config.get("negative_prompt"):
            parameters["negative_prompt"] = config["negative_prompt"]
        if config.get("seed") is not None:
            seed = int(config["seed"])
            if seed < 0 or seed > 2147483647:
                raise ProviderError(self.name, "seed must be between 0 and 2147483647")
            parameters["seed"] = seed
        payload = {
            "model": model,
            "input": {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
            },
            "parameters": parameters,
        }
        timeout_seconds = float(config.get("generation_timeout", 600))
        poll_interval = float(config.get("poll_interval", 2))

        try:
            client = await self._get_client()
            if config.get("use_async", False):
                response = await client.post(
                    "/services/aigc/image-generation/generation",
                    json=payload,
                    headers={"X-DashScope-Async": "enable"},
                )
            else:
                # Qwen Image 3.0 official recommendation for most requests.
                response = await client.post(
                    "/services/aigc/multimodal-generation/generation",
                    json=payload,
                    timeout=timeout_seconds,
                )
            self._raise_for_status(response)
            body = response.json()
            output = body.get("output", {})
            task_id = output.get("task_id")
            if task_id:
                output = await self._poll_task(client, task_id, timeout_seconds, poll_interval)
            image_url, image_b64 = self._extract_image(output)
            if image_b64:
                return base64.b64decode(image_b64)
            if image_url:
                # Signed object-storage URLs do not need the DashScope API key.
                async with httpx.AsyncClient(timeout=60, follow_redirects=True) as downloader:
                    image_response = await downloader.get(image_url)
                    image_response.raise_for_status()
                    return image_response.content
            raise ProviderError(self.name, "DashScope response contains no image")
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(self.name, self.api_url, exc) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(self.name, f"HTTP error: {exc.response.status_code}", exc) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, f"Image generation failed: {exc}", exc) from exc

    async def _poll_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        timeout_seconds: float,
        poll_interval: float,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/tasks/{task_id}")
            self._raise_for_status(response)
            body = response.json()
            output = body.get("output", {})
            status = str(output.get("task_status", "")).upper()
            if status == "SUCCEEDED":
                return output
            if status in {"FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}:
                message = body.get("message") or output.get("message") or f"task {status.lower()}"
                raise ProviderError(self.name, str(message))
            await asyncio.sleep(poll_interval)
        raise ProviderError(self.name, f"Image generation timed out after {timeout_seconds:g}s")

    @staticmethod
    def _extract_image(output: dict[str, Any]) -> tuple[str | None, str | None]:
        results = output.get("results") or []
        if results:
            return results[0].get("url"), results[0].get("b64_json")
        choices = output.get("choices") or []
        if choices:
            content = choices[0].get("message", {}).get("content", [])
            for item in content:
                url = item.get("image") or item.get("url")
                b64_data = item.get("b64_json")
                if url or b64_data:
                    return url, b64_data
        return None, None

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            retry = response.headers.get("retry-after")
            raise ProviderRateLimitError(self.name, float(retry) if retry else None)
        if response.is_error:
            try:
                body = response.json()
                message = body.get("message") or body.get("code")
            except Exception:
                message = None
            if message:
                raise ProviderError(self.name, f"HTTP {response.status_code}: {message}")
            response.raise_for_status()

    @staticmethod
    def _validate_size(size: str) -> None:
        if size == "auto":
            return
        try:
            width, height = (int(value) for value in size.split("*", 1))
        except (TypeError, ValueError):
            raise ProviderError("dashscope", "size must use WIDTHxHEIGHT or WIDTH*HEIGHT")
        pixels = width * height
        if pixels < 512 * 512 or pixels > 2048 * 2048:
            raise ProviderError("dashscope", "image pixels must be between 512x512 and 2048x2048")
        ratio = width / height
        if ratio < 1 / 8 or ratio > 8:
            raise ProviderError("dashscope", "image aspect ratio must be between 1:8 and 8:1")

    async def health_check(self) -> bool:
        try:
            root = self.api_url.split("/api/v1", 1)[0]
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}, timeout=15
            ) as client:
                response = await client.get(f"{root}/compatible-mode/v1/models")
                if response.status_code != 200:
                    return False
                models = {item.get("id") for item in response.json().get("data", [])}
                return self.image_model in models
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
