"""Alibaba Cloud Model Studio Wan3.0 video generation provider."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
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


class Wan3VideoProvider(BaseProvider):
    """Generate videos using the native asynchronous Wan3.0 API."""

    name = "wan3"
    capabilities = ProviderCapabilities(text=False, image=False, video=True)
    MODELS = {"wan3.0-video", "wan3.0-video-prime"}
    RESOLUTIONS = {"480P", "720P", "1080P"}
    RATIOS = {"adaptive", "16:9", "4:3", "1:1", "3:4", "9:16"}

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://dashscope.aliyuncs.com/api/v1",
        model: str = "wan3.0-video",
        default_config: dict[str, Any] | None = None,
    ) -> None:
        if not api_key:
            raise ProviderNotConfiguredError(self.name, "api_key")
        if model not in self.MODELS:
            raise ProviderError(self.name, f"Unsupported model: {model}")
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.model = model
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
        raise ProviderError(self.name, "Wan3 video provider does not generate text")

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        raise ProviderError(self.name, "Wan3 video provider does not generate images")

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        config = {**self.default_config, **(config or {})}
        model = str(config.get("model", self.model))
        if model not in self.MODELS:
            raise ProviderError(self.name, f"Unsupported model: {model}")
        if not prompt.strip() and not image_path:
            raise ProviderError(self.name, "prompt and media cannot both be empty")

        parameters = self._validate_parameters(config)
        input_data: dict[str, Any] = {"prompt": prompt}
        if image_path:
            input_data["media"] = [{
                "type": str(config.get("media_type", "first_frame")),
                "url": self._image_data_url(image_path),
            }]

        try:
            client = await self._get_client()
            response = await client.post(
                "/services/aigc/video-generation/video-synthesis",
                headers={"X-DashScope-Async": "enable"},
                json={"model": model, "input": input_data, "parameters": parameters},
            )
            self._raise_for_status(response)
            body = response.json()
            task_id = body.get("output", {}).get("task_id")
            if not task_id:
                raise ProviderError(self.name, "Wan3 response contains no task_id")

            output = await self._poll_task(
                client,
                task_id,
                timeout=float(config.get("timeout", 1800)),
                poll_interval=float(config.get("poll_interval", 5)),
            )
            video_url = output.get("video_url")
            if not video_url:
                results = output.get("results") or []
                video_url = (
                    results[0].get("video_url") or results[0].get("url")
                ) if results else None
            if not video_url:
                raise ProviderError(self.name, "Wan3 completed without video_url")

            # Wan3 result URLs are temporary. Persist the bytes immediately.
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as downloader:
                video_response = await downloader.get(video_url)
                video_response.raise_for_status()
                return video_response.content
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(self.name, self.api_url, exc) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(self.name, f"HTTP error: {exc.response.status_code}", exc) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, f"Video generation failed: {exc}", exc) from exc

    def _validate_parameters(self, config: dict[str, Any]) -> dict[str, Any]:
        resolution = str(config.get("resolution", "480P")).upper()
        ratio = str(config.get("ratio", "adaptive"))
        duration = int(config.get("duration", 5))
        seed = int(config.get("seed", -1))
        if resolution not in self.RESOLUTIONS:
            raise ProviderError(self.name, f"resolution must be one of {sorted(self.RESOLUTIONS)}")
        if ratio not in self.RATIOS:
            raise ProviderError(self.name, f"ratio must be one of {sorted(self.RATIOS)}")
        if duration != -1 and not 2 <= duration <= 30:
            raise ProviderError(self.name, "duration must be -1 or an integer between 2 and 30")
        if seed != -1 and not 0 <= seed <= 2147483647:
            raise ProviderError(self.name, "seed must be -1 or between 0 and 2147483647")
        return {
            "resolution": resolution,
            "ratio": ratio,
            "duration": duration,
            "audio": bool(config.get("audio", True)),
            "seed": seed,
            "prompt_extend": bool(config.get("prompt_extend", True)),
            "watermark": bool(config.get("watermark", False)),
        }

    def _image_data_url(self, image_path: str) -> str:
        path = Path(image_path).resolve()
        if not path.is_file():
            raise ProviderError(self.name, f"Input image not found: {image_path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ProviderError(self.name, "Input image must not exceed 20MB")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime not in {"image/jpeg", "image/png", "image/bmp", "image/webp"}:
            raise ProviderError(self.name, f"Unsupported image format: {mime}")
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"

    async def _poll_task(
        self, client: httpx.AsyncClient, task_id: str, timeout: float, poll_interval: float
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/tasks/{task_id}")
            self._raise_for_status(response)
            body = response.json()
            output = body.get("output", {})
            status = str(output.get("task_status", "")).upper()
            if status == "SUCCEEDED":
                return output
            if status in {"FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}:
                message = body.get("message") or output.get("message") or status
                raise ProviderError(self.name, str(message))
            await asyncio.sleep(poll_interval)
        raise ProviderError(self.name, f"Wan3 task timed out after {timeout:g}s")

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

    async def health_check(self) -> bool:
        """Validate the key without starting a billable video task."""
        try:
            root = self.api_url.split("/api/v1", 1)[0]
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}, timeout=15
            ) as client:
                response = await client.get(f"{root}/compatible-mode/v1/models")
                return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
