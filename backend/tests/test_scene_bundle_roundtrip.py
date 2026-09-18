"""Roundtrip tests for ScenePromptBundle: Pydantic -> JSON -> Pydantic.

Validates that:
- Serialization via model_dump produces correct camelCase keys.
- Deserialization from JSON round-trips faithfully.
- The ski_lesson_bundle fixture survives a full roundtrip.
- Edge cases: empty scenes, 1 scene, 20 scenes.
"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from backend.app.schemas.scene_bundle import (
    SceneImagePrompt,
    SceneVideoPrompt,
    SceneTransition,
    SceneEntry,
    ScenePromptBundle,
)
from backend.tests.fixtures.ski_lesson_bundle import SKI_LESSON_SCENE_BUNDLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_bundle(*, scenes: list[SceneEntry] | None = None) -> ScenePromptBundle:
    """Build a minimal valid ScenePromptBundle."""
    if scenes is None:
        scenes = [
            SceneEntry(
                scene_id="s1",
                index=0,
                title="Scene One",
                narration="Hello world.",
                duration_seconds=5.0,
                locked=False,
                image=SceneImagePrompt(prompt="A test image"),
                video=SceneVideoPrompt(prompt="A test video"),
                transition=SceneTransition(type="crossfade", duration=0.4),
            ),
        ]
    return ScenePromptBundle(
        storyboard_id="sb-roundtrip",
        workflow_id="wf-roundtrip",
        execution_id="ex-roundtrip",
        title="Roundtrip Test",
        global_style="cinematic",
        negative_prompt="blurry",
        scenes=scenes,
        exported_at="2025-06-15T12:00:00Z",
        source="draft",
    )


def _bundle_from_raw(raw: dict) -> ScenePromptBundle:
    """Build a ScenePromptBundle from a raw dict (camelCase keys)."""
    return ScenePromptBundle.model_validate(raw)


# ---------------------------------------------------------------------------
# Core roundtrip
# ---------------------------------------------------------------------------


class TestPydanticJsonRoundtrip:
    """Pydantic model -> model_dump -> JSON parse -> model_validate roundtrip."""

    def test_single_scene_roundtrip(self):
        bundle = _build_bundle()
        data = bundle.model_dump(by_alias=True)
        json_str = json.dumps(data)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored == bundle

    def test_model_dump_produces_camel_case(self):
        bundle = _build_bundle()
        data = bundle.model_dump(by_alias=True)
        # Top-level keys must be camelCase
        assert "schemaVersion" in data
        assert "storyboardId" in data
        assert "exportedAt" in data
        assert "globalStyle" in data
        assert "negativePrompt" in data
        # Scene keys
        scene = data["scenes"][0]
        assert "sceneId" in scene
        assert "durationSeconds" in scene
        assert "referenceAssetIds" in scene["image"]
        assert "firstFrameAssetId" in scene["video"]

    def test_model_dump_by_alias_false_uses_snake(self):
        bundle = _build_bundle()
        data = bundle.model_dump(by_alias=False)
        assert "schema_version" in data
        assert "storyboard_id" in data
        scene = data["scenes"][0]
        assert "scene_id" in scene
        assert "duration_seconds" in scene
        assert "reference_asset_ids" in scene["image"]
        assert "first_frame_asset_id" in scene["video"]

    def test_json_string_roundtrip(self):
        bundle = _build_bundle()
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored == bundle

    def test_json_string_matches_raw_json(self):
        bundle = _build_bundle()
        pydantic_json = bundle.model_dump_json(by_alias=True)
        raw_data = bundle.model_dump(by_alias=True)
        raw_json = json.dumps(raw_data, separators=(",", ":"))
        # Both should produce equivalent JSON (modulo formatting)
        assert json.loads(pydantic_json) == json.loads(raw_json)


# ---------------------------------------------------------------------------
# Edge cases: scene counts
# ---------------------------------------------------------------------------


class TestSceneCountEdgeCases:
    def test_zero_scenes(self):
        bundle = _build_bundle(scenes=[])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert len(restored.scenes) == 0
        assert restored == bundle

    def test_one_scene(self):
        scene = SceneEntry(
            scene_id="solo",
            index=0,
            title="Solo",
            narration="Just one.",
            image=SceneImagePrompt(prompt="solo img"),
            video=SceneVideoPrompt(prompt="solo vid"),
        )
        bundle = _build_bundle(scenes=[scene])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert len(restored.scenes) == 1
        assert restored.scenes[0].scene_id == "solo"

    def test_twenty_scenes(self):
        scenes = []
        for i in range(20):
            scenes.append(
                SceneEntry(
                    scene_id=f"scene-{i:03d}",
                    index=i,
                    title=f"Scene {i}",
                    narration=f"Narration for scene {i}",
                    duration_seconds=float(i + 1),
                    locked=i % 5 == 0,
                    image=SceneImagePrompt(
                        prompt=f"Image prompt {i}",
                        seed=i,
                        size="1280x720",
                    ),
                    video=SceneVideoPrompt(
                        prompt=f"Video prompt {i}",
                        resolution="480P",
                        ratio="16:9",
                        duration=i + 1,
                    ),
                )
            )
        bundle = _build_bundle(scenes=scenes)
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert len(restored.scenes) == 20
        for i, s in enumerate(restored.scenes):
            assert s.scene_id == f"scene-{i:03d}"
            assert s.index == i
            assert s.duration_seconds == float(i + 1)
            assert s.locked == (i % 5 == 0)


# ---------------------------------------------------------------------------
# Fixture roundtrip: ski_lesson_bundle
# ---------------------------------------------------------------------------


class TestSkiLessonFixtureRoundtrip:
    """Validate that the real-world ski_lesson_bundle fixture round-trips."""

    def test_from_dict_to_model_to_json_to_model(self):
        """camelCase dict -> Pydantic -> JSON -> Pydantic preserves data."""
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        bundle = _bundle_from_raw(raw)

        # Serialize to JSON with camelCase aliases
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)

        # Core fields
        assert restored.schema_version == "1.0"
        assert restored.storyboard_id == "ski-lesson-storyboard"
        assert restored.workflow_id == "template-ski-lesson"
        assert restored.title == "冬季单板滑雪单脚蹬行教学"
        assert restored.source == "draft"

        # Scene
        assert len(restored.scenes) == 1
        scene = restored.scenes[0]
        assert scene.scene_id == "scene-001"
        assert scene.index == 0
        assert scene.locked is True
        assert scene.duration_seconds == 3.0

        # Image prompt
        assert scene.image.prompt.startswith("写实电影感")
        assert scene.image.negative_prompt is not None
        assert scene.image.provider == "dashscope"
        assert scene.image.model == "qwen-image-3.0"
        assert scene.image.size == "1280x720"
        assert scene.image.seed == -1
        assert scene.image.reference_asset_ids == []

        # Video prompt
        assert scene.video.prompt.startswith("保持首帧")
        assert scene.video.provider == "wan3"
        assert scene.video.model == "wan3.0-video"
        assert scene.video.resolution == "480P"
        assert scene.video.ratio == "16:9"
        assert scene.video.duration == 3
        assert scene.video.audio is False
        assert scene.video.first_frame_asset_id is None

        # Transition
        assert scene.transition is not None
        assert scene.transition.type == "crossfade"
        assert scene.transition.duration == 0.3

        # Metadata
        assert scene.metadata["variantCount"] == 2
        assert scene.metadata["outputStrategy"] == "two_variants_to_video"

    def test_json_matches_original_dict_keys(self):
        """The JSON output should have the same top-level keys as the original dict."""
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        bundle = _bundle_from_raw(raw)
        json_str = bundle.model_dump_json(by_alias=True)
        parsed = json.loads(json_str)

        # All original dict keys should be present in the serialized output
        for key in raw:
            assert key in parsed, f"Missing key: {key}"

        # Scene-level keys
        original_scene_keys = set(raw["scenes"][0].keys())
        serialized_scene_keys = set(parsed["scenes"][0].keys())
        assert original_scene_keys == serialized_scene_keys

    def test_image_prompt_preserves_long_text(self):
        """Long Chinese prompts should survive roundtrip without truncation."""
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        original_prompt = raw["scenes"][0]["image"]["prompt"]
        bundle = _bundle_from_raw(raw)
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes[0].image.prompt == original_prompt

    def test_video_prompt_preserves_long_text(self):
        """Long Chinese video prompts should survive roundtrip without truncation."""
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        original_prompt = raw["scenes"][0]["video"]["prompt"]
        bundle = _bundle_from_raw(raw)
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes[0].video.prompt == original_prompt

    def test_negative_prompt_preserved(self):
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        original_neg = raw["negativePrompt"]
        bundle = _bundle_from_raw(raw)
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.negative_prompt == original_neg

    def test_global_style_preserved(self):
        raw = deepcopy(SKI_LESSON_SCENE_BUNDLE)
        original_style = raw["globalStyle"]
        bundle = _bundle_from_raw(raw)
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.global_style == original_style


# ---------------------------------------------------------------------------
# Transition model
# ---------------------------------------------------------------------------


class TestSceneTransition:
    def test_transition_roundtrip(self):
        t = SceneTransition(type="dissolve", duration=0.5)
        json_str = t.model_dump_json(by_alias=True)
        restored = SceneTransition.model_validate_json(json_str)
        assert restored == t

    def test_transition_in_scene_roundtrip(self):
        scene = SceneEntry(
            scene_id="t1",
            index=0,
            title="T",
            narration="N",
            image=SceneImagePrompt(prompt="i"),
            video=SceneVideoPrompt(prompt="v"),
            transition=SceneTransition(type="cut", duration=0.0),
        )
        bundle = _build_bundle(scenes=[scene])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        t = restored.scenes[0].transition
        assert t is not None
        assert t.type == "cut"
        assert t.duration == 0.0

    def test_none_transition_omitted_or_null(self):
        scene = SceneEntry(
            scene_id="no-t",
            index=0,
            title="T",
            narration="N",
            image=SceneImagePrompt(prompt="i"),
            video=SceneVideoPrompt(prompt="v"),
        )
        bundle = _build_bundle(scenes=[scene])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes[0].transition is None
        # In JSON, the key should either be absent or null
        parsed = json.loads(json_str)
        scene_json = parsed["scenes"][0]
        assert "transition" not in scene_json or scene_json["transition"] is None


# ---------------------------------------------------------------------------
# Metadata handling
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_roundtrip(self):
        scene = SceneEntry(
            scene_id="m1",
            index=0,
            title="T",
            narration="N",
            image=SceneImagePrompt(prompt="i"),
            video=SceneVideoPrompt(prompt="v"),
            metadata={"key": "value", "count": 42, "nested": {"a": True}},
        )
        bundle = _build_bundle(scenes=[scene])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes[0].metadata["key"] == "value"
        assert restored.scenes[0].metadata["count"] == 42
        assert restored.scenes[0].metadata["nested"]["a"] is True

    def test_empty_metadata_roundtrip(self):
        scene = SceneEntry(
            scene_id="e1",
            index=0,
            title="T",
            narration="N",
            image=SceneImagePrompt(prompt="i"),
            video=SceneVideoPrompt(prompt="v"),
        )
        bundle = _build_bundle(scenes=[scene])
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes[0].metadata == {}
