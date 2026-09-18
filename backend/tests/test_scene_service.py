"""Tests for SceneService and Storyboard Materializer."""

import sys
from pathlib import Path

import pytest

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.db.connection import get_connection, MIGRATIONS_DIR
from backend.app.schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)
from backend.app.services.scene_service import SceneService
from backend.app.services.storyboard_materializer import (
    MaterializationError,
    compute_deterministic_scene_id,
    materialize_storyboard,
)


def _init_test_db():
    """Initialize the test database by running migrations."""
    conn = get_connection()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for mf in migration_files:
        sql = mf.read_text(encoding="utf-8")
        statements = []
        current = []
        for line in sql.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                if current:
                    current.append(line)
                continue
            current.append(line)
            if stripped.endswith(';'):
                statements.append('\n'.join(current))
                current = []
        if current:
            statements.append('\n'.join(current))
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()


@pytest.fixture(autouse=True)
def _setup_db():
    """Ensure database is initialized and cleaned before each test."""
    _init_test_db()
    yield
    try:
        conn = get_connection()
        conn.execute("DELETE FROM scene_drafts")
        conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_scene(scene_id: str = "s1", index: int = 0, locked: bool = False) -> SceneEntry:
    return SceneEntry(
        scene_id=scene_id,
        index=index,
        title=f"Scene {index + 1}",
        narration=f"Narration for {scene_id}",
        duration_seconds=5.0,
        locked=locked,
        image=SceneImagePrompt(prompt=f"Image prompt for {scene_id}"),
        video=SceneVideoPrompt(prompt=f"Video prompt for {scene_id}"),
    )


def _make_bundle(scenes: list[SceneEntry] | None = None, **overrides) -> ScenePromptBundle:
    if scenes is None:
        scenes = [_make_scene("s1", 0), _make_scene("s2", 1)]
    defaults = dict(
        storyboard_id="sb-001",
        workflow_id="wf-001",
        execution_id="ex-001",
        title="Test Bundle",
        scenes=scenes,
    )
    defaults.update(overrides)
    return ScenePromptBundle(**defaults)


# ---------------------------------------------------------------------------
# SceneService tests
# ---------------------------------------------------------------------------


class TestSceneServiceDraft:
    def test_create_draft_returns_id(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)
        assert draft_id.startswith("draft-")

    def test_create_draft_returns_unique_ids(self):
        svc = SceneService()
        id1 = svc.create_draft(_make_bundle())
        id2 = svc.create_draft(_make_bundle())
        assert id1.startswith("draft-")
        assert id2.startswith("draft-")
        assert id1 != id2

    def test_get_draft_returns_bundle(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)
        result = svc.get_draft(draft_id)
        assert result is not None
        assert result.title == "Test Bundle"
        assert len(result.scenes) == 2

    def test_get_draft_nonexistent_returns_none(self):
        svc = SceneService()
        assert svc.get_draft("nonexistent") is None


class TestSceneServiceUpdateScene:
    def test_update_scene_field(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        success = svc.update_scene(draft_id, 0, {"narration": "Updated narration"})
        assert success is True
        bundle = svc.get_draft(draft_id)
        assert bundle.scenes[0].narration == "Updated narration"

    def test_update_scene_invalid_index(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        assert svc.update_scene(draft_id, 99, {"narration": "x"}) is False

    def test_update_scene_negative_index(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        assert svc.update_scene(draft_id, -1, {"narration": "x"}) is False

    def test_update_scene_nonexistent_draft(self):
        svc = SceneService()
        assert svc.update_scene("no-such", 0, {"narration": "x"}) is False


class TestSceneServiceLockUnlock:
    def test_lock_scene(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        assert svc.lock_scene(draft_id, 0) is True
        bundle = svc.get_draft(draft_id)
        assert bundle.scenes[0].locked is True

    def test_unlock_scene(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        svc.lock_scene(draft_id, 0)
        assert svc.unlock_scene(draft_id, 0) is True
        bundle = svc.get_draft(draft_id)
        assert bundle.scenes[0].locked is False

    def test_lock_scene_invalid_index(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        assert svc.lock_scene(draft_id, 99) is False

    def test_unlock_scene_invalid_index(self):
        svc = SceneService()
        draft_id = svc.create_draft(_make_bundle())
        assert svc.unlock_scene(draft_id, 99) is False


class TestSceneServiceMergeExecution:
    def test_merge_replaces_unlocked_scenes(self):
        svc = SceneService()
        original = _make_bundle()
        draft_id = svc.create_draft(original)

        exec_bundle = _make_bundle(
            scenes=[
                _make_scene("s1", 0),
                _make_scene("s2", 1),
            ]
        )
        exec_bundle.scenes[0].narration = "Exec narration s1"
        exec_bundle.scenes[1].narration = "Exec narration s2"

        merged = svc.merge_execution(draft_id, exec_bundle)
        assert merged.scenes[0].narration == "Exec narration s1"
        assert merged.scenes[1].narration == "Exec narration s2"

    def test_merge_preserves_locked_scenes(self):
        svc = SceneService()
        original = _make_bundle()
        draft_id = svc.create_draft(original)
        svc.lock_scene(draft_id, 0)  # lock s1

        exec_bundle = _make_bundle(
            scenes=[
                _make_scene("s1", 0),
                _make_scene("s2", 1),
            ]
        )
        exec_bundle.scenes[0].narration = "Exec s1"
        exec_bundle.scenes[1].narration = "Exec s2"

        merged = svc.merge_execution(draft_id, exec_bundle)
        # s1 is locked, so draft version preserved
        assert merged.scenes[0].narration == "Narration for s1"
        # s2 is not locked, so execution version used
        assert merged.scenes[1].narration == "Exec s2"

    def test_merge_with_no_draft_returns_execution(self):
        svc = SceneService()
        exec_bundle = _make_bundle()
        merged = svc.merge_execution("nonexistent", exec_bundle)
        assert merged is exec_bundle


class TestSceneServiceImport:
    def test_import_bundle_creates_draft(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.import_bundle(bundle)
        assert draft_id.startswith("draft-")
        retrieved = svc.get_draft(draft_id)
        assert retrieved is not None
        assert retrieved.title == bundle.title
        assert len(retrieved.scenes) == len(bundle.scenes)


class TestSceneServiceListDrafts:
    def test_list_drafts_returns_summaries(self):
        svc = SceneService()
        svc.create_draft(_make_bundle(title="Story A"))
        svc.create_draft(_make_bundle(title="Story B"))
        summaries = svc.list_drafts(workflow_id="wf-001")
        assert len(summaries) == 2
        titles = {s["name"] for s in summaries}
        assert "Story A" in titles
        assert "Story B" in titles
        for s in summaries:
            assert "id" in s
            assert "scene_count" in s

    def test_list_drafts_empty(self):
        svc = SceneService()
        assert svc.list_drafts(workflow_id="wf-nonexistent") == []


# ---------------------------------------------------------------------------
# Storyboard Materializer tests
# ---------------------------------------------------------------------------


def _make_exec_result(scenes: list[dict]) -> dict:
    """Helper: wrap scene dicts into the standard NodeResult format."""
    return {"output": {"metadata": {"scenes": scenes}}}


class TestMaterializeStoryboard:
    def test_materialize_standard_format(self):
        result = _make_exec_result([
            {
                "scene_id": "scene-001",
                "index": 0,
                "narration": "Opening scene",
                "image_prompt": "Sunrise",
                "video_prompt": "Pan across mountains",
                "duration_seconds": 5.0,
            },
            {
                "scene_id": "scene-002",
                "index": 1,
                "narration": "Journey",
                "image_prompt": "Forest path",
                "video_prompt": "Tracking shot",
                "duration_seconds": 8.0,
            },
        ])
        bundle = materialize_storyboard(result, workflow_id="wf-1", storyboard_id="sb-1")
        assert len(bundle.scenes) == 2
        assert bundle.scenes[0].scene_id == "scene-001"
        assert bundle.scenes[1].scene_id == "scene-002"
        assert bundle.scenes[0].narration == "Opening scene"
        assert bundle.scenes[0].locked is False

    def test_materialize_legacy_output_scenes(self):
        result = {
            "output": {
                "scenes": [
                    {
                        "scene_id": "s-1",
                        "index": 0,
                        "narration": "Legacy scene",
                        "image_prompt": "Img",
                        "video_prompt": "Vid",
                    }
                ]
            }
        }
        bundle = materialize_storyboard(result)
        assert len(bundle.scenes) == 1
        assert bundle.scenes[0].scene_id == "s-1"

    def test_materialize_flat_scenes(self):
        result = {
            "scenes": [
                {
                    "scene_id": "flat-1",
                    "index": 0,
                    "narration": "Flat scene",
                    "image_prompt": "Flat img",
                    "video_prompt": "Flat vid",
                }
            ]
        }
        bundle = materialize_storyboard(result)
        assert len(bundle.scenes) == 1
        assert bundle.scenes[0].scene_id == "flat-1"

    def test_materialize_no_scenes_raises(self):
        with pytest.raises(MaterializationError):
            materialize_storyboard({}, allow_empty=False)

    def test_materialize_empty_scenes_raises(self):
        with pytest.raises(MaterializationError):
            materialize_storyboard(
                {"output": {"metadata": {"scenes": []}}},
                allow_empty=False,
            )

    def test_materialize_applies_global_style(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "A mountain",
                "video_prompt": "Pan",
            }
        ])
        bundle = materialize_storyboard(result, global_style="cinematic, warm")
        assert "cinematic, warm" in bundle.scenes[0].image.prompt
        assert "A mountain" in bundle.scenes[0].image.prompt

    def test_materialize_applies_negative_prompt(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "A mountain",
                "video_prompt": "Pan",
            }
        ])
        bundle = materialize_storyboard(result, negative_prompt="blurry")
        assert bundle.scenes[0].image.negative_prompt == "blurry"

    def test_materialize_default_title(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert "Storyboard" in bundle.title

    def test_materialize_custom_title(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result, title="My Custom Title")
        assert bundle.title == "My Custom Title"

    def test_materialize_sorts_by_index(self):
        result = _make_exec_result([
            {
                "scene_id": "s2",
                "index": 2,
                "narration": "Third",
                "image_prompt": "Img2",
                "video_prompt": "Vid2",
            },
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "First",
                "image_prompt": "Img1",
                "video_prompt": "Vid1",
            },
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].scene_id == "s1"
        assert bundle.scenes[1].scene_id == "s2"

    def test_materialize_default_scene_id(self):
        result = _make_exec_result([
            {
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].scene_id.startswith("scene-")

    def test_materialize_source_is_execution(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.source == "execution"


# ---------------------------------------------------------------------------
# SCENE-002: Single scene materialization
# ---------------------------------------------------------------------------


class TestMaterializeSingleScene:
    """Materialize 1 scene -> bundle with 1 scene entry."""

    def test_single_scene_bundle_has_one_entry(self):
        result = _make_exec_result([
            {
                "scene_id": "only-scene",
                "index": 0,
                "narration": "A lonely opening",
                "image_prompt": "Single mountain peak",
                "video_prompt": "Static shot of peak",
                "duration_seconds": 6.0,
            }
        ])
        bundle = materialize_storyboard(result, workflow_id="wf-single", storyboard_id="sb-single")
        assert len(bundle.scenes) == 1
        assert bundle.scenes[0].scene_id == "only-scene"
        assert bundle.scenes[0].index == 0
        assert bundle.scenes[0].narration == "A lonely opening"
        assert bundle.scenes[0].duration_seconds == 6.0

    def test_single_scene_preserves_image_prompt(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Narr",
                "image_prompt": "Detailed image prompt here",
                "video_prompt": "Vid prompt",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].image.prompt == "Detailed image prompt here"

    def test_single_scene_preserves_video_prompt(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Narr",
                "image_prompt": "Img",
                "video_prompt": "Detailed video prompt here",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].video.prompt == "Detailed video prompt here"


# ---------------------------------------------------------------------------
# SCENE-002: Three scenes -> correct ordering
# ---------------------------------------------------------------------------


class TestMaterializeThreeScenes:
    """Materialize 3 scenes -> correct ordering by index."""

    def test_three_scenes_correct_order(self):
        """Scenes provided out of order should be sorted by index."""
        result = _make_exec_result([
            {
                "scene_id": "s3",
                "index": 2,
                "narration": "Third scene",
                "image_prompt": "Img 3",
                "video_prompt": "Vid 3",
            },
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "First scene",
                "image_prompt": "Img 1",
                "video_prompt": "Vid 1",
            },
            {
                "scene_id": "s2",
                "index": 1,
                "narration": "Second scene",
                "image_prompt": "Img 2",
                "video_prompt": "Vid 2",
            },
        ])
        bundle = materialize_storyboard(result)
        assert len(bundle.scenes) == 3
        assert [s.scene_id for s in bundle.scenes] == ["s1", "s2", "s3"]
        assert [s.index for s in bundle.scenes] == [0, 1, 2]
        assert [s.narration for s in bundle.scenes] == [
            "First scene",
            "Second scene",
            "Third scene",
        ]

    def test_three_scenes_already_ordered(self):
        """Scenes already in order should remain in order."""
        result = _make_exec_result([
            {"scene_id": "a", "index": 0, "narration": "A", "image_prompt": "i1", "video_prompt": "v1"},
            {"scene_id": "b", "index": 1, "narration": "B", "image_prompt": "i2", "video_prompt": "v2"},
            {"scene_id": "c", "index": 2, "narration": "C", "image_prompt": "i3", "video_prompt": "v3"},
        ])
        bundle = materialize_storyboard(result)
        assert [s.scene_id for s in bundle.scenes] == ["a", "b", "c"]

    def test_three_scenes_reverse_order(self):
        """Scenes in reverse order should be corrected."""
        result = _make_exec_result([
            {"scene_id": "c", "index": 2, "narration": "C", "image_prompt": "i3", "video_prompt": "v3"},
            {"scene_id": "b", "index": 1, "narration": "B", "image_prompt": "i2", "video_prompt": "v2"},
            {"scene_id": "a", "index": 0, "narration": "A", "image_prompt": "i1", "video_prompt": "v1"},
        ])
        bundle = materialize_storyboard(result)
        assert [s.scene_id for s in bundle.scenes] == ["a", "b", "c"]
        assert [s.index for s in bundle.scenes] == [0, 1, 2]


# ---------------------------------------------------------------------------
# SCENE-002: scene_id stability across materializations
# ---------------------------------------------------------------------------


class TestSceneIdStability:
    """scene_id must be stable: same input -> same scene_id across calls."""

    def test_stability_with_explicit_scene_id(self):
        """Scenes with explicit scene_id keep the same ID on re-materialization."""
        result = _make_exec_result([
            {
                "scene_id": "my-stable-id",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            },
        ])
        bundle1 = materialize_storyboard(result)
        bundle2 = materialize_storyboard(result)
        assert bundle1.scenes[0].scene_id == bundle2.scenes[0].scene_id == "my-stable-id"

    def test_stability_across_five_calls(self):
        """Same input produces same scene_id across 5 independent calls."""
        result = _make_exec_result([
            {"scene_id": "stable-x", "index": 0, "narration": "N1", "image_prompt": "I1", "video_prompt": "V1"},
            {"scene_id": "stable-y", "index": 1, "narration": "N2", "image_prompt": "I2", "video_prompt": "V2"},
        ])
        ids_history = []
        for _ in range(5):
            bundle = materialize_storyboard(result)
            ids_history.append(tuple(s.scene_id for s in bundle.scenes))
        # All 5 calls should produce the exact same scene_id sequence
        assert len(set(ids_history)) == 1

    def test_deterministic_id_without_explicit_scene_id(self):
        """Scenes without scene_id get deterministic IDs that are stable."""
        scene_data = {
            "index": 0,
            "narration": "Deterministic narration",
            "image_prompt": "Deterministic image",
            "video_prompt": "Deterministic video",
        }
        result = _make_exec_result([scene_data])
        bundle1 = materialize_storyboard(result)
        bundle2 = materialize_storyboard(result)
        assert bundle1.scenes[0].scene_id == bundle2.scenes[0].scene_id
        assert bundle1.scenes[0].scene_id.startswith("scene-")

    def test_deterministic_id_differs_for_different_content(self):
        """Different scene content produces different deterministic IDs."""
        scene_a = {"index": 0, "narration": "Alpha", "image_prompt": "Img A", "video_prompt": "Vid A"}
        scene_b = {"index": 0, "narration": "Beta", "image_prompt": "Img B", "video_prompt": "Vid B"}
        bundle_a = materialize_storyboard(_make_exec_result([scene_a]))
        bundle_b = materialize_storyboard(_make_exec_result([scene_b]))
        assert bundle_a.scenes[0].scene_id != bundle_b.scenes[0].scene_id

    def test_deterministic_id_differs_for_different_position(self):
        """Same content at different list position produces different deterministic IDs."""
        scene_data = {"narration": "Same", "image_prompt": "Same", "video_prompt": "Same"}
        # Test compute_deterministic_scene_id directly with different positions
        id_pos0 = compute_deterministic_scene_id(scene_data, 0)
        id_pos5 = compute_deterministic_scene_id(scene_data, 5)
        assert id_pos0 != id_pos5


# ---------------------------------------------------------------------------
# SCENE-002: Empty scenes -> valid empty bundle
# ---------------------------------------------------------------------------


class TestMaterializeEmptyScenes:
    """Empty scenes list produces a valid empty bundle (allow_empty=True by default)."""

    def test_empty_result_returns_empty_bundle(self):
        bundle = materialize_storyboard({})
        assert bundle.scenes == []
        assert bundle.source == "execution"
        assert bundle.schema_version == "1.0"

    def test_empty_scenes_list_returns_empty_bundle(self):
        bundle = materialize_storyboard({"output": {"metadata": {"scenes": []}}})
        assert bundle.scenes == []
        assert len(bundle.scenes) == 0

    def test_empty_bundle_has_default_ids(self):
        bundle = materialize_storyboard({})
        assert bundle.storyboard_id == "sb-generated"
        assert bundle.workflow_id == "wf-unknown"
        assert bundle.execution_id == "ex-unknown"

    def test_empty_bundle_preserves_provided_ids(self):
        bundle = materialize_storyboard(
            {},
            workflow_id="wf-x",
            execution_id="ex-x",
            storyboard_id="sb-x",
        )
        assert bundle.workflow_id == "wf-x"
        assert bundle.execution_id == "ex-x"
        assert bundle.storyboard_id == "sb-x"

    def test_empty_bundle_preserves_title(self):
        bundle = materialize_storyboard({}, title="Empty Board")
        assert bundle.title == "Empty Board"

    def test_empty_bundle_preserves_style_and_negative(self):
        bundle = materialize_storyboard(
            {},
            global_style="cinematic",
            negative_prompt="blurry",
        )
        assert bundle.global_style == "cinematic"
        assert bundle.negative_prompt == "blurry"

    def test_empty_bundle_json_roundtrip(self):
        """Empty bundle should survive JSON serialization roundtrip."""
        import json
        bundle = materialize_storyboard({})
        json_str = bundle.model_dump_json(by_alias=True)
        restored = ScenePromptBundle.model_validate_json(json_str)
        assert restored.scenes == []
        assert restored.source == "execution"


# ---------------------------------------------------------------------------
# SCENE-002: Metadata, narration, duration preservation
# ---------------------------------------------------------------------------


class TestPreserveMetadataNarrationDuration:
    """Verify metadata, narration, and duration are correctly preserved."""

    def test_narration_preserved(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Once upon a time, in a land far away...",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].narration == "Once upon a time, in a land far away..."

    def test_duration_preserved(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
                "duration_seconds": 7.5,
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].duration_seconds == 7.5

    def test_duration_default_when_missing(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].duration_seconds == 5.0

    def test_metadata_preserved(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
                "metadata": {
                    "variantCount": 2,
                    "outputStrategy": "two_variants_to_video",
                    "customField": "hello",
                },
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].metadata["variantCount"] == 2
        assert bundle.scenes[0].metadata["outputStrategy"] == "two_variants_to_video"
        assert bundle.scenes[0].metadata["customField"] == "hello"

    def test_metadata_default_empty(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].metadata == {}

    def test_metadata_nested_preserved(self):
        result = _make_exec_result([
            {
                "scene_id": "s1",
                "index": 0,
                "narration": "Test",
                "image_prompt": "Img",
                "video_prompt": "Vid",
                "metadata": {"level1": {"level2": {"value": 42}}},
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].metadata["level1"]["level2"]["value"] == 42

    def test_multiple_scenes_all_metadata_preserved(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N1",
                "image_prompt": "I1", "video_prompt": "V1",
                "metadata": {"key": "val1"},
            },
            {
                "scene_id": "s2", "index": 1, "narration": "N2",
                "image_prompt": "I2", "video_prompt": "V2",
                "metadata": {"key": "val2"},
            },
            {
                "scene_id": "s3", "index": 2, "narration": "N3",
                "image_prompt": "I3", "video_prompt": "V3",
                "metadata": {"key": "val3"},
            },
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].metadata["key"] == "val1"
        assert bundle.scenes[1].metadata["key"] == "val2"
        assert bundle.scenes[2].metadata["key"] == "val3"


# ---------------------------------------------------------------------------
# SCENE-002: Image/video prompts correctly mapped
# ---------------------------------------------------------------------------


class TestImageVideoPromptsMapped:
    """Verify image and video prompts are correctly mapped to bundle entries."""

    def test_image_prompt_mapped(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "A majestic sunrise over snow-capped mountains",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].image.prompt == "A majestic sunrise over snow-capped mountains"

    def test_video_prompt_mapped(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img",
                "video_prompt": "Slow dolly zoom into the valley",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].video.prompt == "Slow dolly zoom into the valley"

    def test_image_negative_prompt_from_scene(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img", "video_prompt": "Vid",
                "image_negative_prompt": "blurry, distorted",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].image.negative_prompt == "blurry, distorted"

    def test_global_style_prepended_to_image_prompt(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "A mountain landscape",
                "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result, global_style="cinematic, warm tones")
        assert bundle.scenes[0].image.prompt == "A mountain landscape, cinematic, warm tones"

    def test_global_negative_prompt_applied_when_scene_has_none(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img", "video_prompt": "Vid",
            }
        ])
        bundle = materialize_storyboard(result, negative_prompt="low quality, artifacts")
        assert bundle.scenes[0].image.negative_prompt == "low quality, artifacts"

    def test_scene_negative_prompt_takes_precedence(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img", "video_prompt": "Vid",
                "image_negative_prompt": "scene-specific negative",
            }
        ])
        bundle = materialize_storyboard(result, negative_prompt="global negative")
        assert bundle.scenes[0].image.negative_prompt == "scene-specific negative"

    def test_image_provider_and_model_mapped(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img", "video_prompt": "Vid",
                "image_provider": "dashscope",
                "image_model": "qwen-image-3.0",
                "image_size": "1280x720",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].image.provider == "dashscope"
        assert bundle.scenes[0].image.model == "qwen-image-3.0"
        assert bundle.scenes[0].image.size == "1280x720"

    def test_video_provider_model_resolution_ratio_mapped(self):
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N",
                "image_prompt": "Img", "video_prompt": "Vid",
                "video_provider": "wan3",
                "video_model": "wan3.0-video",
                "video_resolution": "480P",
                "video_ratio": "16:9",
            }
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].video.provider == "wan3"
        assert bundle.scenes[0].video.model == "wan3.0-video"
        assert bundle.scenes[0].video.resolution == "480P"
        assert bundle.scenes[0].video.ratio == "16:9"

    def test_image_video_prompts_for_multiple_scenes(self):
        """Each scene's prompts are mapped to the correct scene entry."""
        result = _make_exec_result([
            {
                "scene_id": "s1", "index": 0, "narration": "N1",
                "image_prompt": "Image for scene 1",
                "video_prompt": "Video for scene 1",
            },
            {
                "scene_id": "s2", "index": 1, "narration": "N2",
                "image_prompt": "Image for scene 2",
                "video_prompt": "Video for scene 2",
            },
        ])
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].image.prompt == "Image for scene 1"
        assert bundle.scenes[0].video.prompt == "Video for scene 1"
        assert bundle.scenes[1].image.prompt == "Image for scene 2"
        assert bundle.scenes[1].video.prompt == "Video for scene 2"


# ---------------------------------------------------------------------------
# SCENE-002: compute_deterministic_scene_id unit tests
# ---------------------------------------------------------------------------


class TestComputeDeterministicSceneId:
    def test_returns_explicit_id_if_present(self):
        data = {"scene_id": "explicit-id", "narration": "N"}
        assert compute_deterministic_scene_id(data, 0) == "explicit-id"

    def test_generates_hash_based_id(self):
        data = {"narration": "Test narration", "image_prompt": "Test image", "video_prompt": "Test video"}
        sid = compute_deterministic_scene_id(data, 0)
        assert sid.startswith("scene-")
        assert len(sid) == len("scene-") + 8  # sha256 hex[:8]

    def test_same_input_same_id(self):
        data = {"narration": "N", "image_prompt": "I", "video_prompt": "V"}
        id1 = compute_deterministic_scene_id(data, 0)
        id2 = compute_deterministic_scene_id(data, 0)
        assert id1 == id2

    def test_different_narration_different_id(self):
        data_a = {"narration": "Alpha", "image_prompt": "I", "video_prompt": "V"}
        data_b = {"narration": "Beta", "image_prompt": "I", "video_prompt": "V"}
        assert compute_deterministic_scene_id(data_a, 0) != compute_deterministic_scene_id(data_b, 0)

    def test_different_position_different_id(self):
        data = {"narration": "N", "image_prompt": "I", "video_prompt": "V"}
        assert compute_deterministic_scene_id(data, 0) != compute_deterministic_scene_id(data, 1)
