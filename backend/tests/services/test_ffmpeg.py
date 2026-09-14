"""Tests for FFmpeg service."""

import os
import tempfile
import shutil
import pytest
from backend.app.services.ffmpeg import FFmpegService, FFmpegError


class TestFFmpegService:
    """Tests for FFmpegService."""

    def setup_method(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.service = FFmpegService()

    def teardown_method(self):
        """Cleanup temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_check_ffmpeg_available(self):
        """Test checking FFmpeg availability."""
        # This will be True or False depending on system
        result = await self.service.check_ffmpeg_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_create_test_video(self):
        """Test creating a test video."""
        output_path = os.path.join(self.temp_dir, "test.mp4")

        # Skip if FFmpeg not available
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        result = await self.service.create_test_video(output_path, duration=1.0)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    @pytest.mark.asyncio
    async def test_concatenate_videos(self):
        """Test concatenating videos."""
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        # Create test videos
        video1 = os.path.join(self.temp_dir, "v1.mp4")
        video2 = os.path.join(self.temp_dir, "v2.mp4")
        output = os.path.join(self.temp_dir, "concat.mp4")

        await self.service.create_test_video(video1, duration=1.0)
        await self.service.create_test_video(video2, duration=1.0)

        result = await self.service.concatenate_videos([video1, video2], output)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    @pytest.mark.asyncio
    async def test_concatenate_empty_list_raises(self):
        """Test concatenating empty list raises error."""
        with pytest.raises(FFmpegError) as exc_info:
            await self.service.concatenate_videos([], "output.mp4")
        assert "No input" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_image_to_video(self):
        """Test converting image to video."""
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        # Create a minimal PNG file
        png_path = os.path.join(self.temp_dir, "test.png")
        with open(png_path, "wb") as f:
            # Minimal 1x1 PNG
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        output_path = os.path.join(self.temp_dir, "output.mp4")

        result = await self.service.image_to_video(png_path, output_path, duration=2.0)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    @pytest.mark.asyncio
    async def test_image_to_video_missing_image_raises(self):
        """Test image_to_video with missing image raises error."""
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        with pytest.raises(FFmpegError) as exc_info:
            await self.service.image_to_video(
                "/nonexistent/image.png",
                os.path.join(self.temp_dir, "output.mp4"),
            )
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_video_info(self):
        """Test getting video info."""
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        video_path = os.path.join(self.temp_dir, "info_test.mp4")
        await self.service.create_test_video(video_path, duration=1.0)

        info = await self.service.get_video_info(video_path)
        assert "path" in info
        assert "size" in info
        assert info["size"] > 0

    @pytest.mark.asyncio
    async def test_get_video_info_missing_file_raises(self):
        """Test get_video_info with missing file raises error."""
        if not await self.service.check_ffmpeg_available():
            pytest.skip("FFmpeg not available")

        with pytest.raises(FFmpegError) as exc_info:
            await self.service.get_video_info("/nonexistent/video.mp4")
        assert "not found" in str(exc_info.value).lower()

    def test_parse_duration(self):
        """Test duration parsing."""
        assert self.service._parse_duration("01:30:00.00") == 5400.0
        assert self.service._parse_duration("00:01:30.00") == 90.0
        assert self.service._parse_duration("00:00:05.00") == 5.0
