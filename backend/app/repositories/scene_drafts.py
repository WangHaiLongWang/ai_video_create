"""Scene Draft Repository — SQLite persistence for scene drafts with lock/override."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.db.connection import get_connection


class SceneDraftNotFoundError(Exception):
    """Scene draft does not exist."""


class OptimisticLockError(Exception):
    """Version conflict during update."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict[str, Any]:
    """Convert sqlite3.Row to dict, parsing JSON fields.

    Handles rows that may or may not include bundle_json (e.g. summary queries).
    """
    d = dict(row)
    if "bundle_json" in d:
        d["bundle"] = json.loads(d.pop("bundle_json"))
    if "locked_scene_ids" in d:
        raw = d["locked_scene_ids"]
        d["locked_scene_ids"] = json.loads(raw) if isinstance(raw, str) else raw
    return d


def create_draft(
    *,
    draft_id: str,
    workflow_id: str,
    name: str,
    source: str,
    bundle_dict: dict[str, Any],
    locked_scene_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new scene draft. Returns the created draft as a dict."""
    conn = get_connection()
    now = _now_iso()
    locked = locked_scene_ids or []

    conn.execute(
        "INSERT INTO scene_drafts (id, workflow_id, name, source, bundle_json, "
        "locked_scene_ids, version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (
            draft_id,
            workflow_id,
            name,
            source,
            json.dumps(bundle_dict, ensure_ascii=False),
            json.dumps(locked, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()

    return get_draft(draft_id)


def get_draft(draft_id: str) -> dict[str, Any]:
    """Get a single scene draft by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM scene_drafts WHERE id = ?", (draft_id,)
    ).fetchone()
    if row is None:
        raise SceneDraftNotFoundError(f"Scene draft '{draft_id}' not found")
    return _row_to_dict(row)


def list_drafts(workflow_id: str) -> list[dict[str, Any]]:
    """List all scene drafts for a workflow, ordered by updated_at DESC."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scene_drafts WHERE workflow_id = ? ORDER BY updated_at DESC",
        (workflow_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_draft(
    *,
    draft_id: str,
    name: str | None = None,
    source: str | None = None,
    bundle_dict: dict[str, Any] | None = None,
    locked_scene_ids: list[str] | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    """Update a scene draft with optimistic locking.

    If expected_version is provided, the update only succeeds if the current
    version matches. The version is automatically incremented on success.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT version FROM scene_drafts WHERE id = ?", (draft_id,)
    ).fetchone()
    if row is None:
        raise SceneDraftNotFoundError(f"Scene draft '{draft_id}' not found")

    if expected_version is not None and row["version"] != expected_version:
        raise OptimisticLockError(
            f"Version conflict on draft '{draft_id}': "
            f"expected v{expected_version}, actual v{row['version']}"
        )

    now = _now_iso()
    new_version = row["version"] + 1

    # Build dynamic SET clause
    updates: list[str] = ["version = ?", "updated_at = ?"]
    params: list[Any] = [new_version, now]

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if source is not None:
        updates.append("source = ?")
        params.append(source)
    if bundle_dict is not None:
        updates.append("bundle_json = ?")
        params.append(json.dumps(bundle_dict, ensure_ascii=False))
    if locked_scene_ids is not None:
        updates.append("locked_scene_ids = ?")
        params.append(json.dumps(locked_scene_ids, ensure_ascii=False))

    params.append(draft_id)
    conn.execute(
        f"UPDATE scene_drafts SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()

    return get_draft(draft_id)


def delete_draft(draft_id: str) -> None:
    """Delete a scene draft."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM scene_drafts WHERE id = ?", (draft_id,)
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise SceneDraftNotFoundError(f"Scene draft '{draft_id}' not found")


def lock_scene(draft_id: str, scene_id: str) -> dict[str, Any]:
    """Add a scene_id to the locked list."""
    draft = get_draft(draft_id)
    locked = draft["locked_scene_ids"]
    if scene_id not in locked:
        locked.append(scene_id)
    return update_draft(
        draft_id=draft_id,
        locked_scene_ids=locked,
        expected_version=draft["version"],
    )


def unlock_scene(draft_id: str, scene_id: str) -> dict[str, Any]:
    """Remove a scene_id from the locked list."""
    draft = get_draft(draft_id)
    locked = [sid for sid in draft["locked_scene_ids"] if sid != scene_id]
    return update_draft(
        draft_id=draft_id,
        locked_scene_ids=locked,
        expected_version=draft["version"],
    )
