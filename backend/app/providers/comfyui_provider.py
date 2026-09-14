"""ComfyUI provider — image and video generation via ComfyUI API."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import httpx

from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderConnectionError,
    ProviderError,
)

logger = logging.getLogger(__name__)


class ComfyUIProvider(BaseProvider):
    """ComfyUI provider for image and video generation.

    Uses ComfyUI's REST API to execute workflows for image/video generation.
    """

    name = "comfyui"
    capabilities = ProviderCapabilities(text=False, image=True, video=True)

    def __init__(
        self,
        api_url: str = "http://localhost:8188",
        client_id: str | None = None,
    ):
        """Initialize ComfyUI provider.

        Args:
            api_url: ComfyUI API base URL
            client_id: Client ID for WebSocket connection
        """
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id or f"ai_video_create-{uuid.uuid4().hex[:8]}"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
        return self._client

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """ComfyUI does not support text generation."""
        raise ProviderError(self.name, "ComfyUI does not support text generation")

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        """Generate image using ComfyUI workflow.

        Args:
            prompt: Image description prompt
            config: Optional config (workflow_id, checkpoint, sampler, steps, etc.)

        Returns:
            Image data as bytes (PNG)

        Raises:
            ProviderError: If generation fails
        """
        config = config or {}

        # Build a basic txt2img workflow
        workflow = self._build_txt2img_workflow(prompt, config)

        # Execute workflow
        image_data = await self._execute_workflow(workflow, output_type="image")

        if not image_data:
            raise ProviderError(self.name, "No image output from workflow")

        return image_data[0]

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        """Generate video using ComfyUI img2vid workflow.

        Args:
            image_path: Path to input image
            prompt: Video motion description
            config: Optional config (workflow_id, frames, fps, etc.)

        Returns:
            Video data as bytes (MP4/GIF)

        Raises:
            ProviderError: If generation fails
        """
        config = config or {}

        # Build img2vid workflow
        workflow = self._build_img2vid_workflow(image_path, prompt, config)

        # Execute workflow
        video_data = await self._execute_workflow(workflow, output_type="video")

        if not video_data:
            raise ProviderError(self.name, "No video output from workflow")

        return video_data[0]

    async def _execute_workflow(
        self, workflow: dict, output_type: str = "image", timeout: float = 300.0
    ) -> list[bytes]:
        """Execute a ComfyUI workflow and retrieve outputs.

        Args:
            workflow: ComfyUI workflow dictionary
            output_type: Expected output type (image/video)
            timeout: Maximum wait time in seconds

        Returns:
            List of output data bytes

        Raises:
            ProviderError: If execution fails
        """
        try:
            client = await self._get_client()

            # Queue workflow
            payload = {
                "prompt": workflow,
                "client_id": self.client_id,
            }
            response = await client.post("/prompt", json=payload)
            response.raise_for_status()

            prompt_id = response.json()["prompt_id"]

            # Poll for completion
            outputs = await self._wait_for_completion(prompt_id, timeout)

            # Download outputs
            result_data = []
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        data = await self._download_output(img["filename"], img["subfolder"], img["type"])
                        result_data.append(data)
                if "gifs" in node_output:
                    for gif in node_output["gifs"]:
                        data = await self._download_output(gif["filename"], gif["subfolder"], gif["type"])
                        result_data.append(data)

            return result_data

        except httpx.ConnectError as e:
            raise ProviderConnectionError(self.name, self.api_url, e)
        except httpx.HTTPStatusError as e:
            raise ProviderError(self.name, f"HTTP error: {e.response.status_code}", e)
        except Exception as e:
            raise ProviderError(self.name, f"Workflow execution failed: {e}", e)

    async def _wait_for_completion(self, prompt_id: str, timeout: float) -> dict:
        """Wait for workflow completion by polling history."""
        client = await self._get_client()
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise ProviderError(self.name, f"Workflow timed out after {timeout}s")

            response = await client.get(f"/history/{prompt_id}")
            if response.status_code == 200:
                history = response.json()
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("status", {}).get("completed", False):
                        return entry.get("outputs", {})
                    if entry.get("status", {}).get("status_str") == "error":
                        raise ProviderError(self.name, "Workflow execution failed")

            await asyncio.sleep(1.0)

    async def _download_output(self, filename: str, subfolder: str, file_type: str) -> bytes:
        """Download output file from ComfyUI."""
        client = await self._get_client()

        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": file_type,
        }
        response = await client.get("/view", params=params)
        response.raise_for_status()
        return response.content

    def _build_txt2img_workflow(self, prompt: str, config: dict) -> dict:
        """Build a basic txt2img workflow for ComfyUI."""
        checkpoint = config.get("checkpoint", "sd_xl_base_1.0.safetensors")
        sampler = config.get("sampler", "euler")
        steps = config.get("steps", 20)
        cfg = config.get("cfg", 7.0)
        width = config.get("width", 1024)
        height = config.get("height", 768)
        seed = config.get("seed", -1)
        if seed == -1:
            import random
            seed = random.randint(0, 2**32 - 1)

        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "low quality, blurry, distorted", "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "ai_video_create", "images": ["8", 0]},
            },
        }

    def _build_img2vid_workflow(self, image_path: str, prompt: str, config: dict) -> dict:
        """Build an img2vid workflow for ComfyUI.

        Note: This requires AnimateDiff or similar extension.
        This is a basic template that needs to be customized.
        """
        # This is a placeholder - actual workflow depends on installed extensions
        return {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": image_path},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt},
            },
        }

    async def health_check(self) -> bool:
        """Check if ComfyUI server is reachable."""
        try:
            client = await self._get_client()
            response = await client.get("/system_stats")
            return response.status_code == 200
        except Exception:
            return False

    async def get_system_stats(self) -> dict:
        """Get ComfyUI system statistics."""
        try:
            client = await self._get_client()
            response = await client.get("/system_stats")
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
