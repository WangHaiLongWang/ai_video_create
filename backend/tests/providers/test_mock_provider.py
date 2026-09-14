"""Tests for mock provider."""

import pytest
from backend.app.providers.mock_provider import MockProvider


class TestMockProvider:
    """Tests for MockProvider."""

    def setup_method(self):
        """Create mock provider instance."""
        self.provider = MockProvider(delay=0.01)

    def test_name(self):
        """Test provider name."""
        assert self.provider.name == "mock"

    def test_capabilities(self):
        """Test provider capabilities."""
        caps = self.provider.capabilities
        assert caps.text is True
        assert caps.image is True
        assert caps.video is True

    @pytest.mark.asyncio
    async def test_generate_text(self):
        """Test text generation."""
        result = await self.provider.generate_text("test prompt")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_text_storyboard(self):
        """Test storyboard text generation."""
        result = await self.provider.generate_text("generate storyboard scenes")
        assert isinstance(result, str)
        assert "scene" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_image(self):
        """Test image generation returns valid PNG."""
        result = await self.provider.generate_image("test image")
        assert isinstance(result, bytes)
        # Check PNG signature
        assert result[:8] == b'\x89PNG\r\n\x1a\n'

    @pytest.mark.asyncio
    async def test_generate_video(self):
        """Test video generation returns valid MP4."""
        result = await self.provider.generate_video("/fake/path.png", "test video")
        assert isinstance(result, bytes)
        # Check MP4 ftyp box
        assert b'ftyp' in result

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check always returns True."""
        assert await self.provider.health_check() is True

    @pytest.mark.asyncio
    async def test_respects_delay(self):
        """Test that provider respects configured delay."""
        import time
        provider = MockProvider(delay=0.1)
        start = time.time()
        await provider.generate_text("test")
        elapsed = time.time() - start
        assert elapsed >= 0.05  # Allow some tolerance
