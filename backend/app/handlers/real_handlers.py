"""Real handlers — use AI providers and services for actual execution."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from backend.app.providers import get_provider
from backend.app.providers.base import ProviderError
from backend.app.services.asset_manager import get_asset_manager
from backend.app.services.ffmpeg import get_ffmpeg_service, FFmpegError

logger = logging.getLogger(__name__)


class RealTextInputHandler:
    """TextInput handler — uses LLM provider to process prompts."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute text input node."""
        config = task.get("config", {})
        prompt = config.get("prompt", "")

        if not prompt:
            return {"status": "ok", "output": {"type": "text", "content": ""}}

        # Try to use LLM provider for processing
        provider = get_provider(config.get("provider", "mock"))
        if provider and provider.capabilities.text:
            try:
                processed_text = await provider.generate_text(prompt, config)
                return {"status": "ok", "output": {"type": "text", "content": processed_text}}
            except ProviderError as e:
                logger.warning(f"Provider failed, using raw prompt: {e}")

        # Fallback: return raw prompt
        return {"status": "ok", "output": {"type": "text", "content": prompt}}


class RealStoryboardHandler:
    """Storyboard handler — uses LLM to generate structured scenes."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute storyboard node."""
        config = task.get("config", {})
        prompt = config.get("prompt", "Generate a storyboard")
        scene_count = int(config.get("scenes", 5))
        style = config.get("style", "cinematic")

        # Build storyboard generation prompt
        storyboard_prompt = f"""Generate a storyboard with {scene_count} scenes.
Style: {style}

Requirements:
1. Return a JSON object with a "scenes" array
2. Each scene must have: scene_id, index, narration, image_prompt, video_prompt, duration_seconds
3. Keep image_prompt detailed and descriptive for image generation
4. Keep video_prompt focused on motion and camera movement

User request: {prompt}"""

        # Try to use LLM provider
        provider = get_provider(config.get("provider", "mock"))
        if provider and provider.capabilities.text:
            try:
                response_text = await provider.generate_text(storyboard_prompt, {
                    **config,
                    "temperature": 0.8,
                    "max_tokens": 4096,
                })

                # Parse JSON response
                scenes_data = self._parse_storyboard_response(response_text, scene_count)

                return {
                    "status": "ok",
                    "output": {
                        "type": "list<scene>",
                        "scenes": scenes_data,
                        "count": len(scenes_data),
                    },
                }
            except ProviderError as e:
                logger.warning(f"Provider failed, generating mock storyboard: {e}")

        # Fallback: generate basic storyboard
        scenes = []
        for i in range(scene_count):
            scenes.append({
                "scene_id": f"scene-{i + 1:03d}",
                "index": i,
                "narration": f"Scene {i + 1}: {prompt}",
                "image_prompt": f"{prompt}, style: {style}, scene {i + 1}",
                "video_prompt": f"Camera movement for scene {i + 1}",
                "duration_seconds": 4,
            })

        return {
            "status": "ok",
            "output": {"type": "list<scene>", "scenes": scenes, "count": scene_count},
        }

    def _parse_storyboard_response(self, text: str, expected_count: int) -> list[dict]:
        """Parse LLM response into structured scenes."""
        try:
            # Try to extract JSON from response
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            scenes = data.get("scenes", [])

            # Validate and fill defaults
            validated_scenes = []
            for i, scene in enumerate(scenes[:expected_count]):
                validated_scenes.append({
                    "scene_id": scene.get("scene_id", f"scene-{i + 1:03d}"),
                    "index": i,
                    "narration": scene.get("narration", ""),
                    "image_prompt": scene.get("image_prompt", ""),
                    "video_prompt": scene.get("video_prompt", ""),
                    "duration_seconds": scene.get("duration_seconds", 4),
                })

            # Pad with defaults if fewer scenes than expected
            while len(validated_scenes) < expected_count:
                i = len(validated_scenes)
                validated_scenes.append({
                    "scene_id": f"scene-{i + 1:03d}",
                    "index": i,
                    "narration": f"Scene {i + 1}",
                    "image_prompt": f"Scene {i + 1} image",
                    "video_prompt": f"Scene {i + 1} video",
                    "duration_seconds": 4,
                })

            return validated_scenes

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse storyboard response: {e}")
            # Return default scenes
            return [
                {
                    "scene_id": f"scene-{i + 1:03d}",
                    "index": i,
                    "narration": f"Scene {i + 1}",
                    "image_prompt": f"Scene {i + 1} image",
                    "video_prompt": f"Scene {i + 1} video",
                    "duration_seconds": 4,
                }
                for i in range(expected_count)
            ]


class RealTextToImageHandler:
    """TextToImage handler — uses image provider to generate images."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute text-to-image node."""
        config = task.get("config", {})
        prompt = config.get("image_prompt", config.get("prompt", ""))
        scene_id = task.get("item_key", "unknown")

        if not prompt:
            return {"status": "error", "error": "No prompt provided"}

        # Get provider
        provider = get_provider(config.get("provider", "mock"))
        if not provider or not provider.capabilities.image:
            return {"status": "error", "error": "No image provider available"}

        try:
            # Generate image
            image_data = await provider.generate_image(prompt, config)

            # Save to asset manager
            asset_manager = get_asset_manager()
            asset_id = f"img-{uuid.uuid4().hex[:8]}"
            relative_path = asset_manager.save_asset(
                image_data,
                filename=asset_id,
                category="images",
                extension="png",
            )

            return {
                "status": "ok",
                "output": {
                    "type": "list<image>",
                    "asset_id": asset_id,
                    "scene_id": scene_id,
                    "path": relative_path,
                    "url": asset_manager.get_asset_url(relative_path),
                    "width": config.get("width", 1024),
                    "height": config.get("height", 768),
                },
            }

        except ProviderError as e:
            logger.error(f"Image generation failed: {e}")
            return {"status": "error", "error": str(e)}


class RealImageToVideoHandler:
    """ImageToVideo handler — uses video provider or FFmpeg."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute image-to-video node."""
        config = task.get("config", {})
        scene_id = task.get("item_key", "unknown")
        duration = config.get("duration", 4)

        # Get the input image from upstream
        # The image path should be passed in task config from compiler
        image_path = config.get("image_path", "")

        if not image_path:
            # No image path - try provider
            return await self._use_provider(task, config, scene_id, duration)

        # Use FFmpeg to create video from image
        return await self._use_ffmpeg(task, config, scene_id, image_path, duration)

    async def _use_provider(
        self, task: dict, config: dict, scene_id: str, duration: float
    ) -> dict:
        """Use video provider to generate video."""
        provider = get_provider(config.get("provider", "mock"))
        if not provider or not provider.capabilities.video:
            return {"status": "error", "error": "No video provider available"}

        try:
            # Provider needs an image, but we don't have one
            # Fall back to mock or raise error
            return {"status": "error", "error": "Image path required for video generation"}

        except ProviderError as e:
            logger.error(f"Video generation failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _use_ffmpeg(
        self, task: dict, config: dict, scene_id: str, image_path: str, duration: float
    ) -> dict:
        """Use FFmpeg to create video from image."""
        try:
            ffmpeg = get_ffmpeg_service()

            # Check if FFmpeg is available
            if not await ffmpeg.check_ffmpeg_available():
                # Fallback to mock
                return self._mock_video_output(scene_id, duration)

            # Generate output path
            asset_id = f"vid-{uuid.uuid4().hex[:8]}"
            asset_manager = get_asset_manager()
            output_filename = f"{asset_id}.mp4"
            output_path = asset_manager.get_asset_path(f"videos/{output_filename}")

            # Create video
            await ffmpeg.image_to_video(
                image_path,
                output_path,
                duration=duration,
                width=config.get("width", 1920),
                height=config.get("height", 1080),
            )

            relative_path = f"videos/{output_filename}"

            return {
                "status": "ok",
                "output": {
                    "type": "list<video>",
                    "asset_id": asset_id,
                    "scene_id": scene_id,
                    "path": relative_path,
                    "url": asset_manager.get_asset_url(relative_path),
                    "duration_seconds": duration,
                },
            }

        except FFmpegError as e:
            logger.error(f"FFmpeg video creation failed: {e}")
            return self._mock_video_output(scene_id, duration)

    def _mock_video_output(self, scene_id: str, duration: float) -> dict:
        """Generate mock video output as fallback."""
        asset_id = f"vid-{uuid.uuid4().hex[:8]}"
        return {
            "status": "ok",
            "output": {
                "type": "list<video>",
                "asset_id": asset_id,
                "scene_id": scene_id,
                "path": f"data/assets/videos/{asset_id}.mp4",
                "duration_seconds": duration,
            },
        }


class RealVideoConcatHandler:
    """VideoConcat handler — uses FFmpeg to concatenate videos."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute video concatenation node."""
        config = task.get("config", {})
        filename = config.get("filename", "output.mp4")

        # Get video paths from upstream tasks
        video_paths = config.get("video_paths", [])

        if not video_paths:
            # No videos to concatenate
            asset_id = f"final-{uuid.uuid4().hex[:8]}"
            return {
                "status": "ok",
                "output": {
                    "type": "video",
                    "asset_id": asset_id,
                    "path": f"data/assets/final/{asset_id}.mp4",
                    "filename": filename,
                },
            }

        try:
            ffmpeg = get_ffmpeg_service()

            # Check if FFmpeg is available
            if not await ffmpeg.check_ffmpeg_available():
                return self._mock_concat_output(filename)

            # Resolve absolute paths
            asset_manager = get_asset_manager()
            abs_paths = [asset_manager.get_asset_path(p) for p in video_paths]

            # Generate output path
            asset_id = f"final-{uuid.uuid4().hex[:8]}"
            output_filename = f"{asset_id}.mp4"
            output_path = asset_manager.get_asset_path(f"final/{output_filename}")

            # Concatenate videos
            await ffmpeg.concatenate_videos(abs_paths, output_path)

            relative_path = f"final/{output_filename}"

            return {
                "status": "ok",
                "output": {
                    "type": "video",
                    "asset_id": asset_id,
                    "path": relative_path,
                    "url": asset_manager.get_asset_url(relative_path),
                    "filename": filename,
                },
            }

        except FFmpegError as e:
            logger.error(f"FFmpeg concatenation failed: {e}")
            return self._mock_concat_output(filename)

    def _mock_concat_output(self, filename: str) -> dict:
        """Generate mock concat output as fallback."""
        asset_id = f"final-{uuid.uuid4().hex[:8]}"
        return {
            "status": "ok",
            "output": {
                "type": "video",
                "asset_id": asset_id,
                "path": f"data/assets/final/{asset_id}.mp4",
                "filename": filename,
            },
        }


class RealOutputHandler:
    """Output handler — finalizes assets and generates URLs."""

    async def execute(self, task: dict, context: dict) -> dict:
        """Execute output node."""
        config = task.get("config", {})

        # Get video path from upstream
        video_path = config.get("video_path", "")

        asset_manager = get_asset_manager()

        if video_path and asset_manager.asset_exists(video_path):
            asset_info = asset_manager.get_asset_info(video_path)
            return {
                "status": "ok",
                "output": {
                    "type": "final",
                    "message": "工作流执行完成",
                    "video_path": video_path,
                    "video_url": asset_manager.get_asset_url(video_path),
                    "asset_info": asset_info,
                },
            }

        return {
            "status": "ok",
            "output": {
                "type": "final",
                "message": "工作流执行完成",
            },
        }
