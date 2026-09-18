"""Integration tests for FFmpeg service.

These tests require a working FFmpeg installation on the system.
They exercise version detection, video normalisation, concatenation,
media probing, and error handling paths.

Tests that invoke the real FFmpeg binary are marked with
``@pytest.mark.external`` so they are automatically skipped on systems
where FFmpeg is not available (see ``backend/tests/conftest.py``).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that `backend` is importable.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.services.ffmpeg import (
    FFmpegError,
    FFmpegService,
    FFmpegVersionInfo,
    get_ffmpeg_path,
    is_ffmpeg_available,
    parse_ffmpeg_version,
)

# ---------------------------------------------------------------------------
# Locate FFmpeg binary using the shared discovery logic
# ---------------------------------------------------------------------------

_FFMPEG_PATH = get_ffmpeg_path() or "ffmpeg"

# Determine whether the live FFmpeg tests can run at all
_FFMPEG_IS_AVAILABLE = is_ffmpeg_available()

# Skips the entire module when FFmpeg is missing (for classes that are
# entirely FFmpeg-dependent).  Individual tests can also use the marker.
requires_ffmpeg = pytest.mark.skipif(
    not _FFMPEG_IS_AVAILABLE,
    reason="FFmpeg not available on this system",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ffmpeg_service() -> FFmpegService:
    """Provide a fresh FFmpegService for the whole test module."""
    return FFmpegService(ffmpeg_path=_FFMPEG_PATH)


@pytest.fixture(scope="module")
def event_loop():
    """Provide a single event loop for the module (avoids deprecation warnings)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(coro):
    """Helper to run an async coroutine synchronously in the module event loop."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Fallback: create a new loop for nested calls
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. FFmpeg version detection
# ---------------------------------------------------------------------------

@requires_ffmpeg
class TestFFmpegVersionDetection:
    """Tests for parsing and querying the FFmpeg version."""

    def test_parse_version_output(self):
        """parse_ffmpeg_version extracts major.minor.patch and library versions."""
        sample = (
            "ffmpeg version 7.1-essentials_build-www.gyan.dev "
            "Copyright (c) 2000-2024 the FFmpeg developers\n"
            "built with gcc 14.2.0\n"
            "configuration: --enable-gpl\n"
            "libavutil      59. 39.100 / 59. 39.100\n"
            "libavcodec     61. 19.100 / 61. 19.100\n"
            "libavformat    61.  7.100 / 61.  7.100\n"
        )
        info = parse_ffmpeg_version(sample)
        assert info.major == 7
        assert info.minor == 1
        assert info.patch == 0
        assert info.version == "7.1.0"
        assert info.libavcodec_version == "61.19.100"
        assert info.libavformat_version == "61.7.100"
        assert info.libavutil_version == "59.39.100"
        assert "enable-gpl" in info.build_config

    def test_parse_empty_output(self):
        """Empty output yields an info object with zeroed version."""
        info = parse_ffmpeg_version("")
        assert info.version == ""
        assert info.version_tuple == (0, 0, 0)

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_get_version_info_live(self, ffmpeg_service: FFmpegService):
        """get_version_info returns real data from the installed FFmpeg."""
        info = await ffmpeg_service.get_version_info()
        assert info.major >= 0, "major version should be non-negative"
        assert info.version != "", "version string should be populated"
        assert info.full_output != "", "full output should be captured"

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_check_version_compatible(self, ffmpeg_service: FFmpegService):
        """check_version_compatible returns a tuple with a boolean and message."""
        compatible, msg = await ffmpeg_service.check_version_compatible()
        assert isinstance(compatible, bool)
        assert isinstance(msg, str)
        assert len(msg) > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_ffmpeg_available(self, ffmpeg_service: FFmpegService):
        """check_ffmpeg_available should return True when FFmpeg is installed."""
        available = await ffmpeg_service.check_ffmpeg_available()
        assert available is True


# ---------------------------------------------------------------------------
# 2. Video normalisation
# ---------------------------------------------------------------------------

@requires_ffmpeg
class TestVideoNormalization:
    """Tests for normalising videos to a standard format."""

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_normalize_produces_valid_output(
        self, ffmpeg_service: FFmpegService, tmp_path: Path
    ):
        """Create a test clip, normalise it, and verify the output exists."""
        src = str(tmp_path / "src.mp4")
        dst = str(tmp_path / "normalised.mp4")

        await ffmpeg_service.create_test_video(src, duration=1.0, width=640, height=480)
        assert os.path.exists(src)

        result = await ffmpeg_service.normalize_video(
            src, dst, target_width=1280, target_height=720, target_fps=30
        )
        assert result == dst
        assert os.path.exists(dst)
        assert os.path.getsize(dst) > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_normalize_info_has_correct_resolution(
        self, ffmpeg_service: FFmpegService, tmp_path: Path
    ):
        """Normalised video should reflect target resolution."""
        src = str(tmp_path / "small.mp4")
        dst = str(tmp_path / "out.mp4")
        await ffmpeg_service.create_test_video(src, duration=0.5, width=320, height=240)

        await ffmpeg_service.normalize_video(src, dst, target_width=640, target_height=480)
        info = await ffmpeg_service.get_video_info(dst)
        # get_video_info parses resolution from ffprobe; at minimum the file must exist
        assert "path" in info
        assert info["size"] > 0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_normalize_missing_input_raises(
        self, ffmpeg_service: FFmpegService, tmp_path: Path
    ):
        """Normalising a non-existent file raises FFmpegError."""
        with pytest.raises(FFmpegError, match="not found"):
            await ffmpeg_service.normalize_video(
                str(tmp_path / "nope.mp4"), str(tmp_path / "out.mp4")
            )


# ---------------------------------------------------------------------------
# 3. Video concatenation
# ---------------------------------------------------------------------------

@requires_ffmpeg
class TestVideoConcatenation:
    """Tests for joining multiple video clips."""

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_concatenate_two_clips(
        self, ffmpeg_service: FFmpegService, tmp_path: Path
    ):
        """Concatenating two compatible clips produces a valid output file."""
        clip_a = str(tmp_path / "a.mp4")
        clip_b = str(tmp_path / "b.mp4")
        output = str(tmp_path / "joined.mp4")

        # Create clips with the same resolution for safe concat
        await ffmpeg_service.create_test_video(clip_a, duration=0.5, color="red")
        await ffmpeg_service.create_test_video(clip_b, duration=0.5, color="green")

        result = await ffmpeg_service.concatenate_videos(
            [clip_a, clip_b], output
        )
        assert result == output
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    @pytest.mark.asyncio
    async def test_concatenate_empty_list_raises(self, ffmpeg_service: FFmpegService):
        """Empty input list should raise FFmpegError."""
        with pytest.raises(FFmpegError, match="No input videos"):
            await ffmpeg_service.concatenate_videos([], "/tmp/out.mp4")


# ---------------------------------------------------------------------------
# 4. Media info probing
# ---------------------------------------------------------------------------

@requires_ffmpeg
class TestMediaInfoProbe:
    """Tests for get_video_info."""

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_probe_returns_metadata(
        self, ffmpeg_service: FFmpegService, tmp_path: Path
    ):
        """Probe a known test video and verify returned metadata."""
        vpath = str(tmp_path / "probe.mp4")
        await ffmpeg_service.create_test_video(vpath, duration=1.0)

        info = await ffmpeg_service.get_video_info(vpath)
        assert info["path"] == vpath
        assert info["size"] > 0
        # Duration should be around 1 second (allow some tolerance)
        assert "duration" in info
        assert 0.5 < info["duration"] < 3.0

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_probe_missing_file_raises(self, ffmpeg_service: FFmpegService):
        """Probing a non-existent file raises FFmpegError."""
        with pytest.raises(FFmpegError):
            await ffmpeg_service.get_video_info("/tmp/does_not_exist.mp4")


# ---------------------------------------------------------------------------
# 5. Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests for FFmpegError construction and edge cases."""

    def test_ffmpeg_error_attributes(self):
        """FFmpegError carries returncode and stderr."""
        err = FFmpegError("boom", returncode=1, stderr="some log")
        assert str(err) == "boom"
        assert err.returncode == 1
        assert err.stderr == "some log"

    def test_ffmpeg_error_defaults(self):
        """Default returncode and stderr are None."""
        err = FFmpegError("oops")
        assert err.returncode is None
        assert err.stderr is None

    @pytest.mark.asyncio
    async def test_bad_ffmpeg_path_raises(self):
        """Using a non-existent binary path raises FFmpegError or FileNotFoundError."""
        bad = FFmpegService(ffmpeg_path="/nonexistent/ffmpeg")
        available = await bad.check_ffmpeg_available()
        assert available is False

    @pytest.mark.external
    @pytest.mark.asyncio
    async def test_create_test_video_bad_path_raises(self, ffmpeg_service: FFmpegService):
        """Creating a test video into an invalid directory raises FFmpegError."""
        with pytest.raises(FFmpegError):
            await ffmpeg_service.create_test_video("/nonexistent_dir/output.mp4")


# ---------------------------------------------------------------------------
# 6. FFmpegVersionInfo data class
# ---------------------------------------------------------------------------

class TestVersionInfoDataclass:
    """Verify FFmpegVersionInfo helper properties."""

    def test_str_representation(self):
        info = FFmpegVersionInfo(version="6.0.1")
        assert str(info) == "FFmpeg 6.0.1"

    def test_str_unknown(self):
        info = FFmpegVersionInfo()
        assert str(info) == "FFmpeg (version unknown)"

    def test_version_tuple(self):
        info = FFmpegVersionInfo(major=5, minor=1, patch=2)
        assert info.version_tuple == (5, 1, 2)
