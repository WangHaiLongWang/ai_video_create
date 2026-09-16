"""Tests for ScenePromptBundle schemas, export utilities, and security scanner."""

import json

import pytest

from backend.app.schemas.scene_bundle import (
    SceneImagePrompt,
    ScenePromptBundle,
    SceneEntry,
    SceneVideoPrompt,
)
from backend.app.schemas.scene_exporter import (
    export_to_csv,
    export_to_json,
    export_to_jsonl,
    export_to_markdown,
    export_to_text,
    export_to_qwen_jsonl,
    export_to_wan3_jsonl,
    scan_bundle_security,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _make_bundle(**overrides) -> ScenePromptBundle:
    """Create a reusable test bundle with sensible defaults."""
    scenes = overrides.pop("scenes", [
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
    ])

    defaults = dict(
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
    defaults.update(overrides)
    return ScenePromptBundle(**defaults)


# ---------------------------------------------------------------------------
# Roundtrip validation
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_serialize_deserialize(self):
        bundle = _make_bundle()
        data = bundle.model_dump()
        restored = ScenePromptBundle(**data)
        assert restored.schema_version == "1.0"
        assert restored.storyboard_id == "sb-001"
        assert len(restored.scenes) == 2
        assert restored.scenes[0].scene_id == "s1"

    def test_json_roundtrip(self):
        bundle = _make_bundle()
        json_str = bundle.model_dump_json()
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored == bundle

    def test_scene_defaults(self):
        scene = SceneEntry(
            scene_id="x",
            index=0,
            title="T",
            narration="N",
            image=SceneImagePrompt(prompt="img"),
            video=SceneVideoPrompt(prompt="vid"),
        )
        assert scene.duration_seconds == 5.0
        assert scene.locked is False
        assert scene.transition is None
        assert scene.metadata == {}

    def test_image_defaults(self):
        img = SceneImagePrompt(prompt="hello")
        assert img.seed == -1
        assert img.negative_prompt is None
        assert img.reference_asset_ids == []

    def test_video_defaults(self):
        vid = SceneVideoPrompt(prompt="hello")
        assert vid.duration == 5
        assert vid.audio is True
        assert vid.seed == -1


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


class TestExportJson:
    def test_valid_json(self):
        bundle = _make_bundle()
        result = export_to_json(bundle)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_preserves_schema_version(self):
        bundle = _make_bundle()
        parsed = json.loads(export_to_json(bundle))
        assert parsed["schemaVersion"] == "1.0"

    def test_scene_count(self):
        bundle = _make_bundle()
        parsed = json.loads(export_to_json(bundle))
        assert len(parsed["scenes"]) == 2


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    def test_contains_title(self):
        md = export_to_markdown(_make_bundle())
        assert "# Test Storyboard" in md

    def test_contains_scene_titles(self):
        md = export_to_markdown(_make_bundle())
        assert "## Scene 1: Opening" in md
        assert "## Scene 2: Journey" in md

    def test_contains_prompts(self):
        md = export_to_markdown(_make_bundle())
        assert "A sunrise over misty mountains" in md
        assert "Slow pan across mountain range at dawn" in md

    def test_contains_global_style(self):
        md = export_to_markdown(_make_bundle())
        assert "Global Style: cinematic, warm tones" in md
        assert "Negative: blurry, low quality" in md

    def test_horizontal_rule_between_scenes(self):
        md = export_to_markdown(_make_bundle())
        assert "---" in md


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_starts_with_bom(self):
        csv = export_to_csv(_make_bundle())
        assert csv.startswith("\ufeff")

    def test_header_row(self):
        csv = export_to_csv(_make_bundle())
        header = csv.split("\n")[0].lstrip("\ufeff")
        assert header == "sceneId,index,title,narration,durationSeconds,image_prompt,video_prompt,locked"

    def test_row_count(self):
        csv = export_to_csv(_make_bundle())
        rows = [r for r in csv.strip().split("\n") if r.strip()]
        # header + 2 data rows
        assert len(rows) == 3

    def test_contains_scene_data(self):
        csv = export_to_csv(_make_bundle())
        assert "s1" in csv
        assert "s2" in csv


# ---------------------------------------------------------------------------
# Text export
# ---------------------------------------------------------------------------


class TestExportText:
    def test_scene_markers(self):
        text = export_to_text(_make_bundle())
        assert "[Scene 1]" in text
        assert "[Scene 2]" in text

    def test_contains_all_prompts(self):
        text = export_to_text(_make_bundle())
        assert "Image: A sunrise over misty mountains" in text
        assert "Video: Slow pan across mountain range at dawn" in text
        assert "Image: A traveler on a winding forest path" in text


# ---------------------------------------------------------------------------
# Qwen JSONL export
# ---------------------------------------------------------------------------


class TestExportQwenJsonl:
    def test_one_line_per_scene(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_valid_json_per_line(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "model" in obj
            assert "prompt" in obj
            assert "negative_prompt" in obj
            assert "size" in obj

    def test_default_model(self):
        jsonl = export_to_qwen_jsonl(_make_bundle())
        obj = json.loads(jsonl.strip().split("\n")[0])
        assert obj["model"] == "qwen-image-3.0"
        assert obj["size"] == "1280x720"


# ---------------------------------------------------------------------------
# Wan3 JSONL export
# ---------------------------------------------------------------------------


class TestExportWan3Jsonl:
    def test_one_line_per_scene(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_valid_json_per_line(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)
            assert "model" in obj
            assert "prompt" in obj
            assert "resolution" in obj
            assert "ratio" in obj
            assert "duration" in obj

    def test_defaults_for_missing(self):
        jsonl = export_to_wan3_jsonl(_make_bundle())
        # Second scene has no ratio, should default
        obj = json.loads(jsonl.strip().split("\n")[1])
        assert obj["ratio"] == "adaptive"
        assert obj["model"] == "wan3.0-video"


# ---------------------------------------------------------------------------
# Security scanner
# ---------------------------------------------------------------------------


class TestScanBundleSecurity:
    def test_clean_bundle_passes(self):
        issues = scan_bundle_security(_make_bundle())
        assert len(issues) == 0

    def test_detects_sk_secret_key(self):
        bundle = _make_bundle()
        bundle.scenes[0].image.prompt = "Use key sk-abcdefghijklmnopqrstuvwxyz123456"
        issues = scan_bundle_security(bundle)
        secret = [i for i in issues if i.code == "SECRET_KEY"]
        assert len(secret) >= 1
        assert secret[0].severity == "error"
        assert secret[0].scene_id == "s1"

    def test_detects_api_key_assignment(self):
        bundle = _make_bundle()
        bundle.scenes[0].narration = "Set api_key=supersecret123 in the config"
        issues = scan_bundle_security(bundle)
        secret = [i for i in issues if i.code == "SECRET_KEY"]
        assert len(secret) >= 1

    def test_detects_signed_url_amz(self):
        bundle = _make_bundle()
        bundle.scenes[0].image.prompt = "Load from https://cdn.example.com/img.jpg?X-Amz-Signature=abc123"
        issues = scan_bundle_security(bundle)
        url = [i for i in issues if i.code == "SIGNED_URL"]
        assert len(url) >= 1

    def test_detects_signed_url_aws(self):
        bundle = _make_bundle()
        bundle.scenes[1].video.prompt = "Fetch https://s3.amazonaws.com/bucket/file?Signature=xyz"
        issues = scan_bundle_security(bundle)
        url = [i for i in issues if i.code == "SIGNED_URL"]
        assert len(url) >= 1

    def test_detects_unix_absolute_path(self):
        bundle = _make_bundle()
        bundle.scenes[0].image.prompt = "Load texture from /home/user/assets/texture.png"
        issues = scan_bundle_security(bundle)
        path = [i for i in issues if i.code == "ABSOLUTE_PATH"]
        assert len(path) >= 1
        assert path[0].severity == "warning"

    def test_detects_windows_absolute_path(self):
        bundle = _make_bundle()
        bundle.scenes[0].narration = "Reference C:\\Users\\admin\\file.txt for details"
        issues = scan_bundle_security(bundle)
        path = [i for i in issues if i.code == "ABSOLUTE_PATH"]
        assert len(path) >= 1

    def test_detects_api_key_variable(self):
        bundle = _make_bundle()
        bundle.scenes[1].video.prompt = "Send to endpoint with ${API_KEY} header"
        issues = scan_bundle_security(bundle)
        key = [i for i in issues if i.code == "API_KEY"]
        assert len(key) >= 1

    def test_detects_process_env(self):
        bundle = _make_bundle()
        bundle.scenes[0].image.prompt = "Use process.env.SECRET_KEY for auth"
        issues = scan_bundle_security(bundle)
        key = [i for i in issues if i.code == "API_KEY"]
        assert len(key) >= 1

    def test_detects_global_field_issues(self):
        bundle = _make_bundle()
        bundle.global_style = "cinematic with key sk-abcdefghijklmnopqrstuvwxyz123456"
        issues = scan_bundle_security(bundle)
        secret = [i for i in issues if i.code == "SECRET_KEY"]
        assert len(secret) >= 1
        assert secret[0].scene_id is None

    def test_multiple_issues_detected(self):
        bundle = _make_bundle()
        bundle.scenes[0].image.prompt = (
            "key sk-abcdefghijklmnopqrstuvwxyz123456 path /tmp/file"
        )
        issues = scan_bundle_security(bundle)
        codes = [i.code for i in issues]
        assert "SECRET_KEY" in codes
        assert "ABSOLUTE_PATH" in codes


# ---------------------------------------------------------------------------
# Placeholder for export_to_jsonl (if needed in future)
# ---------------------------------------------------------------------------


class TestExportJsonlPlaceholder:
    def test_export_to_jsonl_exists(self):
        """Verify export_to_jsonl is importable."""
        assert callable(export_to_jsonl)
