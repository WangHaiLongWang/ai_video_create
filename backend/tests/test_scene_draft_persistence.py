"""Tests for Scene Draft persistence (SQLite migration + repository + service).

Covers:
- Create and retrieve draft
- Lock scene prevents overwrite
- Merge only updates unlocked scenes
- Version increments correctly
- Optimistic locking
- CRUD: list, update, delete
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.db.connection import get_connection, close_connection, _get_db_path, MIGRATIONS_DIR
from backend.app.repositories import scene_drafts as repo
from backend.app.schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)
from backend.app.services.scene_service import SceneService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
                pass  # Already exists
    conn.commit()


@pytest.fixture(autouse=True)
def _setup_db():
    """Ensure database is initialized before each test."""
    _init_test_db()
    yield
    # Clean up scene_drafts table after each test
    try:
        conn = get_connection()
        conn.execute("DELETE FROM scene_drafts")
        conn.commit()
    except Exception:
        pass


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


def _make_bundle(scenes=None, **overrides) -> ScenePromptBundle:
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
# Repository tests
# ---------------------------------------------------------------------------


class TestRepositoryCreateAndGet:
    def test_create_draft_returns_record(self):
        bundle = _make_bundle()
        record = repo.create_draft(
            draft_id="draft-test-001",
            workflow_id="wf-001",
            name="Test Draft",
            source="draft",
            bundle_dict=bundle.model_dump(by_alias=True),
        )
        assert record["id"] == "draft-test-001"
        assert record["workflow_id"] == "wf-001"
        assert record["name"] == "Test Draft"
        assert record["source"] == "draft"
        assert record["version"] == 1
        assert record["locked_scene_ids"] == []

    def test_get_draft_returns_full_record(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="draft-test-002",
            workflow_id="wf-001",
            name="Full Draft",
            source="draft",
            bundle_dict=bundle.model_dump(by_alias=True),
        )
        record = repo.get_draft("draft-test-002")
        assert record["id"] == "draft-test-002"
        assert "bundle" in record
        assert isinstance(record["bundle"], dict)
        assert record["bundle"]["title"] == "Test Bundle"

    def test_get_nonexistent_raises(self):
        with pytest.raises(repo.SceneDraftNotFoundError):
            repo.get_draft("no-such-draft")


class TestRepositoryListDrafts:
    def test_list_drafts_for_workflow(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d1", workflow_id="wf-001", name="Draft 1",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        repo.create_draft(
            draft_id="d2", workflow_id="wf-001", name="Draft 2",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        repo.create_draft(
            draft_id="d3", workflow_id="wf-002", name="Other WF Draft",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )

        results = repo.list_drafts("wf-001")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert "Draft 1" in names
        assert "Draft 2" in names

    def test_list_drafts_empty(self):
        results = repo.list_drafts("wf-nonexistent")
        assert results == []


class TestRepositoryUpdateDraft:
    def test_update_name(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-update", workflow_id="wf-001", name="Old Name",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        updated = repo.update_draft(draft_id="d-update", name="New Name")
        assert updated["name"] == "New Name"
        assert updated["version"] == 2

    def test_update_source(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-src", workflow_id="wf-001", name="Draft",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        updated = repo.update_draft(draft_id="d-src", source="merged")
        assert updated["source"] == "merged"
        assert updated["version"] == 2

    def test_version_increments_on_update(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-ver", workflow_id="wf-001", name="V1",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        record = repo.get_draft("d-ver")
        assert record["version"] == 1

        repo.update_draft(draft_id="d-ver", name="V2")
        record = repo.get_draft("d-ver")
        assert record["version"] == 2

        repo.update_draft(draft_id="d-ver", name="V3")
        record = repo.get_draft("d-ver")
        assert record["version"] == 3

    def test_optimistic_lock_conflict(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-lock", workflow_id="wf-001", name="Original",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        # First update succeeds
        repo.update_draft(draft_id="d-lock", name="Updated", expected_version=1)
        # Second update with stale version fails
        with pytest.raises(repo.OptimisticLockError):
            repo.update_draft(draft_id="d-lock", name="Stale", expected_version=1)


class TestRepositoryDeleteDraft:
    def test_delete_draft(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-del", workflow_id="wf-001", name="Delete Me",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
        )
        repo.delete_draft("d-del")
        with pytest.raises(repo.SceneDraftNotFoundError):
            repo.get_draft("d-del")

    def test_delete_nonexistent_raises(self):
        with pytest.raises(repo.SceneDraftNotFoundError):
            repo.delete_draft("no-such-draft")


class TestRepositoryLockUnlock:
    def test_lock_scene_adds_to_list(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-lock", workflow_id="wf-001", name="Lock Test",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
            locked_scene_ids=[],
        )
        updated = repo.lock_scene("d-lock", "s1")
        assert "s1" in updated["locked_scene_ids"]
        assert updated["version"] == 2

    def test_lock_scene_idempotent(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-lock2", workflow_id="wf-001", name="Idem",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
            locked_scene_ids=[],
        )
        repo.lock_scene("d-lock2", "s1")
        updated = repo.lock_scene("d-lock2", "s1")
        assert updated["locked_scene_ids"].count("s1") == 1

    def test_unlock_scene_removes_from_list(self):
        bundle = _make_bundle()
        repo.create_draft(
            draft_id="d-ul", workflow_id="wf-001", name="Unlock",
            source="draft", bundle_dict=bundle.model_dump(by_alias=True),
            locked_scene_ids=["s1", "s2"],
        )
        updated = repo.unlock_scene("d-ul", "s1")
        assert "s1" not in updated["locked_scene_ids"]
        assert "s2" in updated["locked_scene_ids"]


# ---------------------------------------------------------------------------
# Service tests (with persistence)
# ---------------------------------------------------------------------------


class TestServiceDraftCRUD:
    def test_create_and_get_draft(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)
        assert draft_id.startswith("draft-")

        retrieved = svc.get_draft(draft_id)
        assert retrieved is not None
        assert retrieved.title == "Test Bundle"
        assert len(retrieved.scenes) == 2

    def test_get_nonexistent_returns_none(self):
        svc = SceneService()
        assert svc.get_draft("nonexistent") is None

    def test_list_drafts(self):
        svc = SceneService()
        svc.create_draft(_make_bundle(title="Story A"))
        svc.create_draft(_make_bundle(title="Story B"))

        summaries = svc.list_drafts(workflow_id="wf-001")
        assert len(summaries) == 2
        titles = {s["name"] for s in summaries}
        assert "Story A" in titles
        assert "Story B" in titles

    def test_delete_draft(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)
        assert svc.delete_draft(draft_id) is True
        assert svc.get_draft(draft_id) is None

    def test_delete_nonexistent_returns_false(self):
        svc = SceneService()
        assert svc.delete_draft("no-such") is False


class TestServiceLockScene:
    def test_lock_scene_persists(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)

        success = svc.lock_scene(draft_id, 0)
        assert success is True

        # Verify persistence
        retrieved = svc.get_draft(draft_id)
        assert retrieved.scenes[0].locked is True
        assert retrieved.scenes[1].locked is False

    def test_unlock_scene_persists(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)

        svc.lock_scene(draft_id, 0)
        success = svc.unlock_scene(draft_id, 0)
        assert success is True

        retrieved = svc.get_draft(draft_id)
        assert retrieved.scenes[0].locked is False

    def test_lock_invalid_index_returns_false(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)
        assert svc.lock_scene(draft_id, 99) is False
        assert svc.lock_scene(draft_id, -1) is False

    def test_lock_nonexistent_draft_returns_false(self):
        svc = SceneService()
        assert svc.lock_scene("no-such", 0) is False


class TestServiceMergeExecution:
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

        # Lock scene s1 (index 0)
        svc.lock_scene(draft_id, 0)

        # Also verify the locked flag in the draft data
        draft = svc.get_draft(draft_id)
        assert draft.scenes[0].locked is True

        exec_bundle = _make_bundle(
            scenes=[
                _make_scene("s1", 0),
                _make_scene("s2", 1),
            ]
        )
        exec_bundle.scenes[0].narration = "Exec s1"
        exec_bundle.scenes[1].narration = "Exec s2"

        merged = svc.merge_execution(draft_id, exec_bundle)
        # s1 is locked, draft version preserved
        assert merged.scenes[0].narration == "Narration for s1"
        # s2 is unlocked, execution version used
        assert merged.scenes[1].narration == "Exec s2"

    def test_merge_nonexistent_draft_returns_execution(self):
        svc = SceneService()
        exec_bundle = _make_bundle()
        merged = svc.merge_execution("nonexistent", exec_bundle)
        assert merged is exec_bundle

    def test_merge_persists_source_as_merged(self):
        svc = SceneService()
        original = _make_bundle()
        draft_id = svc.create_draft(original)

        exec_bundle = _make_bundle()
        svc.merge_execution(draft_id, exec_bundle)

        # Verify the draft source changed to "merged"
        from backend.app.repositories import scene_drafts as repo
        record = repo.get_draft(draft_id)
        assert record["source"] == "merged"


class TestServiceVersionIncrement:
    def test_version_increments_on_lock(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)

        from backend.app.repositories import scene_drafts as repo
        record = repo.get_draft(draft_id)
        assert record["version"] == 1

        svc.lock_scene(draft_id, 0)
        record = repo.get_draft(draft_id)
        assert record["version"] == 2

    def test_version_increments_on_merge(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)

        from backend.app.repositories import scene_drafts as repo
        svc.merge_execution(draft_id, _make_bundle())
        record = repo.get_draft(draft_id)
        assert record["version"] == 2

    def test_version_increments_on_update_scene(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.create_draft(bundle)

        from backend.app.repositories import scene_drafts as repo
        svc.update_scene(draft_id, 0, {"narration": "Updated"})
        record = repo.get_draft(draft_id)
        assert record["version"] == 2


class TestServiceImportBundle:
    def test_import_creates_draft(self):
        svc = SceneService()
        bundle = _make_bundle()
        draft_id = svc.import_bundle(bundle)
        assert draft_id.startswith("draft-")
        retrieved = svc.get_draft(draft_id)
        assert retrieved is not None
        assert retrieved.title == "Test Bundle"
