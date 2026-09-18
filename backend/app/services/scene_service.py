"""Scene Service — manages Scene Draft, Override, and Lock with SQLite persistence.

Responsibilities:
1. Create/read/update/delete Scene Drafts (persisted in SQLite)
2. Apply user overrides
3. Lock/unlock scenes (prevents execution results from overwriting)
4. Merge execution results respecting lock state
"""

from __future__ import annotations

import json
from typing import Any

from ..repositories import scene_drafts as repo
from ..schemas.scene_bundle import ScenePromptBundle, SceneEntry


class SceneService:
    """CRUD and merge logic for Scene Bundles, backed by SQLite."""

    def create_draft(self, bundle: ScenePromptBundle, workflow_id: str | None = None) -> str:
        """Create a draft from a bundle, return draft_id.

        If workflow_id is provided, it overrides the bundle's workflow_id.
        """
        import uuid
        draft_id = f"draft-{uuid.uuid4().hex[:12]}"
        source = bundle.source or "draft"
        wf_id = workflow_id or bundle.workflow_id
        repo.create_draft(
            draft_id=draft_id,
            workflow_id=wf_id,
            name=bundle.title,
            source=source,
            bundle_dict=bundle.model_dump(),
            locked_scene_ids=[],
        )
        return draft_id

    def get_draft(self, draft_id: str) -> ScenePromptBundle | None:
        """Get a draft as a ScenePromptBundle. Returns None if not found."""
        try:
            record = repo.get_draft(draft_id)
        except repo.SceneDraftNotFoundError:
            return None
        return ScenePromptBundle(**record["bundle"])

    def update_scene(self, draft_id: str, scene_index: int, updates: dict[str, Any]) -> bool:
        """Update a specific scene's fields by index."""
        draft = self._get_record(draft_id)
        if draft is None:
            return False

        bundle_dict = draft["bundle"]
        scenes = bundle_dict.get("scenes", [])
        if scene_index < 0 or scene_index >= len(scenes):
            return False

        scene = scenes[scene_index]
        for key, value in updates.items():
            scene[key] = value

        repo.update_draft(
            draft_id=draft_id,
            bundle_dict=bundle_dict,
            expected_version=draft["version"],
        )
        return True

    def lock_scene(self, draft_id: str, scene_index: int) -> bool:
        """Lock a scene by index to prevent regeneration overwrites."""
        draft = self._get_record(draft_id)
        if draft is None:
            return False

        bundle_dict = draft["bundle"]
        scenes = bundle_dict.get("scenes", [])
        if scene_index < 0 or scene_index >= len(scenes):
            return False

        scene_id = scenes[scene_index].get("scene_id", "")
        if not scene_id:
            return False

        # Update locked flag in bundle data
        scenes[scene_index]["locked"] = True
        locked_ids = draft["locked_scene_ids"]
        if scene_id not in locked_ids:
            locked_ids.append(scene_id)

        repo.update_draft(
            draft_id=draft_id,
            bundle_dict=bundle_dict,
            locked_scene_ids=locked_ids,
            expected_version=draft["version"],
        )
        return True

    def unlock_scene(self, draft_id: str, scene_index: int) -> bool:
        """Unlock a scene to allow regeneration."""
        draft = self._get_record(draft_id)
        if draft is None:
            return False

        bundle_dict = draft["bundle"]
        scenes = bundle_dict.get("scenes", [])
        if scene_index < 0 or scene_index >= len(scenes):
            return False

        scene_id = scenes[scene_index].get("scene_id", "")
        if not scene_id:
            return False

        scenes[scene_index]["locked"] = False
        locked_ids = [sid for sid in draft["locked_scene_ids"] if sid != scene_id]

        repo.update_draft(
            draft_id=draft_id,
            bundle_dict=bundle_dict,
            locked_scene_ids=locked_ids,
            expected_version=draft["version"],
        )
        return True

    def merge_execution(self, draft_id: str, execution_bundle: ScenePromptBundle) -> ScenePromptBundle:
        """Merge execution results with the draft. Preserves locked scenes."""
        draft = self._get_record(draft_id)
        if draft is None:
            return execution_bundle

        locked_ids = set(draft["locked_scene_ids"])
        draft_bundle_dict = draft["bundle"]
        draft_scenes_by_id: dict[str, dict] = {
            s.get("scene_id"): s
            for s in draft_bundle_dict.get("scenes", [])
            if s.get("scene_id")
        }

        merged_scenes = []
        for exec_scene in execution_bundle.scenes:
            if exec_scene.scene_id in locked_ids and exec_scene.scene_id in draft_scenes_by_id:
                # Keep draft version for locked scenes
                merged_scenes.append(SceneEntry(**draft_scenes_by_id[exec_scene.scene_id]))
            else:
                merged_scenes.append(exec_scene)

        execution_bundle.scenes = merged_scenes

        # Persist the merged result
        merged_source = "merged"
        repo.update_draft(
            draft_id=draft_id,
            source=merged_source,
            bundle_dict=execution_bundle.model_dump(),
            expected_version=draft["version"],
        )
        return execution_bundle

    def import_bundle(self, bundle: ScenePromptBundle, workflow_id: str | None = None) -> str:
        """Import an external bundle as a new draft."""
        return self.create_draft(bundle, workflow_id=workflow_id)

    def list_drafts(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """List draft summaries.

        If workflow_id is provided, list drafts for that workflow.
        Otherwise, list all drafts (requires iterating all workflows or
        using a direct query).
        """
        if workflow_id is None:
            # List all drafts across all workflows
            conn = repo.get_connection()
            rows = conn.execute(
                "SELECT id, name, source, workflow_id, version, "
                "locked_scene_ids, created_at, updated_at "
                "FROM scene_drafts ORDER BY updated_at DESC"
            ).fetchall()
            return [repo._row_to_dict(r) for r in rows]

        records = repo.list_drafts(workflow_id)
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "source": r["source"],
                "workflow_id": r["workflow_id"],
                "version": r["version"],
                "locked_scene_ids": r["locked_scene_ids"],
                "scene_count": len(r["bundle"].get("scenes", [])),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in records
        ]

    def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft. Returns True on success."""
        try:
            repo.delete_draft(draft_id)
            return True
        except repo.SceneDraftNotFoundError:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_record(self, draft_id: str) -> dict[str, Any] | None:
        """Get raw record from repository. Returns None if not found."""
        try:
            return repo.get_draft(draft_id)
        except repo.SceneDraftNotFoundError:
            return None
