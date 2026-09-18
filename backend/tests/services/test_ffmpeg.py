"""Tests for FFmpeg service."""

import asyncio
import os
import tempfile
import shutil
import pytest
from backend.app.services.ffmpeg import (
    FFmpegService,
    FFmpegError,
    is_ffmpeg_available,
    get_ffmpeg_path,
)


class TestFFmpegService:
    """Tests for FFmpegService."""

    def setup_method(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        # Use the discovered ffmpeg path so that imageio-ffmpeg or other
        # non-PATH installations are picked up on all platforms.
        self.service = FFmpegService(ffmpeg_path=get_ffmpeg_path() or "ffmpeg")

    def teardown_method(self):
        """Cleanup temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_check_ffmpeg_available(self):
        """Test checking FFmpeg availability."""
        # This will be True or False depending on system
        result = await self.service.check_ffmpeg_available()
        assert isinstance(result, bool)

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_create_test_video(self):
        """Test creating a test video."""
        output_path = os.path.join(self.temp_dir, "test.mp4")
        result = await self.service.create_test_video(output_path, duration=1.0)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_concatenate_videos(self):
        """Test concatenating videos."""
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

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_image_to_video(self):
        """Test converting image to video."""
        # Create a valid test image using ffmpeg itself (avoids invalid PNG bytes)
        png_path = os.path.join(self.temp_dir, "test.png")
        create_cmd = [
            self.service.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", "color=c=red:s=320x240:d=1",
            "-frames:v", "1", png_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *create_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode != 0 or not os.path.exists(png_path):
            pytest.skip("Could not create test image via FFmpeg")

        output_path = os.path.join(self.temp_dir, "output.mp4")

        result = await self.service.image_to_video(png_path, output_path, duration=1.0, fps=12)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_image_to_video_missing_image_raises(self):
        """Test image_to_video with missing image raises error."""
        with pytest.raises(FFmpegError) as exc_info:
            await self.service.image_to_video(
                "/nonexistent/image.png",
                os.path.join(self.temp_dir, "output.mp4"),
            )
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_get_video_info(self):
        """Test getting video info."""
        video_path = os.path.join(self.temp_dir, "info_test.mp4")
        await self.service.create_test_video(video_path, duration=1.0)

        info = await self.service.get_video_info(video_path)
        assert "path" in info
        assert "size" in info
        assert info["size"] > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_get_video_info_missing_file_raises(self):
        """Test get_video_info with missing file raises error."""
        with pytest.raises(FFmpegError) as exc_info:
            await self.service.get_video_info("/nonexistent/video.mp4")
        assert "not found" in str(exc_info.value).lower()

    def test_parse_duration(self):
        """Test duration parsing."""
        assert self.service._parse_duration("01:30:00.00") == 5400.0
        assert self.service._parse_duration("00:01:30.00") == 90.0
        assert self.service._parse_duration("00:00:05.00") == 5.0


class TestFFmpegDiscovery:
    """Tests for module-level FFmpeg discovery helpers."""

    def test_is_ffmpeg_available_returns_bool(self):
        """is_ffmpeg_available always returns a boolean."""
        result = is_ffmpeg_available()
        assert isinstance(result, bool)

    def test_get_ffmpeg_path_returns_str_or_none(self):
        """get_ffmpeg_path returns a string path or None."""
        result = get_ffmpeg_path()
        assert result is None or isinstance(result, str)

    def test_get_ffmpeg_path_cached(self):
        """Repeated calls to get_ffmpeg_path return the same value."""
        from backend.app.services import ffmpeg as ffmpeg_mod
        # Reset cache
        ffmpeg_mod._ffmpeg_discovered_path = None
        first = get_ffmpeg_path()
        second = get_ffmpeg_path()
        assert first == second
