"""Module definitions repository — persistent storage with optimistic locking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.app.db.connection import get_connection
from backend.app.schemas.module_definition import ModuleDefinition


class ConflictError(Exception):
    """Optimistic lock version conflict."""

    def __init__(self, module_id: str, expected_version: int, current_version: int) -> None:
        self.module_id = module_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Version conflict for module {module_id}: "
            f"expected expected_version={expected_version}, "
            f"but current expected_version={current_version}"
        )


class ModuleNotFoundError(Exception):
    """Module definition not found."""


class ModuleRepository:
    """Persistent storage for module definitions with optimistic locking."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize repository.

        Args:
            db_path: Optional db_path override (unused when using shared connection).
                     Kept for testability but the actual connection comes from
                     ``backend.app.db.connection``.
        """
        # Ensure tables exist
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create tables if they do not already exist (idempotent)."""
        conn = get_connection()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS module_definitions (
                id               TEXT NOT NULL,
                version          TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'draft',
                base_kind        TEXT NOT NULL,
                definition_json  TEXT NOT NULL,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                published_at     TEXT,
                archived_at      TEXT,
                expected_version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (id, version)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS module_usage (
                workflow_id     TEXT NOT NULL,
                node_id         TEXT NOT NULL,
                module_id       TEXT NOT NULL,
                module_version  TEXT NOT NULL,
                PRIMARY KEY (workflow_id, node_id)
            )"""
        )
        conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_definition(row: Any) -> ModuleDefinition:
        """Deserialize a database row into a ModuleDefinition."""
        definition_json = row["definition_json"]
        data = json.loads(definition_json)
        return ModuleDefinition.model_validate(data)

    def _get_raw(self, module_id: str, version: str) -> dict | None:
        """Return the raw row dict or None."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM module_definitions WHERE id = ? AND version = ?",
            (module_id, version),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_draft(self, definition: ModuleDefinition) -> ModuleDefinition:
        """Persist a new draft module definition."""
        now = self._now_iso()
        definition_data = definition.model_dump(mode="json", by_alias=True)
        conn = get_connection()
        conn.execute(
            "INSERT INTO module_definitions "
            "(id, version, status, base_kind, definition_json, created_at, updated_at, expected_version) "
            "VALUES (?, ?, 'draft', ?, ?, ?, ?, 1)",
            (
                definition.id,
                definition.version,
                definition.base_kind,
                json.dumps(definition_data, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
        return definition.model_copy(update={"status": "draft"})

    def get_module(self, module_id: str, version: str) -> ModuleDefinition | None:
        """Retrieve a specific module version."""
        raw = self._get_raw(module_id, version)
        if raw is None:
            return None
        return self._row_to_definition(raw)

    def list_modules(
        self,
        status: str | None = None,
        capability: str | None = None,
    ) -> list[ModuleDefinition]:
        """List modules with optional status and capability filters.

        Returns the latest version of each module matching the filters.
        """
        conn = get_connection()
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if capability:
            conditions.append("base_kind = ?")
            params.append(capability)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Group by id, pick latest version
        rows = conn.execute(
            f"SELECT id, MAX(version) as max_version FROM module_definitions {where} GROUP BY id",
            params,
        ).fetchall()

        result: list[ModuleDefinition] = []
        for row in rows:
            raw = self._get_raw(row["id"], row["max_version"])
            if raw:
                result.append(self._row_to_definition(raw))
        return result

    def update_draft(
        self,
        module_id: str,
        version: str,
        definition: ModuleDefinition,
        expected_version: int,
    ) -> ModuleDefinition:
        """Update a draft with optimistic locking.

        Raises ConflictError if the expected_version does not match.
        """
        conn = get_connection()
        raw = self._get_raw(module_id, version)
        if raw is None:
            raise ModuleNotFoundError(f"Module {module_id}@{version} not found")

        if raw["expected_version"] != expected_version:
            raise ConflictError(module_id, expected_version, raw["expected_version"])

        if raw["status"] != "draft":
            raise ValueError(
                f"Cannot update module {module_id}@{version} with status '{raw['status']}': "
                "only draft modules can be updated"
            )

        now = self._now_iso()
        new_expected = expected_version + 1
        conn.execute(
            "UPDATE module_definitions "
            "SET definition_json = ?, base_kind = ?, updated_at = ?, expected_version = ? "
            "WHERE id = ? AND version = ?",
            (
                json.dumps(definition.model_dump(mode="json", by_alias=True), ensure_ascii=False),
                definition.base_kind,
                now,
                new_expected,
                module_id,
                version,
            ),
        )
        conn.commit()
        return definition

    def publish(
        self,
        module_id: str,
        version: str,
        expected_version: int | None = None,
    ) -> ModuleDefinition:
        """Publish a draft module. Only draft modules can be published.

        If expected_version is None, it is auto-resolved from the current row
        (convenience for single-user operations like UI publish).

        Raises ConflictError if expected_version does not match.
        Raises ValueError if module is not in draft status.
        """
        conn = get_connection()
        raw = self._get_raw(module_id, version)
        if raw is None:
            raise ModuleNotFoundError(f"Module {module_id}@{version} not found")

        effective_ev = expected_version if expected_version is not None else raw["expected_version"]

        if raw["expected_version"] != effective_ev:
            raise ConflictError(module_id, effective_ev, raw["expected_version"])

        if raw["status"] != "draft":
            raise ValueError(
                f"Cannot publish module {module_id}@{version} with status '{raw['status']}': "
                "only draft modules can be published"
            )

        now = self._now_iso()
        new_expected = effective_ev + 1
        # Update definition_json to reflect new status
        definition = self._row_to_definition(raw)
        definition.status = "published"
        updated_json = json.dumps(definition.model_dump(mode="json", by_alias=True), ensure_ascii=False)
        conn.execute(
            "UPDATE module_definitions "
            "SET status = 'published', published_at = ?, updated_at = ?, expected_version = ?, definition_json = ? "
            "WHERE id = ? AND version = ?",
            (now, now, new_expected, updated_json, module_id, version),
        )
        conn.commit()
        return definition

    def archive(
        self,
        module_id: str,
        version: str,
        expected_version: int | None = None,
    ) -> ModuleDefinition:
        """Archive a published module. Only published modules can be archived.

        If expected_version is None, it is auto-resolved from the current row.

        Raises ConflictError if expected_version does not match.
        Raises ValueError if module is not in published status.
        """
        conn = get_connection()
        raw = self._get_raw(module_id, version)
        if raw is None:
            raise ModuleNotFoundError(f"Module {module_id}@{version} not found")

        effective_ev = expected_version if expected_version is not None else raw["expected_version"]

        if raw["expected_version"] != effective_ev:
            raise ConflictError(module_id, effective_ev, raw["expected_version"])

        if raw["status"] != "published":
            raise ValueError(
                f"Cannot archive module {module_id}@{version} with status '{raw['status']}': "
                "only published modules can be archived"
            )

        now = self._now_iso()
        new_expected = effective_ev + 1
        # Update definition_json to reflect new status
        definition = self._row_to_definition(raw)
        definition.status = "archived"
        updated_json = json.dumps(definition.model_dump(mode="json", by_alias=True), ensure_ascii=False)
        conn.execute(
            "UPDATE module_definitions "
            "SET status = 'archived', archived_at = ?, updated_at = ?, expected_version = ?, definition_json = ? "
            "WHERE id = ? AND version = ?",
            (now, now, new_expected, updated_json, module_id, version),
        )
        conn.commit()
        return definition

    def clone(
        self,
        module_id: str,
        version: str,
        expected_version: int | None = None,
    ) -> ModuleDefinition:
        """Clone a published or draft module into a new draft with an incremented version.

        The new draft gets a fresh id (based on the original with '-copy' suffix),
        version bumped to next patch, status set to 'draft', and expected_version reset to 1.

        If expected_version is None, it is auto-resolved from the current row.

        Raises ConflictError if expected_version does not match.
        Raises ModuleNotFoundError if the source module does not exist.
        """
        conn = get_connection()
        raw = self._get_raw(module_id, version)
        if raw is None:
            raise ModuleNotFoundError(f"Module {module_id}@{version} not found")

        effective_ev = expected_version if expected_version is not None else raw["expected_version"]

        if raw["expected_version"] != effective_ev:
            raise ConflictError(module_id, effective_ev, raw["expected_version"])

        # Read the source definition
        definition = self._row_to_definition(raw)

        # Increment version: bump patch (e.g. 1.2.3 -> 1.2.4)
        parts = definition.version.split(".")
        patch = int(parts[-1]) + 1
        parts[-1] = str(patch)
        new_version = ".".join(parts)

        # Create new id with '-copy' suffix to avoid collisions
        new_id = f"{module_id}-copy"

        now = self._now_iso()
        definition.id = new_id
        definition.version = new_version
        definition.status = "draft"

        definition_data = definition.model_dump(mode="json", by_alias=True)
        conn.execute(
            "INSERT INTO module_definitions "
            "(id, version, status, base_kind, definition_json, created_at, updated_at, expected_version) "
            "VALUES (?, ?, 'draft', ?, ?, ?, ?, 1)",
            (
                definition.id,
                definition.version,
                definition.base_kind,
                json.dumps(definition_data, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
        return definition

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_usage(
        self,
        workflow_id: str,
        node_id: str,
        module_id: str,
        module_version: str,
    ) -> None:
        """Record that a workflow node uses a specific module version."""
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO module_usage "
            "(workflow_id, node_id, module_id, module_version) "
            "VALUES (?, ?, ?, ?)",
            (workflow_id, node_id, module_id, module_version),
        )
        conn.commit()

    def get_usage(self, module_id: str) -> list[dict]:
        """Return all usage records for a given module."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM module_usage WHERE module_id = ?", (module_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def is_used_in_workflow(self, module_id: str, workflow_id: str) -> bool:
        """Check whether a module is used in a specific workflow."""
        conn = get_connection()
        row = conn.execute(
            "SELECT 1 FROM module_usage WHERE module_id = ? AND workflow_id = ? LIMIT 1",
            (module_id, workflow_id),
        ).fetchone()
        return row is not None
