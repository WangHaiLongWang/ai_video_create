"""Volcengine Ark provider for Seedream image and Seedance video generation."""

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


class DoubaoProvider(BaseProvider):
    """Generate images with Seedream and videos with Seedance via Ark.

    Ark deployments may expose a model name or an endpoint ID. Both are
    accepted as opaque configurable strings so newly released Seedance models
    do not require a code release.
    """

    name = "doubao"
    display_name = "Doubao Seedream / Seedance"
    capabilities = ProviderCapabilities(text=False, image=True, video=True)
    RATIOS = {"adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"}
    RESOLUTIONS = {"480p", "720p", "1080p"}

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        image_model: str = "doubao-seedream-4-0",
        video_model: str = "doubao-seedance-2-5",
        default_config: dict[str, Any] | None = None,
    ) -> None:
        if not api_key:
            raise ProviderNotConfiguredError(self.name, "api_key")
        if not image_model and not video_model:
            raise ProviderNotConfiguredError(self.name, "image_model or video_model")
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.image_model = image_model
        self.video_model = video_model
        self.default_config = default_config or {}
        self._client: httpx.AsyncClient | None = None
        self._last_external_job_id: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30, connect=10),
            )
        return self._client

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        raise ProviderError(self.name, "Doubao media provider does not generate text")

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        cfg = {**self.default_config, **(config or {})}
        if not prompt.strip():
            raise ProviderError(self.name, "Image prompt must not be empty")
        model = str(cfg.get("image_model", self.image_model)).strip()
        if not model:
            raise ProviderNotConfiguredError(self.name, "image_model")
        size = str(cfg.get("size", "1280x720"))
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": str(cfg.get("response_format", "b64_json")),
            "watermark": bool(cfg.get("watermark", False)),
        }
        if cfg.get("seed") is not None and int(cfg["seed"]) >= 0:
            payload["seed"] = int(cfg["seed"])
        if cfg.get("negative_prompt"):
            payload["negative_prompt"] = str(cfg["negative_prompt"])

        try:
            response = await (await self._get_client()).post(
                "/images/generations", json=payload, timeout=float(cfg.get("image_timeout", 300))
            )
            self._raise_for_status(response)
            data = response.json().get("data") or []
            if not data:
                raise ProviderError(self.name, "Seedream response contains no image")
            if data[0].get("b64_json"):
                return base64.b64decode(data[0]["b64_json"])
            if data[0].get("url"):
                return await self._download(str(data[0]["url"]), 120)
            raise ProviderError(self.name, "Seedream response contains no image data")
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(self.name, self.api_url, exc) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, f"Image generation failed: {exc}", exc) from exc

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        cfg = {**self.default_config, **(config or {})}
        if not prompt.strip() and not image_path:
            raise ProviderError(self.name, "prompt and image cannot both be empty")
        model = str(cfg.get("video_model", self.video_model)).strip()
        if not model:
            raise ProviderNotConfiguredError(self.name, "video_model")
        ratio = str(cfg.get("ratio", "adaptive"))
        resolution = str(cfg.get("resolution", "720p")).lower()
        duration = int(cfg.get("duration", 5))
        if ratio not in self.RATIOS:
            raise ProviderError(self.name, f"ratio must be one of {sorted(self.RATIOS)}")
        if resolution not in self.RESOLUTIONS:
            raise ProviderError(self.name, f"resolution must be one of {sorted(self.RESOLUTIONS)}")
        if duration not in {5, 10}:
            raise ProviderError(self.name, "duration must be 5 or 10 seconds")

        content: list[dict[str, Any]] = []
        if prompt.strip():
            content.append({"type": "text", "text": prompt})
        if image_path:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._image_data_url(image_path)},
            })
        payload: dict[str, Any] = {
            "model": model,
            "content": content,
            "ratio": ratio,
            "resolution": resolution,
            "duration": duration,
            "watermark": bool(cfg.get("watermark", False)),
        }
        if cfg.get("seed") is not None and int(cfg["seed"]) >= 0:
            payload["seed"] = int(cfg["seed"])
        if cfg.get("camera_fixed") is not None:
            payload["camera_fixed"] = bool(cfg["camera_fixed"])

        try:
            client = await self._get_client()
            response = await client.post("/contents/generations/tasks", json=payload)
            self._raise_for_status(response)
            body = response.json()
            task_id = body.get("id") or body.get("task_id")
            if not task_id:
                raise ProviderError(self.name, "Seedance response contains no task id")
            self._last_external_job_id = str(task_id)
            completed = await self._poll_video(
                client,
                str(task_id),
                float(cfg.get("timeout", 1800)),
                float(cfg.get("poll_interval", 5)),
            )
            video_url = self._extract_video_url(completed)
            if not video_url:
                raise ProviderError(self.name, "Seedance task completed without video URL")
            return await self._download(video_url, 300)
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(self.name, self.api_url, exc) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, f"Video generation failed: {exc}", exc) from exc

    async def _poll_video(
        self, client: httpx.AsyncClient, task_id: str, timeout: float, poll_interval: float
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/contents/generations/tasks/{task_id}")
            self._raise_for_status(response)
            body = response.json()
            status = str(body.get("status", "")).lower()
            if status in {"succeeded", "success", "completed"}:
                return body
            if status in {"failed", "cancelled", "canceled", "expired"}:
                error = body.get("error") or body.get("message") or status
                raise ProviderError(self.name, str(error))
            await asyncio.sleep(poll_interval)
        raise ProviderError(self.name, f"Seedance task timed out after {timeout:g}s")

    @staticmethod
    def _extract_video_url(body: dict[str, Any]) -> str | None:
        content = body.get("content") or body.get("output") or {}
        if isinstance(content, dict):
            return content.get("video_url") or content.get("url")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and (item.get("video_url") or item.get("url")):
                    return item.get("video_url") or item.get("url")
        return body.get("video_url") or body.get("url")

    @staticmethod
    def _image_data_url(image_path: str) -> str:
        path = Path(image_path).resolve()
        if not path.is_file():
            raise ProviderError("doubao", f"Input image not found: {image_path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ProviderError("doubao", "Input image must not exceed 20MB")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise ProviderError("doubao", f"Unsupported image format: {mime}")
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"

    async def _download(self, url: str, timeout: float) -> bytes:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            retry = response.headers.get("retry-after")
            raise ProviderRateLimitError(self.name, float(retry) if retry else None)
        if response.is_error:
            try:
                body = response.json()
                error = body.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else error
                message = message or body.get("message") or body.get("code")
            except Exception:
                message = None
            raise ProviderError(self.name, f"HTTP {response.status_code}: {message or response.text}")

    async def health_check(self) -> bool:
        try:
            response = await (await self._get_client()).get("/models")
            return response.status_code == 200
        except Exception:
            return False

    def get_external_job_id(self) -> str | None:
        return self._last_external_job_id

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
