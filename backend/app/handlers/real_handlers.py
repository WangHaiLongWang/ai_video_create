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
from backend.app.handlers.contracts import ArtifactRef, NodeResult

logger = logging.getLogger(__name__)


def _provider_name(config: dict, capability: str) -> str:
    """Resolve a node override or the configured default provider."""
    configured = config.get("provider")
    if configured:
        return str(configured).lower()
    from backend.app.config import get_settings
    settings = get_settings()
    defaults = {
        "text": settings.DEFAULT_LLM_PROVIDER.value,
        "image": settings.DEFAULT_IMAGE_PROVIDER.value,
        "video": settings.DEFAULT_VIDEO_PROVIDER.value,
    }
    return defaults[capability]


class RealTextInputHandler:
    """TextInput handler — uses LLM provider to process prompts."""

    async def execute(self, task: dict, context: dict) -> NodeResult:
        """Execute text input node."""
        config = task.get("config", {})
        prompt = config.get("prompt", "")

        if not prompt:
            return NodeResult.ok(
                output=ArtifactRef(type="text", metadata={"content": ""}),
            )

        # TextInput is a source node. LLM processing belongs to storyboard or a
        # dedicated LLM node, so preserve the user's prompt verbatim.
        return NodeResult.ok(
            output=ArtifactRef(type="text", metadata={"content": prompt}),
        )


class RealStoryboardHandler:
    """Storyboard handler — uses LLM to generate structured scenes."""

    async def execute(self, task: dict, context: dict) -> NodeResult:
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
        provider = get_provider(_provider_name(config, "text"))
        if provider and provider.capabilities.text:
            try:
                response_text = await provider.generate_text(storyboard_prompt, {
                    **config,
                    "temperature": 0.8,
                    "max_tokens": 4096,
                })

                # Parse JSON response
                scenes_data = self._parse_storyboard_response(response_text, scene_count)

                return NodeResult.ok(
                    output=ArtifactRef(
                        type="text",
                        metadata={"scenes": scenes_data, "count": len(scenes_data)},
                    ),
                )
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

        return NodeResult.ok(
            output=ArtifactRef(
                type="text",
                metadata={"scenes": scenes, "count": scene_count},
            ),
        )

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
    """TextToImage handler — uses image provider to generate images.

    Expects ``config["image_prompt"]`` to be set by the worker from the
    corresponding scene's ``image_prompt`` field (via
    :class:`~backend.app.handlers.contracts.Scene`).  Falls back to
    ``config["prompt"]`` when no scene data is available.
    """

    async def execute(self, task: dict, context: dict) -> NodeResult:
        """Execute text-to-image node.

        The worker injects ``scene.image_prompt`` into ``config["image_prompt"]``
        before this handler runs.  When ``variant_prompt_suffix`` is present it
        is appended to the prompt to produce variant-specific images.
        """
        config = task.get("config", {})
        prompt = config.get("image_prompt", config.get("prompt", ""))
        scene_id = task.get("item_key", "unknown")

        # 解析 scene_id 和 variant_id（支持 "scene-001::variant-01" 格式）
        actual_scene_id = scene_id
        variant_id = config.get("variant_id", "")
        if "::" in scene_id:
            actual_scene_id, variant_id = scene_id.split("::", 1)

        # 追加变体 prompt suffix
        variant_suffix = config.get("variant_prompt_suffix", "")
        if variant_suffix:
            prompt = f"{prompt} {variant_suffix}"

        if not prompt:
            return NodeResult.fail(
                code="NO_PROMPT",
                message="No prompt provided",
            )

        # Get provider
        provider = get_provider(_provider_name(config, "image"))
        if not provider or not provider.capabilities.image:
            return NodeResult.fail(
                code="NO_IMAGE_PROVIDER",
                message="No image provider available",
            )

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

            return NodeResult.ok(
                output=ArtifactRef(
                    type="image",
                    asset_id=asset_id,
                    scene_id=actual_scene_id,
                    variant_id=variant_id or None,
                    url=asset_manager.get_asset_url(relative_path),
                    metadata={
                        "path": relative_path,
                        "width": config.get("width", 1024),
                        "height": config.get("height", 768),
                        "variant_index": config.get("variant_index", 0),
                    },
                ),
                artifacts=[asset_id],
            )

        except ProviderError as e:
            logger.error(f"Image generation failed: {e}")
            return NodeResult.fail(
                code="PROVIDER_ERROR",
                message=str(e),
            )


class RealImageToVideoHandler:
    """ImageToVideo handler — uses video provider or FFmpeg.

    Expects ``config["video_prompt"]`` to be set by the worker from the
    corresponding scene's ``video_prompt`` field (via
    :class:`~backend.app.handlers.contracts.Scene`).  Falls back to
    ``config["prompt"]`` when no scene data is available.
    """

    async def execute(self, task: dict, context: dict) -> NodeResult:
        """Execute image-to-video node.

        The worker injects ``scene.video_prompt`` into ``config["video_prompt"]``
        and ``scene.duration`` into ``config["duration"]`` before this handler runs.
        """
        config = task.get("config", {})
        scene_id = task.get("item_key", "unknown")
        duration = config.get("duration", 4)

        # 解析 scene_id 和 variant_id
        actual_scene_id = scene_id
        variant_id = config.get("variant_id", "")
        if "::" in scene_id:
            actual_scene_id, variant_id = scene_id.split("::", 1)

        image_path = config.get("image_path", "") or self._find_upstream_image(
            context.get("upstream_results", {}), scene_id
        )

        if not image_path:
            return NodeResult.fail(
                code="NO_IMAGE",
                message="Image path required for video generation",
            )

        provider_name = _provider_name(config, "video")
        if provider_name in {"wan3", "comfyui"}:
            return await self._use_provider(task, config, actual_scene_id, variant_id, duration, image_path)
        if provider_name == "mock":
            return self._mock_video_output(actual_scene_id, variant_id, duration)
        return await self._use_ffmpeg(task, config, actual_scene_id, variant_id, image_path, duration)

    async def _use_provider(
        self, task: dict, config: dict, scene_id: str, variant_id: str, duration: float, image_path: str
    ) -> NodeResult:
        """Use video provider to generate video."""
        provider = get_provider(_provider_name(config, "video"))
        if not provider or not provider.capabilities.video:
            return NodeResult.fail(
                code="NO_VIDEO_PROVIDER",
                message="No video provider available",
            )

        try:
            asset_manager = get_asset_manager()
            if not __import__("os").path.isabs(image_path):
                image_path = asset_manager.get_asset_path(image_path)
            video_data = await provider.generate_video(
                image_path,
                str(config.get("video_prompt", config.get("prompt", "镜头自然运动"))),
                config,
            )

            # Persist external_job_id if the provider exposes one
            external_job_id = None
            if hasattr(provider, "get_external_job_id"):
                external_job_id = provider.get_external_job_id()
            if external_job_id and task.get("id"):
                from backend.app.engine.queue import save_external_job_id
                save_external_job_id(task["id"], external_job_id)

            asset_id = f"vid-{uuid.uuid4().hex[:8]}"
            relative_path = asset_manager.save_asset(
                video_data,
                filename=asset_id,
                category="videos",
                extension="mp4",
            )
            return NodeResult.ok(
                output=ArtifactRef(
                    type="video",
                    asset_id=asset_id,
                    scene_id=scene_id,
                    variant_id=variant_id or None,
                    url=asset_manager.get_asset_url(relative_path),
                    metadata={
                        "path": relative_path,
                        "duration_seconds": duration,
                        "resolution": config.get("resolution", "480P"),
                        "provider": _provider_name(config, "video"),
                        "external_job_id": external_job_id,
                    },
                ),
                artifacts=[asset_id],
            )

        except ProviderError as e:
            logger.error(f"Video generation failed: {e}")
            return NodeResult.fail(
                code="PROVIDER_ERROR",
                message=str(e),
            )

    @staticmethod
    def _find_upstream_image(upstream_results: dict, scene_id: str) -> str:
        """Find the image output matching this mapped scene and optional variant.

        ``scene_id`` may be a plain ``scene-001`` or a compound
        ``scene-001::variant-01`` key.  When a variant is present we require
        an exact match on both ``scene_id`` and ``variant_id`` in the upstream
        artifact metadata.
        """
        actual_scene = scene_id
        variant_id = ""
        if "::" in scene_id:
            actual_scene, variant_id = scene_id.split("::", 1)

        fallback = ""
        for result in upstream_results.values():
            output = result.get("output", result) if isinstance(result, dict) else {}
            if not isinstance(output, dict):
                continue
            # Path may be at top level or in metadata
            path = str(output.get("path", ""))
            if not path:
                meta = output.get("metadata", {})
                if isinstance(meta, dict):
                    path = str(meta.get("path", ""))
            if not path:
                continue
            if not fallback:
                fallback = path
            out_scene = output.get("scene_id", "")
            out_variant = output.get("variant_id", "")
            if out_scene == actual_scene:
                if variant_id:
                    if out_variant == variant_id:
                        return path
                else:
                    return path
        return fallback

    async def _use_ffmpeg(
        self, task: dict, config: dict, scene_id: str, variant_id: str, image_path: str, duration: float
    ) -> NodeResult:
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

            return NodeResult.ok(
                output=ArtifactRef(
                    type="video",
                    asset_id=asset_id,
                    scene_id=scene_id,
                    variant_id=variant_id or None,
                    url=asset_manager.get_asset_url(relative_path),
                    metadata={
                        "path": relative_path,
                        "duration_seconds": duration,
                    },
                ),
                artifacts=[asset_id],
            )

        except FFmpegError as e:
            logger.error(f"FFmpeg video creation failed: {e}")
            return self._mock_video_output(scene_id, variant_id, duration)

    def _mock_video_output(self, scene_id: str, variant_id: str = "", duration: float = 4) -> NodeResult:
        """Generate mock video output as fallback."""
        asset_id = f"vid-{uuid.uuid4().hex[:8]}"
        return NodeResult.ok(
            output=ArtifactRef(
                type="video",
                asset_id=asset_id,
                scene_id=scene_id,
                variant_id=variant_id or None,
                metadata={
                    "path": f"data/assets/videos/{asset_id}.mp4",
                    "duration_seconds": duration,
                },
            ),
            artifacts=[asset_id],
        )


class RealVideoConcatHandler:
    """VideoConcat handler — uses FFmpeg to concatenate videos."""

    async def execute(self, task: dict, context: dict) -> NodeResult:
        """Execute video concatenation node."""
        config = task.get("config", {})
        filename = config.get("filename", "output.mp4")

        # Get video paths from upstream tasks
        video_paths = config.get("video_paths", [])

        if not video_paths:
            # No videos to concatenate
            asset_id = f"final-{uuid.uuid4().hex[:8]}"
            return NodeResult.ok(
                output=ArtifactRef(
                    type="video",
                    asset_id=asset_id,
                    metadata={
                        "path": f"data/assets/final/{asset_id}.mp4",
                        "filename": filename,
                    },
                ),
                artifacts=[asset_id],
            )

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

            return NodeResult.ok(
                output=ArtifactRef(
                    type="video",
                    asset_id=asset_id,
                    url=asset_manager.get_asset_url(relative_path),
                    metadata={
                        "path": relative_path,
                        "filename": filename,
                    },
                ),
                artifacts=[asset_id],
            )

        except FFmpegError as e:
            logger.error(f"FFmpeg concatenation failed: {e}")
            return self._mock_concat_output(filename)

    def _mock_concat_output(self, filename: str) -> NodeResult:
        """Generate mock concat output as fallback."""
        asset_id = f"final-{uuid.uuid4().hex[:8]}"
        return NodeResult.ok(
            output=ArtifactRef(
                type="video",
                asset_id=asset_id,
                metadata={
                    "path": f"data/assets/final/{asset_id}.mp4",
                    "filename": filename,
                },
            ),
            artifacts=[asset_id],
        )


class RealOutputHandler:
    """Output handler — finalizes assets and generates URLs."""

    async def execute(self, task: dict, context: dict) -> NodeResult:
        """Execute output node."""
        config = task.get("config", {})

        # Get video path from upstream
        video_path = config.get("video_path", "")

        asset_manager = get_asset_manager()

        if video_path and asset_manager.asset_exists(video_path):
            asset_info = asset_manager.get_asset_info(video_path)
            return NodeResult.ok(
                output=ArtifactRef(
                    type="video",
                    url=asset_manager.get_asset_url(video_path),
                    metadata={
                        "message": "工作流执行完成",
                        "video_path": video_path,
                        "asset_info": asset_info,
                    },
                ),
            )

        return NodeResult.ok(
            output=ArtifactRef(
                type="video",
                metadata={"message": "工作流执行完成"},
            ),
        )
