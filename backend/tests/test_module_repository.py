"""Tests for ModuleRepository — persistent storage + optimistic locking."""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from backend.app.db.connection import close_connection, get_connection, init_db
from backend.app.repositories.module_repository import (
    ConflictError,
    ModuleNotFoundError,
    ModuleRepository,
)
from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_registry import (
    BUILTIN_MODULES,
    ModuleRegistry,
    ModuleValidationError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Provide a fresh in-memory SQLite database for each test."""
    import backend.app.db.connection as conn_mod

    # Use in-memory database for isolation
    conn_mod._CONNECTION = None
    conn_mod._DB_PATH = None

    # Monkey-patch to use in-memory DB
    original_get_db_path = conn_mod._get_db_path

    def _in_memory_path():
        return tmp_path / "test_modules.db"

    conn_mod._get_db_path = _in_memory_path

    # Also need a fresh connection
    conn_mod._CONNECTION = None
    init_db()

    yield

    close_connection()
    conn_mod._get_db_path = original_get_db_path
    conn_mod._CONNECTION = None


@pytest.fixture
def repo():
    """Fresh ModuleRepository using the in-memory DB."""
    return ModuleRepository()


def _make_definition(
    module_id: str = "test.custom.module",
    version: str = "1.0.0",
    status: str = "draft",
    base_kind: str = "textToImage",
    category: str = "image",
    label: str = "Test Module",
    capability: str = "image",
) -> ModuleDefinition:
    """Helper to create a ModuleDefinition for testing."""
    return ModuleDefinition(
        id=module_id,
        version=version,
        status=status,
        baseKind=base_kind,
        category=category,
        label=label,
        providerPolicy=ProviderPolicy(
            capability=capability,
            allowed=["test-provider"],
            default="test-provider",
        ),
    )


# ---------------------------------------------------------------------------
# 1. Create draft and retrieve
# ---------------------------------------------------------------------------


class TestCreateAndRetrieve:
    def test_create_draft_and_retrieve(self, repo: ModuleRepository):
        definition = _make_definition()
        result = repo.create_draft(definition)
        assert result.id == "test.custom.module"
        assert result.version == "1.0.0"
        assert result.expected_version == 1

        retrieved = repo.get_module("test.custom.module", "1.0.0")
        assert retrieved is not None
        assert retrieved.id == "test.custom.module"

    def test_get_nonexistent_module_returns_none(self, repo: ModuleRepository):
        assert repo.get_module("nonexistent", "1.0.0") is None

    def test_create_draft_persists_definition_json(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        conn = get_connection()
        row = conn.execute(
            "SELECT definition_json FROM module_definitions WHERE id = ? AND version = ?",
            ("test.custom.module", "1.0.0"),
        ).fetchone()
        assert row is not None
        import json
        data = json.loads(row["definition_json"])
        assert data["id"] == "test.custom.module"
        assert data["baseKind"] == "textToImage"


# ---------------------------------------------------------------------------
# 2. List modules with status filter
# ---------------------------------------------------------------------------


class TestListModules:
    def test_list_modules_returns_created_drafts(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        modules = repo.list_modules(status="draft")
        ids = [m.id for m in modules]
        assert "test.custom.module" in ids

    def test_list_modules_status_filter_draft(self, repo: ModuleRepository):
        repo.create_draft(_make_definition(module_id="mod.a", version="1.0.0"))
        repo.create_draft(_make_definition(module_id="mod.b", version="1.0.0", status="draft"))
        # mod.a is draft, publish mod.b
        repo.publish("mod.b", "1.0.0", expected_version=1)

        drafts = repo.list_modules(status="draft")
        assert any(m.id == "mod.a" for m in drafts)
        assert not any(m.id == "mod.b" for m in drafts)

    def test_list_modules_status_filter_published(self, repo: ModuleRepository):
        repo.create_draft(_make_definition(module_id="mod.a", version="1.0.0"))
        repo.publish("mod.a", "1.0.0", expected_version=1)

        published = repo.list_modules(status="published")
        assert any(m.id == "mod.a" for m in published)

    def test_list_modules_returns_empty_when_no_match(self, repo: ModuleRepository):
        repo.create_draft(_make_definition())
        archived = repo.list_modules(status="archived")
        assert len(archived) == 0


# ---------------------------------------------------------------------------
# 3. Update draft with optimistic lock
# ---------------------------------------------------------------------------


class TestUpdateDraft:
    def test_update_draft_succeeds(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        updated = _make_definition(label="Updated Label")
        result = repo.update_draft("test.custom.module", "1.0.0", updated, expected_version=1)
        assert result.label == "Updated Label"
        assert result.expected_version == 2

        retrieved = repo.get_module("test.custom.module", "1.0.0")
        assert retrieved is not None

    def test_update_draft_with_stale_version_raises_conflict(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        # First update succeeds
        updated = _make_definition(label="V2")
        repo.update_draft("test.custom.module", "1.0.0", updated, expected_version=1)

        # Second update with stale version fails
        updated2 = _make_definition(label="V3")
        with pytest.raises(ConflictError) as exc_info:
            repo.update_draft("test.custom.module", "1.0.0", updated2, expected_version=1)
        assert exc_info.value.expected_version == 1
        assert exc_info.value.current_version == 2

    def test_update_draft_increments_expected_version(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        updated = _make_definition(label="V2")
        repo.update_draft("test.custom.module", "1.0.0", updated, expected_version=1)

        # Check the DB directly
        conn = get_connection()
        row = conn.execute(
            "SELECT expected_version FROM module_definitions WHERE id = ? AND version = ?",
            ("test.custom.module", "1.0.0"),
        ).fetchone()
        assert row["expected_version"] == 2


# ---------------------------------------------------------------------------
# 4. Publish
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_draft(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        result = repo.publish("test.custom.module", "1.0.0", expected_version=1)
        assert result.status == "published"

        retrieved = repo.get_module("test.custom.module", "1.0.0")
        assert retrieved is not None
        assert retrieved.status == "published"

    def test_publish_already_published_raises(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)

        with pytest.raises(ValueError, match="only draft"):
            repo.publish("test.custom.module", "1.0.0", expected_version=2)

    def test_publish_nonexistent_raises(self, repo: ModuleRepository):
        with pytest.raises(ModuleNotFoundError):
            repo.publish("nonexistent", "1.0.0", expected_version=1)


# ---------------------------------------------------------------------------
# 5. Archive
# ---------------------------------------------------------------------------


class TestArchive:
    def test_archive_published_module(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)

        result = repo.archive("test.custom.module", "1.0.0", expected_version=2)
        assert result.status == "archived"

        # Still accessible via get
        retrieved = repo.get_module("test.custom.module", "1.0.0")
        assert retrieved is not None

    def test_archive_draft_raises(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        with pytest.raises(ValueError, match="only published"):
            repo.archive("test.custom.module", "1.0.0", expected_version=1)

    def test_archive_nonexistent_raises(self, repo: ModuleRepository):
        with pytest.raises(ModuleNotFoundError):
            repo.archive("nonexistent", "1.0.0", expected_version=1)


# ---------------------------------------------------------------------------
# 6. Usage tracking
# ---------------------------------------------------------------------------


class TestUsageTracking:
    def test_record_usage(self, repo: ModuleRepository):
        repo.record_usage("wf-1", "node-1", "mod-1", "1.0.0")
        usage = repo.get_usage("mod-1")
        assert len(usage) == 1
        assert usage[0]["workflow_id"] == "wf-1"
        assert usage[0]["node_id"] == "node-1"

    def test_get_usage_multiple(self, repo: ModuleRepository):
        repo.record_usage("wf-1", "node-1", "mod-1", "1.0.0")
        repo.record_usage("wf-2", "node-2", "mod-1", "1.0.0")
        usage = repo.get_usage("mod-1")
        assert len(usage) == 2

    def test_is_used_in_workflow(self, repo: ModuleRepository):
        repo.record_usage("wf-1", "node-1", "mod-1", "1.0.0")
        assert repo.is_used_in_workflow("mod-1", "wf-1") is True
        assert repo.is_used_in_workflow("mod-1", "wf-2") is False

    def test_get_usage_empty(self, repo: ModuleRepository):
        usage = repo.get_usage("nonexistent")
        assert len(usage) == 0


# ---------------------------------------------------------------------------
# 7. DB initialization creates tables
# ---------------------------------------------------------------------------


class TestDBInit:
    def test_tables_are_created(self, repo: ModuleRepository):
        conn = get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "module_definitions" in table_names
        assert "module_usage" in table_names

    def test_idempotent_init(self):
        """Calling init twice should not fail."""
        init_db()
        init_db()


# ---------------------------------------------------------------------------
# 8. Concurrent update detection
# ---------------------------------------------------------------------------


class TestConcurrentUpdates:
    def test_concurrent_update_conflict(self, repo: ModuleRepository):
        """Two sequential updates with the same expected_version detect conflict."""
        definition = _make_definition()
        repo.create_draft(definition)

        updated1 = _make_definition(label="First")
        repo.update_draft("test.custom.module", "1.0.0", updated1, expected_version=1)

        # Second update with stale expected_version should fail
        updated2 = _make_definition(label="Second")
        with pytest.raises(ConflictError) as exc_info:
            repo.update_draft("test.custom.module", "1.0.0", updated2, expected_version=1)
        assert exc_info.value.expected_version == 1
        assert exc_info.value.current_version == 2

    def test_sequential_optimistic_lock_prevents_lost_update(self, repo: ModuleRepository):
        """Simulate two concurrent clients: only one succeeds."""
        definition = _make_definition()
        repo.create_draft(definition)

        # Client A reads expected_version=1
        raw1 = repo._get_raw("test.custom.module", "1.0.0")
        assert raw1 is not None
        ev_a = raw1["expected_version"]

        # Client B reads expected_version=1 and updates first
        updated_b = _make_definition(label="Client B")
        repo.update_draft("test.custom.module", "1.0.0", updated_b, expected_version=ev_a)

        # Client A tries to update with stale version
        updated_a = _make_definition(label="Client A")
        with pytest.raises(ConflictError):
            repo.update_draft("test.custom.module", "1.0.0", updated_a, expected_version=ev_a)


# ---------------------------------------------------------------------------
# 9. List with capability filter
# ---------------------------------------------------------------------------


class TestListCapabilityFilter:
    def test_list_by_provider_capability(self, repo: ModuleRepository):
        repo.create_draft(_make_definition(module_id="img.mod", base_kind="textToImage"))
        repo.create_draft(_make_definition(module_id="vid.mod", base_kind="textToImage", category="video", capability="video"))

        image_mods = repo.list_modules(capability="image")
        assert any(m.id == "img.mod" for m in image_mods)
        assert not any(m.id == "vid.mod" for m in image_mods)

        video_mods = repo.list_modules(capability="video")
        assert any(m.id == "vid.mod" for m in video_mods)
        assert not any(m.id == "img.mod" for m in video_mods)


class TestSemanticVersionOrdering:
    def test_list_modules_uses_numeric_semver_order(self, repo: ModuleRepository):
        repo.create_draft(_make_definition(module_id="versioned.mod", version="1.9.0"))
        repo.create_draft(_make_definition(module_id="versioned.mod", version="1.10.0"))
        modules = {module.id: module for module in repo.list_modules()}
        assert modules["versioned.mod"].version == "1.10.0"


class TestPersistentPublishGate:
    def test_publish_draft_rejects_invalid_provider_policy(self, repo: ModuleRepository):
        definition = _make_definition()
        definition.provider_policy = ProviderPolicy(
            capability="image", allowed=["doubao"], default="openai", locked=True
        )
        repo.create_draft(definition)
        registry = ModuleRegistry(repository=repo)
        with pytest.raises(ModuleValidationError) as exc_info:
            registry.publish_draft(definition.id, definition.version, expected_version=1)
        assert any(
            isinstance(error, dict) and error.get("error") == "DEFAULT_PROVIDER_NOT_ALLOWED"
            for error in exc_info.value.errors
        )
        assert repo.get_module(definition.id, definition.version).status == "draft"


# ---------------------------------------------------------------------------
# 10. Builtin modules always appear in registry list
# ---------------------------------------------------------------------------


class TestBuiltinIntegration:
    def test_builtin_always_in_registry_list(self):
        """Even without a repository, builtin modules appear in list_modules."""
        registry = ModuleRegistry(repository=None)
        modules = registry.list_modules()
        ids = [m.id for m in modules]
        assert "builtin.seedream.text-to-image" in ids

    def test_builtin_in_registry_with_repository(self, repo: ModuleRepository):
        """Builtin modules are merged with DB modules when repository is set."""
        repo.create_draft(_make_definition(module_id="custom.mod"))
        registry = ModuleRegistry(repository=repo)
        modules = registry.list_modules()
        ids = [m.id for m in modules]
        assert "builtin.seedream.text-to-image" in ids
        assert "custom.mod" in ids

    def test_registry_create_draft_delegates_to_repository(self, repo: ModuleRepository):
        registry = ModuleRegistry(repository=repo)
        definition = _make_definition(module_id="reg.mod")
        result = registry.create_draft(definition)
        assert result.id == "reg.mod"

    def test_registry_without_repository_raises(self):
        registry = ModuleRegistry(repository=None)
        definition = _make_definition()
        with pytest.raises(RuntimeError, match="Repository not configured"):
            registry.create_draft(definition)


# ---------------------------------------------------------------------------
# 11. Archive then still accessible via get
# ---------------------------------------------------------------------------


class TestArchiveAccessibility:
    def test_archived_module_still_gettable(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)
        repo.archive("test.custom.module", "1.0.0", expected_version=2)

        retrieved = repo.get_module("test.custom.module", "1.0.0")
        assert retrieved is not None
        assert retrieved.status == "archived"

    def test_archived_module_not_in_draft_list(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)
        repo.archive("test.custom.module", "1.0.0", expected_version=2)

        drafts = repo.list_modules(status="draft")
        assert not any(m.id == "test.custom.module" for m in drafts)

    def test_archived_module_in_archived_list(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)
        repo.archive("test.custom.module", "1.0.0", expected_version=2)

        archived = repo.list_modules(status="archived")
        assert any(m.id == "test.custom.module" for m in archived)


# ---------------------------------------------------------------------------
# 12. Update draft on non-draft raises
# ---------------------------------------------------------------------------


class TestUpdateNonDraft:
    def test_update_published_raises(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)

        updated = _make_definition(label="Should Fail")
        with pytest.raises(ValueError, match="only draft"):
            repo.update_draft("test.custom.module", "1.0.0", updated, expected_version=2)

    def test_update_nonexistent_raises(self, repo: ModuleRepository):
        updated = _make_definition(module_id="nonexistent")
        with pytest.raises(ModuleNotFoundError):
            repo.update_draft("nonexistent", "1.0.0", updated, expected_version=1)


# ---------------------------------------------------------------------------
# 13. Clone
# ---------------------------------------------------------------------------


class TestClone:
    def test_clone_creates_new_draft_with_incremented_version(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        cloned = repo.clone("test.custom.module", "1.0.0")
        assert cloned.id == "test.custom.module-copy"
        assert cloned.version == "1.0.1"
        assert cloned.status == "draft"

    def test_clone_from_published_module(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)
        repo.publish("test.custom.module", "1.0.0", expected_version=1)

        cloned = repo.clone("test.custom.module", "1.0.0")
        assert cloned.id == "test.custom.module-copy"
        assert cloned.version == "1.0.1"
        assert cloned.status == "draft"

    def test_clone_persists_to_db(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        repo.clone("test.custom.module", "1.0.0")

        # Verify the cloned module is in the DB
        retrieved = repo.get_module("test.custom.module-copy", "1.0.1")
        assert retrieved is not None
        assert retrieved.status == "draft"

    def test_clone_nonexistent_raises(self, repo: ModuleRepository):
        with pytest.raises(ModuleNotFoundError):
            repo.clone("nonexistent", "1.0.0")

    def test_clone_auto_resolves_expected_version(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        # Clone without specifying expected_version
        cloned = repo.clone("test.custom.module", "1.0.0")
        assert cloned.status == "draft"
        assert cloned.id == "test.custom.module-copy"

    def test_clone_with_wrong_expected_version_raises_conflict(self, repo: ModuleRepository):
        definition = _make_definition()
        repo.create_draft(definition)

        # Clone with wrong expected_version should fail
        with pytest.raises(ConflictError):
            repo.clone("test.custom.module", "1.0.0", expected_version=99)

    def test_clone_preserves_module_data(self, repo: ModuleRepository):
        definition = _make_definition(label="Original Module", category="image")
        repo.create_draft(definition)

        cloned = repo.clone("test.custom.module", "1.0.0")
        assert cloned.label == "Original Module"
        assert cloned.category == "image"
        assert cloned.base_kind == "textToImage"
