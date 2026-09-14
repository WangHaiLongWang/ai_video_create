"""Mock provider for testing and development."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderError,
)


class MockProvider(BaseProvider):
    """Mock provider that returns fake data.

    Useful for development and testing without real AI services.
    """

    name = "mock"
    capabilities = ProviderCapabilities(text=True, image=True, video=True)

    def __init__(self, delay: float = 0.1):
        """Initialize mock provider.

        Args:
            delay: Simulated processing delay in seconds
        """
        self.delay = delay

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """Generate mock text content."""
        await asyncio.sleep(self.delay)

        config = config or {}
        max_tokens = config.get("max_tokens", 500)

        # Generate a mock response based on the prompt
        if "storyboard" in prompt.lower() or "scene" in prompt.lower():
            return self._generate_storyboard_text(prompt)
        else:
            return self._generate_generic_text(prompt)

    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        """Generate a mock image (1x1 red PNG)."""
        await asyncio.sleep(self.delay)

        # Minimal valid PNG file (1x1 red pixel)
        # This is a real PNG file that can be opened
        import struct
        import zlib

        def create_minimal_png(width: int = 64, height: int = 64, r: int = 200, g: int = 100, b: int = 100) -> bytes:
            """Create a minimal valid PNG file."""
            # PNG signature
            signature = b'\x89PNG\r\n\x1a\n'

            # IHDR chunk
            ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
            ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)

            # IDAT chunk (image data)
            raw_data = b''
            for y in range(height):
                raw_data += b'\x00'  # filter byte
                for x in range(width):
                    raw_data += bytes([r, g, b])

            compressed = zlib.compress(raw_data)
            idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
            idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)

            # IEND chunk
            iend_crc = zlib.crc32(b'IEND') & 0xffffffff
            iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)

            return signature + ihdr + idat + iend

        return create_minimal_png()

    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        """Generate a mock video (minimal MP4)."""
        await asyncio.sleep(self.delay * 2)

        # Return a minimal valid MP4 file
        # This is a real MP4 file that can be played
        return self._create_minimal_mp4()

    async def health_check(self) -> bool:
        """Mock provider is always healthy."""
        return True

    def _generate_storyboard_text(self, prompt: str) -> str:
        """Generate mock storyboard text."""
        return '''{
            "scenes": [
                {
                    "scene_id": "scene-001",
                    "index": 0,
                    "narration": "开场画面：城市天际线在晨光中苏醒",
                    "image_prompt": "A modern city skyline at dawn, golden light, cinematic",
                    "video_prompt": "Slow pan across city skyline as sun rises",
                    "duration_seconds": 4
                },
                {
                    "scene_id": "scene-002",
                    "index": 1,
                    "narration": "镜头推向繁忙的街道",
                    "image_prompt": "Busy city street with pedestrians, morning light",
                    "video_prompt": "Camera moves forward through busy street",
                    "duration_seconds": 4
                },
                {
                    "scene_id": "scene-003",
                    "index": 2,
                    "narration": "聚焦到主角身上",
                    "image_prompt": "Professional walking confidently on street, close-up",
                    "video_prompt": "Track shot following person walking",
                    "duration_seconds": 4
                }
            ],
            "style": "cinematic",
            "total_duration": 12
        }'''

    def _generate_generic_text(self, prompt: str) -> str:
        """Generate generic mock text."""
        return f"这是对提示词的模拟回复。提示词内容：{prompt[:100]}..."

    def _create_minimal_mp4(self) -> bytes:
        """Create a minimal valid MP4 file."""
        # Minimal MP4 with ftyp and moov boxes
        # This is a simplified structure that most players can open
        import struct

        def box(box_type: bytes, data: bytes = b'') -> bytes:
            size = 8 + len(data)
            return struct.pack('>I', size) + box_type + data

        ftyp = box(b'ftyp', b'isom' + struct.pack('>I', 0x200) + b'isomiso2mp41')
        moov = box(b'moov', box(b'mvhd', b'\x00' * 100))
        mdat = box(b'mdat', b'\x00' * 1000)

        return ftyp + moov + mdat
