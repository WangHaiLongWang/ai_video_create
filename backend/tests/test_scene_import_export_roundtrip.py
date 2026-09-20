"""SCENE-005: JSON/Markdown/CSV/Text import/export roundtrip tests.

Validates:
- Bundle -> JSON -> import -> compare (full roundtrip)
- Bundle -> Markdown -> verify format
- Bundle -> CSV -> import -> compare (full roundtrip)
- Bundle -> Text -> import -> compare (prompts only)
- Chinese characters preserved in all formats
- Empty scenes handled correctly
- Large bundle (20 scenes) performance
- Edge cases: invalid JSON, missing fields, special characters
"""

from __future__ import annotations

import json
import time

import pytest

from backend.app.schemas.scene_bundle import (
    SceneImagePrompt,
    SceneVideoPrompt,
    SceneEntry,
    ScenePromptBundle,
)
from backend.app.schemas.scene_exporter import (
    export_to_csv,
    export_to_json,
    export_to_jsonl,
    export_to_markdown,
    export_to_qwen_jsonl,
    export_to_text,
    export_to_wan3_jsonl,
    import_from_csv,
    import_from_json,
    import_from_text,
    SceneImportError,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_bundle(*, scenes: list[SceneEntry] | None = None) -> ScenePromptBundle:
    """Create a reusable test bundle with sensible defaults."""
    if scenes is None:
        scenes = [
            SceneEntry(
                scene_id="s1",
                index=1,
                title="Opening",
                narration="The sun rises over the mountains.",
                duration_seconds=5.0,
                locked=False,
                image=SceneImagePrompt(
                    prompt="A sunrise over misty mountains",
                    negative_prompt="dark",
                    model="qwen-image-3.0",
                    size="1280x720",
                ),
                video=SceneVideoPrompt(
                    prompt="Slow pan across mountain range at dawn",
                    model="wan3.0-video",
                    resolution="480P",
                    ratio="16:9",
                    duration=5,
                ),
            ),
            SceneEntry(
                scene_id="s2",
                index=2,
                title="Journey",
                narration="A traveler walks along a winding path.",
                duration_seconds=8.0,
                locked=True,
                image=SceneImagePrompt(
                    prompt="A traveler on a winding forest path",
                    model="qwen-image-3.0",
                    size="1280x720",
                ),
                video=SceneVideoPrompt(
                    prompt="Tracking shot following a traveler through a forest",
                    resolution="720P",
                    duration=8,
                ),
            ),
        ]
    return ScenePromptBundle(
        storyboard_id="sb-001",
        workflow_id="wf-001",
        execution_id="ex-001",
        title="Test Storyboard",
        global_style="cinematic, warm tones",
        negative_prompt="blurry, low quality",
        scenes=scenes,
        exported_at="2025-01-15T10:00:00Z",
        source="draft",
    )


def _make_chinese_bundle() -> ScenePromptBundle:
    """Bundle with Chinese characters for UTF-8 testing."""
    return ScenePromptBundle(
        storyboard_id="sb-cn-001",
        workflow_id="wf-cn-001",
        execution_id="ex-cn-001",
        title="冬季单板滑雪教学",
        global_style="写实电影感，晴朗冬季白天",
        negative_prompt="第三个人，背景人物，人群",
        scenes=[
            SceneEntry(
                scene_id="cn-s1",
                index=0,
                title="开场介绍",
                narration="欢迎来到冬季单板滑雪教学课程。",
                duration_seconds=3.0,
                locked=True,
                image=SceneImagePrompt(
                    prompt="写实电影感，滑雪者在雪坡上准备出发",
                    negative_prompt="模糊，低质量",
                    model="qwen-image-3.0",
                    size="1280x720",
                ),
                video=SceneVideoPrompt(
                    prompt="保持首帧，滑雪者开始滑行",
                    model="wan3.0-video",
                    resolution="480P",
                    ratio="16:9",
                    duration=3,
                    audio=False,
                ),
            ),
            SceneEntry(
                scene_id="cn-s2",
                index=1,
                title="技术讲解",
                narration="单脚蹬行是基础动作。",
                duration_seconds=5.0,
                image=SceneImagePrompt(
                    prompt="滑雪者单脚蹬行的特写镜头",
                    model="qwen-image-3.0",
                    size="1280x720",
                ),
                video=SceneVideoPrompt(
                    prompt="滑雪者反复练习单脚蹬行",
                    resolution="480P",
                    duration=5,
                ),
            ),
        ],
    )


def _make_special_chars_bundle() -> ScenePromptBundle:
    """Bundle with special characters in prompts."""
    return ScenePromptBundle(
        storyboard_id="sb-special",
        workflow_id="wf-special",
        execution_id="ex-special",
        title="Special Characters: <>&\"'{}[]",
        scenes=[
            SceneEntry(
                scene_id="sp1",
                index=0,
                title='Quote test: "double" and \'single\'',
                narration="Newline\nhere and tab\there.",
                duration_seconds=5.0,
                image=SceneImagePrompt(
                    prompt="Image with <html> &amp; entities",
                ),
                video=SceneVideoPrompt(
                    prompt='Video with commas, "quotes", and\nnewlines',
                ),
            ),
        ],
    )


def _make_empty_bundle() -> ScenePromptBundle:
    """Bundle with zero scenes."""
    return ScenePromptBundle(
        storyboard_id="sb-empty",
        workflow_id="wf-empty",
        execution_id="ex-empty",
        title="Empty Bundle",
        scenes=[],
    )


def _make_large_bundle(scene_count: int = 20) -> ScenePromptBundle:
    """Bundle with many scenes for performance testing."""
    scenes = []
    for i in range(scene_count):
        scenes.append(
            SceneEntry(
                scene_id=f"scene-{i:03d}",
                index=i,
                title=f"Scene {i}",
                narration=f"Narration for scene number {i} with some detail.",
                duration_seconds=float(i + 1),
                locked=i % 5 == 0,
                image=SceneImagePrompt(
                    prompt=f"Image prompt for scene {i}: detailed description of the scene",
                    negative_prompt=f"Negative for scene {i}",
                    model="qwen-image-3.0",
                    size="1280x720",
                    seed=i,
                ),
                video=SceneVideoPrompt(
                    prompt=f"Video prompt for scene {i}: camera movement description",
                    model="wan3.0-video",
                    resolution="480P",
                    ratio="16:9",
                    duration=i + 1,
                ),
            )
        )
    return ScenePromptBundle(
        storyboard_id="sb-large",
        workflow_id="wf-large",
        execution_id="ex-large",
        title="Large Bundle",
        global_style="cinematic",
        scenes=scenes,
    )


# ---------------------------------------------------------------------------
# JSON roundtrip
# ---------------------------------------------------------------------------


class TestJsonRoundtrip:
    """Bundle -> JSON -> import_from_json -> compare."""

    def test_basic_roundtrip(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored == original

    def test_preserves_storyboard_id(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored.storyboard_id == "sb-001"
        assert restored.workflow_id == "wf-001"
        assert restored.execution_id == "ex-001"

    def test_preserves_title_and_metadata(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored.title == "Test Storyboard"
        assert restored.global_style == "cinematic, warm tones"
        assert restored.negative_prompt == "blurry, low quality"

    def test_preserves_scene_count(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert len(restored.scenes) == 2

    def test_preserves_scene_fields(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        s = restored.scenes[0]
        assert s.scene_id == "s1"
        assert s.index == 1
        assert s.title == "Opening"
        assert s.narration == "The sun rises over the mountains."
        assert s.duration_seconds == 5.0
        assert s.locked is False

    def test_preserves_image_prompt_fields(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        img = restored.scenes[0].image
        assert img.prompt == "A sunrise over misty mountains"
        assert img.negative_prompt == "dark"
        assert img.model == "qwen-image-3.0"
        assert img.size == "1280x720"

    def test_preserves_video_prompt_fields(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        vid = restored.scenes[0].video
        assert vid.prompt == "Slow pan across mountain range at dawn"
        assert vid.model == "wan3.0-video"
        assert vid.resolution == "480P"
        assert vid.ratio == "16:9"
        assert vid.duration == 5

    def test_preserves_locked_flag(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored.scenes[0].locked is False
        assert restored.scenes[1].locked is True

    def test_roundtrip_is_idempotent(self):
        """Export -> import -> export -> import produces same result."""
        original = _make_bundle()
        json1 = export_to_json(original)
        restored1 = import_from_json(json1)
        json2 = export_to_json(restored1)
        restored2 = import_from_json(json2)
        assert restored1 == restored2

    def test_json_output_is_valid_json(self):
        original = _make_bundle()
        json_str = export_to_json(original)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "scenes" in parsed


# ---------------------------------------------------------------------------
# Markdown format verification
# ---------------------------------------------------------------------------


class TestMarkdownFormat:
    """Bundle -> Markdown -> verify format (Markdown is not re-imported)."""

    def test_contains_title(self):
        md = export_to_markdown(_make_bundle())
        assert md.startswith("# Test Storyboard")

    def test_contains_global_style(self):
        md = export_to_markdown(_make_bundle())
        assert "Global Style: cinematic, warm tones" in md

    def test_contains_negative_prompt(self):
        md = export_to_markdown(_make_bundle())
        assert "Negative: blurry, low quality" in md

    def test_contains_scene_headings(self):
        md = export_to_markdown(_make_bundle())
        assert "## Scene 1: Opening" in md
        assert "## Scene 2: Journey" in md

    def test_contains_narration(self):
        md = export_to_markdown(_make_bundle())
        assert "**Narration:** The sun rises over the mountains." in md

    def test_contains_duration(self):
        md = export_to_markdown(_make_bundle())
        assert "**Duration:** 5.0s" in md
        assert "**Duration:** 8.0s" in md

    def test_contains_image_prompt(self):
        md = export_to_markdown(_make_bundle())
        assert "**Image Prompt:** A sunrise over misty mountains" in md

    def test_contains_video_prompt(self):
        md = export_to_markdown(_make_bundle())
        assert "**Video Prompt:** Slow pan across mountain range at dawn" in md

    def test_horizontal_rules_between_scenes(self):
        md = export_to_markdown(_make_bundle())
        lines = md.split("\n")
        hr_count = sum(1 for line in lines if line.strip() == "---")
        # 2 scenes -> 1 horizontal rule between them
        assert hr_count == 1

    def test_chinese_characters_preserved(self):
        bundle = _make_chinese_bundle()
        md = export_to_markdown(bundle)
        assert "冬季单板滑雪教学" in md
        assert "写实电影感" in md
        assert "单脚蹬行" in md

    def test_empty_bundle(self):
        md = export_to_markdown(_make_empty_bundle())
        assert "# Empty Bundle" in md
        # No scene sections
        assert "## Scene" not in md

    def test_single_scene_no_horizontal_rule(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="solo", index=0, title="Solo", narration="Just one.",
                image=SceneImagePrompt(prompt="img"),
                video=SceneVideoPrompt(prompt="vid"),
            ),
        ])
        md = export_to_markdown(bundle)
        assert "## Scene 0: Solo" in md
        assert "---" not in md


# ---------------------------------------------------------------------------
# CSV roundtrip
# ---------------------------------------------------------------------------


class TestCsvRoundtrip:
    """Bundle -> CSV -> import_from_csv -> compare."""

    def test_basic_roundtrip(self):
        original = _make_bundle()
        csv_str = export_to_csv(original)
        restored = import_from_csv(csv_str)
        # CSV roundtrip loses some fields (provider, model, etc.) - compare core fields
        assert len(restored.scenes) == len(original.scenes)
        for orig_scene, rest_scene in zip(original.scenes, restored.scenes):
            assert rest_scene.scene_id == orig_scene.scene_id
            assert rest_scene.index == orig_scene.index
            assert rest_scene.title == orig_scene.title
            assert rest_scene.narration == orig_scene.narration
            assert rest_scene.duration_seconds == orig_scene.duration_seconds
            assert rest_scene.locked == orig_scene.locked
            assert rest_scene.image.prompt == orig_scene.image.prompt
            assert rest_scene.video.prompt == orig_scene.video.prompt

    def test_starts_with_bom(self):
        csv_str = export_to_csv(_make_bundle())
        assert csv_str.startswith("﻿")

    def test_header_row(self):
        csv_str = export_to_csv(_make_bundle())
        header = csv_str.split("\n")[0].lstrip("﻿")
        assert header == "sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked"

    def test_row_count(self):
        csv_str = export_to_csv(_make_bundle())
        rows = [r for r in csv_str.strip().split("\n") if r.strip()]
        assert len(rows) == 3  # header + 2 data rows

    def test_preserves_scene_ids(self):
        csv_str = export_to_csv(_make_bundle())
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].scene_id == "s1"
        assert restored.scenes[1].scene_id == "s2"

    def test_preserves_locked_flags(self):
        csv_str = export_to_csv(_make_bundle())
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].locked is False
        assert restored.scenes[1].locked is True

    def test_chinese_characters_preserved(self):
        bundle = _make_chinese_bundle()
        csv_str = export_to_csv(bundle)
        assert "冬季单板滑雪教学" in csv_str or "开场介绍" in csv_str
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].title == "开场介绍"
        assert restored.scenes[0].image.prompt == "写实电影感，滑雪者在雪坡上准备出发"

    def test_special_chars_escaped(self):
        bundle = _make_special_chars_bundle()
        csv_str = export_to_csv(bundle)
        # Commas and quotes in prompts should be CSV-escaped
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].video.prompt == 'Video with commas, "quotes", and\nnewlines'

    def test_bundle_metadata_defaults(self):
        """CSV import creates bundle with imported-csv metadata."""
        csv_str = export_to_csv(_make_bundle())
        restored = import_from_csv(csv_str)
        assert restored.storyboard_id == "imported-csv"
        assert restored.workflow_id == "imported-csv"
        assert restored.title == "Imported from CSV"

    def test_empty_bundle_produces_only_header(self):
        csv_str = export_to_csv(_make_empty_bundle())
        rows = [r for r in csv_str.strip().split("\n") if r.strip()]
        assert len(rows) == 1  # header only

    def test_import_empty_csv_raises(self):
        with pytest.raises(SceneImportError, match="at least one data row"):
            import_from_csv("sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked\n")


# ---------------------------------------------------------------------------
# Text import
# ---------------------------------------------------------------------------


class TestTextRoundtrip:
    """Bundle -> Text -> import_from_text -> compare prompts."""

    def test_basic_roundtrip(self):
        original = _make_bundle()
        text_str = export_to_text(original)
        restored = import_from_text(text_str)
        assert len(restored.scenes) == len(original.scenes)
        for orig_scene, rest_scene in zip(original.scenes, restored.scenes):
            assert rest_scene.index == orig_scene.index
            assert rest_scene.image.prompt == orig_scene.image.prompt
            assert rest_scene.video.prompt == orig_scene.video.prompt

    def test_scene_markers(self):
        text_str = export_to_text(_make_bundle())
        assert "[Scene 1]" in text_str
        assert "[Scene 2]" in text_str

    def test_contains_image_and_video_prompts(self):
        text_str = export_to_text(_make_bundle())
        assert "Image: A sunrise over misty mountains" in text_str
        assert "Video: Slow pan across mountain range at dawn" in text_str

    def test_import_metadata_defaults(self):
        text_str = export_to_text(_make_bundle())
        restored = import_from_text(text_str)
        assert restored.storyboard_id == "imported-text"
        assert restored.title == "Imported from Text"

    def test_import_narration_defaults_to_image_prompt(self):
        """Text format has no narration; import uses image prompt."""
        text_str = export_to_text(_make_bundle())
        restored = import_from_text(text_str)
        # Narration should be set to the image prompt
        assert restored.scenes[0].narration == "A sunrise over misty mountains"

    def test_chinese_characters_preserved(self):
        bundle = _make_chinese_bundle()
        text_str = export_to_text(bundle)
        assert "写实电影感" in text_str
        assert "保持首帧" in text_str
        restored = import_from_text(text_str)
        assert restored.scenes[0].image.prompt == "写实电影感，滑雪者在雪坡上准备出发"
        assert restored.scenes[0].video.prompt == "保持首帧，滑雪者开始滑行"

    def test_empty_bundle_raises(self):
        text_str = export_to_text(_make_empty_bundle())
        with pytest.raises(SceneImportError, match="No \\[Scene N\\] blocks found"):
            import_from_text(text_str)


# ---------------------------------------------------------------------------
# Empty scenes handling
# ---------------------------------------------------------------------------


class TestEmptyBundle:
    """Test behavior with zero scenes."""

    def test_json_roundtrip(self):
        original = _make_empty_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert len(restored.scenes) == 0
        assert restored.title == "Empty Bundle"

    def test_csv_export_has_header_only(self):
        csv_str = export_to_csv(_make_empty_bundle())
        lines = [l for l in csv_str.strip().split("\n") if l.strip()]
        assert len(lines) == 1  # header only

    def test_text_export_is_empty(self):
        text_str = export_to_text(_make_empty_bundle())
        assert text_str.strip() == ""

    def test_markdown_export_has_title_only(self):
        md = export_to_markdown(_make_empty_bundle())
        assert "# Empty Bundle" in md
        assert "## Scene" not in md


# ---------------------------------------------------------------------------
# Large bundle performance
# ---------------------------------------------------------------------------


class TestLargeBundlePerformance:
    """Performance tests for bundles with many scenes."""

    def test_json_roundtrip_20_scenes(self):
        original = _make_large_bundle(20)
        start = time.time()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        elapsed = time.time() - start
        assert len(restored.scenes) == 20
        assert elapsed < 5.0, f"JSON roundtrip took {elapsed:.2f}s, expected < 5s"

    def test_csv_roundtrip_20_scenes(self):
        original = _make_large_bundle(20)
        start = time.time()
        csv_str = export_to_csv(original)
        restored = import_from_csv(csv_str)
        elapsed = time.time() - start
        assert len(restored.scenes) == 20
        assert elapsed < 5.0, f"CSV roundtrip took {elapsed:.2f}s, expected < 5s"

    def test_text_roundtrip_20_scenes(self):
        original = _make_large_bundle(20)
        start = time.time()
        text_str = export_to_text(original)
        restored = import_from_text(text_str)
        elapsed = time.time() - start
        assert len(restored.scenes) == 20
        assert elapsed < 5.0, f"Text roundtrip took {elapsed:.2f}s, expected < 5s"

    def test_json_roundtrip_preserves_all_scene_ids(self):
        original = _make_large_bundle(20)
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        for i in range(20):
            assert restored.scenes[i].scene_id == f"scene-{i:03d}"
            assert restored.scenes[i].index == i

    def test_all_scenes_preserve_locked_status(self):
        original = _make_large_bundle(20)
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        for i in range(20):
            assert restored.scenes[i].locked == (i % 5 == 0)


# ---------------------------------------------------------------------------
# Edge cases: import errors
# ---------------------------------------------------------------------------


class TestImportErrors:
    """Test error handling for invalid import data."""

    def test_import_invalid_json_string(self):
        with pytest.raises(SceneImportError, match="Invalid JSON"):
            import_from_json("this is not json {{{")

    def test_import_json_array_instead_of_object(self):
        with pytest.raises(SceneImportError, match="root must be an object"):
            import_from_json('["a", "b", "c"]')

    def test_import_json_string_instead_of_object(self):
        with pytest.raises(SceneImportError, match="root must be an object"):
            import_from_json('"just a string"')

    def test_import_json_missing_required_fields(self):
        with pytest.raises(SceneImportError, match="Validation failed"):
            import_from_json('{"title": "Only Title"}')

    def test_import_json_wrong_type_for_field(self):
        bad = {
            "schemaVersion": "1.0",
            "storyboardId": "sb",
            "workflowId": "wf",
            "executionId": "ex",
            "title": "T",
            "scenes": "not a list",
        }
        with pytest.raises(SceneImportError, match="Validation failed"):
            import_from_json(json.dumps(bad))

    def test_import_csv_wrong_header(self):
        bad_csv = "col1,col2,col3\na,b,c\n"
        with pytest.raises(SceneImportError, match="Unexpected CSV header"):
            import_from_csv(bad_csv)

    def test_import_csv_too_few_rows(self):
        header_only = "sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked\n"
        with pytest.raises(SceneImportError, match="at least one data row"):
            import_from_csv(header_only)

    def test_import_csv_too_few_columns(self):
        csv = "sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked\ns1,0,T,N,5,I,V\n"
        with pytest.raises(SceneImportError, match="expected 8 columns"):
            import_from_csv(csv)

    def test_import_text_no_scene_blocks(self):
        with pytest.raises(SceneImportError, match="No \\[Scene N\\] blocks found"):
            import_from_text("Just some random text without scene blocks")

    def test_import_text_empty_string(self):
        with pytest.raises(SceneImportError, match="No \\[Scene N\\] blocks found"):
            import_from_text("")


# ---------------------------------------------------------------------------
# Edge cases: special characters
# ---------------------------------------------------------------------------


class TestSpecialCharacters:
    """Test handling of special characters in prompts."""

    def test_json_roundtrip_special_chars(self):
        original = _make_special_chars_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored.title == 'Special Characters: <>&"\'{}[]'
        assert restored.scenes[0].title == "Quote test: \"double\" and 'single'"

    def test_csv_roundtrip_special_chars(self):
        original = _make_special_chars_bundle()
        csv_str = export_to_csv(original)
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].video.prompt == 'Video with commas, "quotes", and\nnewlines'

    def test_jsonl_preserves_special_chars(self):
        original = _make_special_chars_bundle()
        jsonl_str = export_to_jsonl(original)
        for line in jsonl_str.strip().split("\n"):
            obj = json.loads(line)
            assert "image" in obj
            assert "prompt" in obj["image"]

    def test_json_roundtrip_html_entities(self):
        original = _make_special_chars_bundle()
        json_str = export_to_json(original)
        restored = import_from_json(json_str)
        assert restored.scenes[0].image.prompt == "Image with <html> &amp; entities"


# ---------------------------------------------------------------------------
# UTF-8 encoding
# ---------------------------------------------------------------------------


class TestUtf8Encoding:
    """Verify UTF-8 handling across all formats."""

    def test_json_utf8(self):
        bundle = _make_chinese_bundle()
        json_str = export_to_json(bundle)
        # Verify the string is valid UTF-8
        json_str.encode("utf-8")
        restored = import_from_json(json_str)
        assert restored.title == "冬季单板滑雪教学"

    def test_csv_utf8(self):
        bundle = _make_chinese_bundle()
        csv_str = export_to_csv(bundle)
        csv_str.encode("utf-8")
        restored = import_from_csv(csv_str)
        assert restored.scenes[0].title == "开场介绍"

    def test_text_utf8(self):
        bundle = _make_chinese_bundle()
        text_str = export_to_text(bundle)
        text_str.encode("utf-8")
        restored = import_from_text(text_str)
        assert restored.scenes[0].image.prompt == "写实电影感，滑雪者在雪坡上准备出发"

    def test_markdown_utf8(self):
        bundle = _make_chinese_bundle()
        md = export_to_markdown(bundle)
        md.encode("utf-8")
        assert "冬季单板滑雪教学" in md
        assert "写实电影感，晴朗冬季白天" in md


# ---------------------------------------------------------------------------
# Cross-format: JSON export produces re-importable output
# ---------------------------------------------------------------------------


class TestJsonReimportable:
    """Verify that export_to_json output can be directly passed to import_from_json."""

    def test_export_output_importable(self):
        original = _make_bundle()
        exported = export_to_json(original)
        imported = import_from_json(exported)
        assert imported == original

    def test_chinese_bundle_reimportable(self):
        original = _make_chinese_bundle()
        exported = export_to_json(original)
        imported = import_from_json(exported)
        assert imported == original

    def test_large_bundle_reimportable(self):
        original = _make_large_bundle(20)
        exported = export_to_json(original)
        imported = import_from_json(exported)
        assert len(imported.scenes) == 20
        for orig, imp in zip(original.scenes, imported.scenes):
            assert imp.scene_id == orig.scene_id
            assert imp.image.prompt == orig.image.prompt
            assert imp.video.prompt == orig.video.prompt


# ---------------------------------------------------------------------------
# JSONL format
# ---------------------------------------------------------------------------


class TestJsonlFormat:
    """Verify JSONL export format."""

    def test_one_line_per_scene(self):
        bundle = _make_bundle()
        jsonl = export_to_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_valid_json_per_line(self):
        bundle = _make_bundle()
        jsonl = export_to_jsonl(bundle)
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "sceneId" in obj or "scene_id" in obj
            assert "prompt" in obj.get("image", {})

    def test_chinese_preserved_in_jsonl(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_jsonl(bundle)
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert obj.get("image", {}).get("prompt")


# ---------------------------------------------------------------------------
# Qwen Image JSONL format verification (SCENE-006)
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402  (local import for security assertions)

# Re-use helpers already defined above: _make_bundle, _make_chinese_bundle, etc.


class TestQwenJsonlFormat:
    """Verify Qwen-specific JSONL request preview format.

    The Qwen JSONL output is a *request preview*, NOT a full bundle export.
    Each line is a flat JSON object suitable for the Qwen Image API.
    """

    # ---- basic structure ----

    def test_each_line_is_valid_json(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)  # must not raise
            assert isinstance(obj, dict)

    def test_one_line_per_scene(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_multiple_scenes_produce_multiple_lines(self):
        bundle = _make_large_bundle(10)
        jsonl = export_to_qwen_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        assert len(lines) == 10

    def test_empty_bundle_produces_no_lines(self):
        jsonl = export_to_qwen_jsonl(_make_empty_bundle())
        assert jsonl.strip() == ""

    # ---- required fields present ----

    def test_required_fields_model_prompt_size(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "model" in obj, "model field missing"
            assert "prompt" in obj, "prompt field missing"
            assert "size" in obj, "size field missing"

    def test_negative_prompt_included(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "negative_prompt" in obj, "negative_prompt field missing"
            assert isinstance(obj["negative_prompt"], str)

    def test_negative_prompt_empty_string_when_none(self):
        """Scene without negative_prompt gets an empty string."""
        jsonl = export_to_qwen_jsonl(_make_bundle())
        # Scene 2 in _make_bundle has no negative_prompt
        line2 = jsonl.strip().split("\n")[1]
        obj = json.loads(line2)
        assert obj["negative_prompt"] == ""

    def test_negative_prompt_populated_when_set(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        # Scene 1 has negative_prompt="dark"
        line1 = jsonl.strip().split("\n")[0]
        obj = json.loads(line1)
        assert obj["negative_prompt"] == "dark"

    def test_seed_included_when_explicit(self):
        bundle = _make_large_bundle(3)
        jsonl = export_to_qwen_jsonl(bundle)
        # All scenes in _make_large_bundle have seed set (0, 1, 2)
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "seed" in obj, "seed should be present when explicitly set"
            assert isinstance(obj["seed"], int)

    def test_seed_omitted_when_default(self):
        bundle = _make_bundle()
        # _make_bundle scenes have default seed (-1)
        jsonl = export_to_qwen_jsonl(bundle)
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "seed" not in obj, "seed should be omitted when -1 (random)"

    # ---- size format ----

    def test_size_format_width_x_height(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        size_re = _re.compile(r"^\d+x\d+$")
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert size_re.match(obj["size"]), f"Invalid size format: {obj['size']}"

    def test_default_size_is_1280x720(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_qwen_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["size"] == "1280x720"

    def test_custom_size_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test", size="1920x1080"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_qwen_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["size"] == "1920x1080"

    # ---- model defaults ----

    def test_default_model(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_qwen_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["model"] == "qwen-image-3.0"

    def test_custom_model_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test", model="qwen-image-v2"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_qwen_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["model"] == "qwen-image-v2"

    # ---- security: no secrets / no absolute paths ----

    def test_no_api_key_in_any_line(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        key_patterns = [
            _re.compile(r"sk-[A-Za-z0-9]{16,}"),
            _re.compile(r"api_key\s*[=:]\s*\S+", _re.IGNORECASE),
            _re.compile(r"apikey\s*:\s*\S+", _re.IGNORECASE),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in key_patterns:
                assert not pat.search(line), f"API key detected in Qwen JSONL line"

    def test_no_signed_url_in_any_line(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        sig_patterns = [
            _re.compile(r"[?&]Signature=[^&]+"),
            _re.compile(r"[?&]X-Amz-Signature=[^&]+"),
            _re.compile(r"[?&]sig=[^&]+"),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in sig_patterns:
                assert not pat.search(line), f"Signed URL detected in Qwen JSONL line"

    def test_no_absolute_path_in_any_line(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        path_patterns = [
            _re.compile(r"[A-Z]:\\[^\"'\s,]+"),          # Windows
            _re.compile(r"/(?:home|tmp|var|etc|usr|opt)/[^\"'\s,]+"),  # Unix
        ]
        for line in jsonl.strip().split("\n"):
            for pat in path_patterns:
                assert not pat.search(line), f"Absolute path detected in Qwen JSONL line"

    def test_no_api_key_variable_in_any_line(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        var_patterns = [
            _re.compile(r"\$\{[A-Z_]*API[_-]?KEY[A-Z_]*\}", _re.IGNORECASE),
            _re.compile(r"\$[A-Z_]*API[_-]?KEY[A-Z_]*", _re.IGNORECASE),
            _re.compile(r"process\.env\."),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in var_patterns:
                assert not pat.search(line), f"API key variable detected in Qwen JSONL line"

    def test_no_bundle_metadata_leaked(self):
        """Qwen JSONL should not contain storyboard/workflow/execution IDs."""
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "storyboard_id" not in obj
            assert "workflow_id" not in obj
            assert "execution_id" not in obj
            assert "storyboardId" not in obj
            assert "workflowId" not in obj
            assert "executionId" not in obj

    # ---- Chinese / UTF-8 ----

    def test_chinese_prompts_preserved(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_qwen_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        # First scene has Chinese prompt
        obj0 = json.loads(lines[0])
        assert "写实电影感" in obj0["prompt"]
        # Negative prompt also Chinese
        assert "模糊" in obj0["negative_prompt"]

    def test_chinese_negative_prompt_preserved(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_qwen_jsonl(bundle)
        obj = json.loads(jsonl.strip().split("\n")[0])
        assert obj["negative_prompt"] == "模糊，低质量"

    def test_utf8_encoding_valid(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_qwen_jsonl(bundle)
        # Ensure it encodes as valid UTF-8
        jsonl.encode("utf-8")

    def test_chinese_ensure_ascii_false(self):
        """Chinese characters should appear as-is, not \\uXXXX escaped."""
        bundle = _make_chinese_bundle()
        jsonl = export_to_qwen_jsonl(bundle)
        assert "\\u" not in jsonl, "Chinese chars should not be unicode-escaped"

    # ---- format completeness ----

    def test_output_ends_with_newline(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        assert jsonl.endswith("\n")

    def test_no_trailing_comma(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            assert not line.endswith(","), "JSONL lines must not end with comma"

    def test_no_bundle_level_fields(self):
        """Qwen JSONL is per-request; should NOT contain bundle-level fields."""
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "title" not in obj
            assert "scenes" not in obj
            assert "global_style" not in obj
            assert "globalStyle" not in obj


# ---------------------------------------------------------------------------
# Wan3 JSONL format verification (SCENE-007)
# ---------------------------------------------------------------------------


class TestWan3JsonlFormat:
    """Verify Wan3-specific JSONL request preview format.

    The Wan3 JSONL output is a *request preview*, NOT a full bundle export.
    Each line is a flat JSON object suitable for the Wan3 Video API.
    """

    # ---- basic structure ----

    def test_each_line_is_valid_json(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)  # must not raise
            assert isinstance(obj, dict)

    def test_one_line_per_scene(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_multiple_scenes_produce_multiple_lines(self):
        bundle = _make_large_bundle(10)
        jsonl = export_to_wan3_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        assert len(lines) == 10

    def test_empty_bundle_produces_no_lines(self):
        jsonl = export_to_wan3_jsonl(_make_empty_bundle())
        assert jsonl.strip() == ""

    # ---- required fields present ----

    def test_required_fields_model_prompt_resolution_ratio_duration(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "model" in obj, "model field missing"
            assert "prompt" in obj, "prompt field missing"
            assert "resolution" in obj, "resolution field missing"
            assert "ratio" in obj, "ratio field missing"
            assert "duration" in obj, "duration field missing"

    def test_model_default_value(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["model"] == "wan3.0-video"

    def test_model_custom_value_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test", model="wan3.5-video"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["model"] == "wan3.5-video"

    def test_resolution_default_value(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["resolution"] == "480P"

    def test_resolution_custom_value_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test", resolution="1080P"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["resolution"] == "1080P"

    def test_ratio_default_value(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["ratio"] == "adaptive"

    def test_ratio_custom_value_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test", ratio="16:9"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["ratio"] == "16:9"

    def test_duration_default_value(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["duration"] == 5

    def test_duration_custom_value_preserved(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test", duration=10),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert obj["duration"] == 10

    # ---- firstFrame / asset_id mapping ----

    def test_first_frame_asset_id_included_when_set(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(
                    prompt="test",
                    first_frame_asset_id="asset-abc-123",
                ),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert "firstFrame" in obj
        assert obj["firstFrame"] == "asset-abc-123"

    def test_first_frame_omitted_when_none(self):
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(prompt="test"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        assert "firstFrame" not in obj

    def test_first_frame_is_asset_id_not_path(self):
        """firstFrame must be an asset_id string, not a filesystem path."""
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T", narration="N",
                image=SceneImagePrompt(prompt="test"),
                video=SceneVideoPrompt(
                    prompt="test",
                    first_frame_asset_id="img_20250115_skier_001",
                ),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        obj = json.loads(jsonl.strip())
        first_frame = obj["firstFrame"]
        # Must not look like an absolute path
        assert not first_frame.startswith("/"), "firstFrame must not be an absolute path"
        assert not first_frame.startswith("C:\\"), "firstFrame must not be a Windows path"
        # Must be a string identifier
        assert isinstance(first_frame, str)
        assert len(first_frame) > 0

    def test_mixed_first_frame_scenes(self):
        """Some scenes have first_frame_asset_id, others don't."""
        bundle = _make_bundle(scenes=[
            SceneEntry(
                scene_id="s1", index=0, title="T1", narration="N1",
                image=SceneImagePrompt(prompt="test1"),
                video=SceneVideoPrompt(
                    prompt="test1",
                    first_frame_asset_id="asset-001",
                ),
            ),
            SceneEntry(
                scene_id="s2", index=1, title="T2", narration="N2",
                image=SceneImagePrompt(prompt="test2"),
                video=SceneVideoPrompt(prompt="test2"),
            ),
        ])
        jsonl = export_to_wan3_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        obj1 = json.loads(lines[0])
        obj2 = json.loads(lines[1])
        assert obj1["firstFrame"] == "asset-001"
        assert "firstFrame" not in obj2

    # ---- security: no secrets / no absolute paths ----

    def test_no_api_key_in_any_line(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        key_patterns = [
            _re.compile(r"sk-[A-Za-z0-9]{16,}"),
            _re.compile(r"api_key\s*[=:]\s*\S+", _re.IGNORECASE),
            _re.compile(r"apikey\s*:\s*\S+", _re.IGNORECASE),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in key_patterns:
                assert not pat.search(line), "API key detected in Wan3 JSONL line"

    def test_no_signed_url_in_any_line(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        sig_patterns = [
            _re.compile(r"[?&]Signature=[^&]+"),
            _re.compile(r"[?&]X-Amz-Signature=[^&]+"),
            _re.compile(r"[?&]sig=[^&]+"),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in sig_patterns:
                assert not pat.search(line), "Signed URL detected in Wan3 JSONL line"

    def test_no_absolute_path_in_any_line(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        path_patterns = [
            _re.compile(r"[A-Z]:\\[^\"'\s,]+"),          # Windows
            _re.compile(r"/(?:home|tmp|var|etc|usr|opt)/[^\"'\s,]+"),  # Unix
        ]
        for line in jsonl.strip().split("\n"):
            for pat in path_patterns:
                assert not pat.search(line), "Absolute path detected in Wan3 JSONL line"

    def test_no_api_key_variable_in_any_line(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        var_patterns = [
            _re.compile(r"\$\{[A-Z_]*API[_-]?KEY[A-Z_]*\}", _re.IGNORECASE),
            _re.compile(r"\$[A-Z_]*API[_-]?KEY[A-Z_]*", _re.IGNORECASE),
            _re.compile(r"process\.env\."),
        ]
        for line in jsonl.strip().split("\n"):
            for pat in var_patterns:
                assert not pat.search(line), "API key variable detected in Wan3 JSONL line"

    def test_no_bundle_metadata_leaked(self):
        """Wan3 JSONL should not contain storyboard/workflow/execution IDs."""
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "storyboard_id" not in obj
            assert "workflow_id" not in obj
            assert "execution_id" not in obj
            assert "storyboardId" not in obj
            assert "workflowId" not in obj
            assert "executionId" not in obj

    # ---- Chinese / UTF-8 ----

    def test_chinese_prompts_preserved(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_wan3_jsonl(bundle)
        lines = jsonl.strip().split("\n")
        obj0 = json.loads(lines[0])
        assert "写实电影感" in obj0["prompt"] or "滑雪者" in obj0["prompt"]

    def test_chinese_ensure_ascii_false(self):
        """Chinese characters should appear as-is, not \\uXXXX escaped."""
        bundle = _make_chinese_bundle()
        jsonl = export_to_wan3_jsonl(bundle)
        assert "\\u" not in jsonl, "Chinese chars should not be unicode-escaped"

    def test_utf8_encoding_valid(self):
        bundle = _make_chinese_bundle()
        jsonl = export_to_wan3_jsonl(bundle)
        jsonl.encode("utf-8")

    # ---- format completeness ----

    def test_output_ends_with_newline(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        assert jsonl.endswith("\n")

    def test_no_trailing_comma(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            assert not line.endswith(","), "JSONL lines must not end with comma"

    def test_no_bundle_level_fields(self):
        """Wan3 JSONL is per-request; should NOT contain bundle-level fields."""
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "title" not in obj
            assert "scenes" not in obj
            assert "global_style" not in obj
            assert "globalStyle" not in obj

    def test_no_image_fields_leaked(self):
        """Wan3 JSONL is for video; should NOT contain image-specific fields."""
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "size" not in obj, "Image size should not appear in Wan3 video JSONL"
            assert "negative_prompt" not in obj, "Negative prompt is image-specific"
            assert "seed" not in obj, "Seed is image-specific in this context"

    def test_no_scene_metadata_leaked(self):
        """Wan3 JSONL should not contain scene metadata like sceneId or narration."""
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "sceneId" not in obj
            assert "scene_id" not in obj
            assert "narration" not in obj
            assert "index" not in obj
            assert "locked" not in obj
