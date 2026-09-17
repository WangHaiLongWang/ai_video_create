"""FFmpeg service — video concatenation, conversion, and processing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class FFmpegVersionInfo:
    """Parsed FFmpeg version and build information."""

    version: str = ""
    major: int = 0
    minor: int = 0
    patch: int = 0
    build_config: str = ""
    libavcodec_version: str = ""
    libavformat_version: str = ""
    libavutil_version: str = ""
    full_output: str = ""

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        return f"FFmpeg {self.version}" if self.version else "FFmpeg (version unknown)"


def parse_ffmpeg_version(output: str) -> FFmpegVersionInfo:
    """Parse FFmpeg -version output into structured info.

    Args:
        output: Raw text output from ``ffmpeg -version``.

    Returns:
        FFmpegVersionInfo with parsed fields.
    """
    info = FFmpegVersionInfo(full_output=output)

    # First line: "ffmpeg version X.Y.Z-... Copyright ..." or "ffmpeg version X.Y-..."
    version_match = re.search(r"ffmpeg\s+version\s+(\d+)\.(\d+)\.?(\d*)", output)
    if version_match:
        info.major = int(version_match.group(1))
        info.minor = int(version_match.group(2))
        patch_str = version_match.group(3)
        info.patch = int(patch_str) if patch_str else 0
        info.version = f"{info.major}.{info.minor}.{info.patch}"

    # Build configuration line
    config_match = re.search(r"configuration:\s*(.+)", output)
    if config_match:
        info.build_config = config_match.group(1).strip()

    # Library versions — format is "libavcodec     61. 19.100 / 61. 19.100"
    lib_pattern = re.compile(r"^(lib\w+)\s+(\d+)\.\s*(\d+\.\d+)")
    for line in output.splitlines():
        m = lib_pattern.match(line)
        if m:
            lib_name = m.group(1)
            major_ver = m.group(2)
            minor_ver = m.group(3)
            full_ver = f"{major_ver}.{minor_ver}"
            if lib_name == "libavcodec":
                info.libavcodec_version = full_ver
            elif lib_name == "libavformat":
                info.libavformat_version = full_ver
            elif lib_name == "libavutil":
                info.libavutil_version = full_ver

    return info


class FFmpegError(Exception):
    """FFmpeg operation failed."""

    def __init__(self, message: str, returncode: int | None = None, stderr: str | None = None):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class FFmpegService:
    """Service for FFmpeg video processing operations."""

    # Minimum required FFmpeg version (major, minor, patch)
    MIN_VERSION: tuple[int, int, int] = (4, 0, 0)

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """Initialize FFmpeg service.

        Args:
            ffmpeg_path: Path to ffmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path
        self._ffmpeg_available: bool | None = None
        self._version_info: FFmpegVersionInfo | None = None

    # ------------------------------------------------------------------
    # Version detection
    # ------------------------------------------------------------------

    async def get_version_info(self) -> FFmpegVersionInfo:
        """Return parsed FFmpeg version info (cached).

        Raises:
            FFmpegError: If FFmpeg is not reachable.
        """
        if self._version_info is not None:
            return self._version_info

        if not await self.check_ffmpeg_available():
            raise FFmpegError(
                f"FFmpeg is not available at '{self.ffmpeg_path}'. "
                "Install FFmpeg and ensure it is on your PATH or set FFMPEG_PATH."
            )

        proc = await asyncio.create_subprocess_exec(
            self.ffmpeg_path, "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")
        self._version_info = parse_ffmpeg_version(output)
        return self._version_info

    async def check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is available and executable
        """
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available

        try:
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._ffmpeg_available = proc.returncode == 0
            return self._ffmpeg_available
        except FileNotFoundError:
            self._ffmpeg_available = False
            return False

    async def check_version_compatible(self) -> tuple[bool, str]:
        """Check whether installed FFmpeg meets minimum version requirement.

        Returns:
            Tuple of (is_compatible, message).
        """
        try:
            info = await self.get_version_info()
        except FFmpegError as exc:
            return False, str(exc)

        if info.version_tuple >= self.MIN_VERSION:
            return True, (
                f"{info} is compatible (minimum required: "
                f"{'.'.join(map(str, self.MIN_VERSION))})"
            )
        return False, (
            f"{info} is below the minimum required version "
            f"{'.'.join(map(str, self.MIN_VERSION))}. "
            "Please upgrade FFmpeg."
        )

    async def concatenate_videos(
        self,
        video_paths: list[str],
        output_path: str,
        callback: Callable[[float], Awaitable[None]] | None = None,
    ) -> str:
        """Concatenate multiple videos into one.

        Args:
            video_paths: List of input video file paths
            output_path: Output video file path
            callback: Optional progress callback (0.0 to 1.0)

        Returns:
            Path to the output video

        Raises:
            FFmpegError: If concatenation fails
        """
        if not video_paths:
            raise FFmpegError("No input videos provided")

        # Check if FFmpeg is available
        if not await self.check_ffmpeg_available():
            raise FFmpegError("FFmpeg is not available")

        # Create concat list file
        concat_list_path = None
        try:
            # Write concat list — resolve relative paths to absolute so ffmpeg
            # can find the files regardless of its working directory.
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False
            ) as f:
                for video_path in video_paths:
                    abs_path = os.path.abspath(video_path)
                    # Escape single quotes in path
                    safe_path = abs_path.replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
                concat_list_path = f.name

            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite output
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",  # Copy streams without re-encoding
                "-movflags", "+faststart",
                output_path,
            ]

            # Execute
            await self._run_ffmpeg(cmd, callback)

            return output_path

        finally:
            # Cleanup temp file
            if concat_list_path and os.path.exists(concat_list_path):
                os.unlink(concat_list_path)

    async def normalize_video(
        self,
        input_path: str,
        output_path: str,
        target_width: int = 1920,
        target_height: int = 1080,
        target_fps: int = 30,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        callback: Callable[[float], Awaitable[None]] | None = None,
    ) -> str:
        """Normalize a video to a standard format suitable for concatenation.

        Re-encodes the video with consistent codec, resolution, frame rate
        and pixel format so that multiple clips can be safely concatenated.

        Args:
            input_path: Path to source video.
            output_path: Path for the normalized output.
            target_width: Target width in pixels.
            target_height: Target height in pixels.
            target_fps: Target frames per second.
            video_codec: Video encoder (e.g. libx264, libx265).
            audio_codec: Audio encoder (e.g. aac, copy).
            callback: Optional async progress callback.

        Returns:
            Path to the normalized video.

        Raises:
            FFmpegError: On missing input or FFmpeg failure.
        """
        if not await self.check_ffmpeg_available():
            raise FFmpegError("FFmpeg is not available")

        if not os.path.exists(input_path):
            raise FFmpegError(f"Input video not found: {input_path}")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", input_path,
            "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                   f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,"
                   f"fps={target_fps}",
            "-c:v", video_codec,
            "-pix_fmt", "yuv420p",
            "-c:a", audio_codec,
            "-ar", "44100",
            "-ac", "2",
            "-movflags", "+faststart",
            output_path,
        ]

        await self._run_ffmpeg(cmd, callback)
        return output_path

    async def image_to_video(
        self,
        image_path: str,
        output_path: str,
        duration: float = 4.0,
        fps: int = 24,
        width: int = 1920,
        height: int = 1080,
        callback: Callable[[float], Awaitable[None]] | None = None,
    ) -> str:
        """Convert an image to a video with Ken Burns effect.

        Args:
            image_path: Path to input image
            output_path: Path to output video
            duration: Video duration in seconds
            fps: Frames per second
            width: Output width
            height: Output height
            callback: Optional progress callback

        Returns:
            Path to the output video

        Raises:
            FFmpegError: If conversion fails
        """
        if not await self.check_ffmpeg_available():
            raise FFmpegError("FFmpeg is not available")

        if not os.path.exists(image_path):
            raise FFmpegError(f"Image not found: {image_path}")

        total_frames = int(duration * fps)

        # Ken Burns effect: slow zoom in
        # zoompan filter: zoom from 1.0 to 1.1 over the duration
        zoom_filter = (
            f"zoompan=z='min(zoom+0.0005,1.1)':"
            f"d={total_frames}:"
            f"s={width}x{height}:"
            f"fps={fps}"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", zoom_filter,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ]

        await self._run_ffmpeg(cmd, callback)
        return output_path

    async def get_video_info(self, video_path: str) -> dict[str, Any]:
        """Get video file information.

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video metadata

        Raises:
            FFmpegError: If probe fails
        """
        if not await self.check_ffmpeg_available():
            raise FFmpegError("FFmpeg is not available")

        if not os.path.exists(video_path):
            raise FFmpegError(f"Video not found: {video_path}")

        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-f", "null",
            "-",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        stderr_text = stderr.decode('utf-8', errors='replace')

        # Parse ffprobe output
        info = {
            "path": video_path,
            "size": os.path.getsize(video_path),
        }

        # Extract duration
        for line in stderr_text.split('\n'):
            if 'Duration:' in line:
                duration_str = line.split('Duration:')[1].split(',')[0].strip()
                info["duration"] = self._parse_duration(duration_str)
            if 'Video:' in line:
                parts = line.split('Video:')[1].split(',')
                info["codec"] = parts[0].strip()
                if len(parts) > 1:
                    info["resolution"] = parts[1].strip()
            if 'Audio:' in line:
                info["has_audio"] = True

        return info

    async def create_test_video(
        self,
        output_path: str,
        duration: float = 2.0,
        width: int = 320,
        height: int = 240,
        color: str = "blue",
    ) -> str:
        """Create a test video with solid color (for testing).

        Args:
            output_path: Output path
            duration: Duration in seconds
            width: Width
            height: Height
            color: Background color

        Returns:
            Path to created video
        """
        if not await self.check_ffmpeg_available():
            raise FFmpegError("FFmpeg is not available")

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s={width}x{height}:d={duration}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        await self._run_ffmpeg(cmd)
        return output_path

    async def _run_ffmpeg(
        self,
        cmd: list[str],
        callback: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Run an FFmpeg command.

        Args:
            cmd: Command and arguments
            callback: Optional progress callback

        Raises:
            FFmpegError: If command fails, with detailed diagnostic info.
        """
        logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            stderr_text = stderr.decode('utf-8', errors='replace')
            # Extract the last meaningful error line from FFmpeg output
            error_lines = [
                ln.strip() for ln in stderr_text.splitlines()
                if ln.strip() and not ln.strip().startswith("frame=")
            ]
            last_error = error_lines[-1] if error_lines else "unknown error"
            raise FFmpegError(
                f"FFmpeg failed (rc={proc.returncode}): {last_error}\n"
                f"Command: {' '.join(cmd[:6])}{'...' if len(cmd) > 6 else ''}",
                returncode=proc.returncode,
                stderr=stderr_text,
            )

    def _parse_duration(self, duration_str: str) -> float:
        """Parse HH:MM:SS.ms duration string."""
        parts = duration_str.split(':')
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        return 0.0


# Global instance
_ffmpeg_service: FFmpegService | None = None


def _detect_ffmpeg_path(configured_path: str) -> str:
    """Return the best available ffmpeg path.

    Resolution order:
    1. Explicitly configured path (settings.FFMPEG_PATH) if it exists on disk.
    2. ``imageio_ffmpeg`` bundled binary (common in pip-installed environments).
    3. Fallback to the configured string (may fail at runtime if not on PATH).
    """
    import os
    if configured_path and os.path.isfile(configured_path):
        return configured_path
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return configured_path


def get_ffmpeg_service() -> FFmpegService:
    """Get or create global FFmpeg service instance."""
    global _ffmpeg_service
    if _ffmpeg_service is None:
        from backend.app.config import get_settings
        settings = get_settings()
        resolved = _detect_ffmpeg_path(settings.FFMPEG_PATH)
        _ffmpeg_service = FFmpegService(resolved)
    return _ffmpeg_service


def reset_ffmpeg_service() -> None:
    """Reset FFmpeg service (for testing)."""
    global _ffmpeg_service
    _ffmpeg_service = None
