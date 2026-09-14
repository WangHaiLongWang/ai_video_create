"""FFmpeg service — video concatenation, conversion, and processing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """FFmpeg operation failed."""

    def __init__(self, message: str, returncode: int | None = None, stderr: str | None = None):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class FFmpegService:
    """Service for FFmpeg video processing operations."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """Initialize FFmpeg service.

        Args:
            ffmpeg_path: Path to ffmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path
        self._ffmpeg_available: bool | None = None

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
            # Write concat list
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False
            ) as f:
                for video_path in video_paths:
                    # Escape single quotes in path
                    safe_path = video_path.replace("'", "'\\''")
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
            FFmpegError: If command fails
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
            raise FFmpegError(
                f"FFmpeg failed with return code {proc.returncode}",
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


def get_ffmpeg_service() -> FFmpegService:
    """Get or create global FFmpeg service instance."""
    global _ffmpeg_service
    if _ffmpeg_service is None:
        from backend.app.config import get_settings
        settings = get_settings()
        _ffmpeg_service = FFmpegService(settings.FFMPEG_PATH)
    return _ffmpeg_service


def reset_ffmpeg_service() -> None:
    """Reset FFmpeg service (for testing)."""
    global _ffmpeg_service
    _ffmpeg_service = None
