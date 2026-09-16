"""Tests for SceneService and Storyboard Materializer."""

import sys
from pathlib import Path

import pytest

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)
from backend.app.services.scene_service import SceneService
from backend.app.services.storyboard_materializer import (
    MaterializationError,
    materialize_storyboard,
)


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
        assert draft_id == "draft-0001"

    def test_create_draft_increments_counter(self):
        svc = SceneService()
        id1 = svc.create_draft(_make_bundle())
        id2 = svc.create_draft(_make_bundle())
        assert id1 == "draft-0001"
        assert id2 == "draft-0002"

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
        svc.lock_scene(svc.create_draft(original), 0)  # lock s1

        draft_id = None
        for did in svc._drafts:
            draft_id = did
            break

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
        assert svc.get_draft(draft_id) is bundle


class TestSceneServiceListDrafts:
    def test_list_drafts_returns_summaries(self):
        svc = SceneService()
        svc.create_draft(_make_bundle(title="Story A"))
        svc.create_draft(_make_bundle(title="Story B"))
        summaries = svc.list_drafts()
        assert len(summaries) == 2
        titles = {s["title"] for s in summaries}
        assert "Story A" in titles
        assert "Story B" in titles
        for s in summaries:
            assert "id" in s
            assert "scene_count" in s
            assert "schema_version" in s

    def test_list_drafts_empty(self):
        svc = SceneService()
        assert svc.list_drafts() == []


# ---------------------------------------------------------------------------
# Storyboard Materializer tests
# ---------------------------------------------------------------------------


class TestMaterializeStoryboard:
    def test_materialize_standard_format(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
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
                    ]
                }
            }
        }
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
            materialize_storyboard({})

    def test_materialize_empty_scenes_raises(self):
        with pytest.raises(MaterializationError):
            materialize_storyboard({"output": {"metadata": {"scenes": []}}})

    def test_materialize_applies_global_style(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "A mountain",
                            "video_prompt": "Pan",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result, global_style="cinematic, warm")
        assert "cinematic, warm" in bundle.scenes[0].image.prompt
        assert "A mountain" in bundle.scenes[0].image.prompt

    def test_materialize_applies_negative_prompt(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "A mountain",
                            "video_prompt": "Pan",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result, negative_prompt="blurry")
        assert bundle.scenes[0].image.negative_prompt == "blurry"

    def test_materialize_default_title(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "Img",
                            "video_prompt": "Vid",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result)
        assert "Storyboard" in bundle.title

    def test_materialize_custom_title(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "Img",
                            "video_prompt": "Vid",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result, title="My Custom Title")
        assert bundle.title == "My Custom Title"

    def test_materialize_sorts_by_index(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
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
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].scene_id == "s1"
        assert bundle.scenes[1].scene_id == "s2"

    def test_materialize_default_scene_id(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "Img",
                            "video_prompt": "Vid",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result)
        assert bundle.scenes[0].scene_id == "scene-001"

    def test_materialize_source_is_execution(self):
        result = {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "index": 0,
                            "narration": "Test",
                            "image_prompt": "Img",
                            "video_prompt": "Vid",
                        }
                    ]
                }
            }
        }
        bundle = materialize_storyboard(result)
        assert bundle.source == "execution"
