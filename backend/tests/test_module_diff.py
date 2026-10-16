"""Tests for Module Diff engine and compatibility checker."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.services.module_diff import (
    ModuleDiff,
    compute_module_diff,
    is_breaking,
    check_config_compatibility,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(
    *,
    version: str = "1.0.0",
    config_schema: dict | None = None,
    ports: dict | None = None,
    provider_policy: ProviderPolicy | None = None,
    label: str = "Test Module",
    description: str = "A test module",
) -> ModuleDefinition:
    """Create a minimal ModuleDefinition for testing."""
    return ModuleDefinition(
        id="test.module",
        version=version,
        status="published",
        baseKind="textToImage",
        category="image",
        label=label,
        description=description,
        providerPolicy=provider_policy
        or ProviderPolicy(
            capability="image",
            allowed=["openai", "doubao"],
            default="openai",
            locked=False,
        ),
        configSchema=config_schema
        or {
            "properties": {
                "model": {"type": "string", "title": "Model", "default": "gpt-4"},
                "temperature": {"type": "number", "title": "Temperature", "default": 0.7},
                "variantCount": {"type": "integer", "title": "Variants", "default": 1},
            },
            "required": ["model"],
        },
        ports=ports
        or {
            "inputs": [
                {"id": "text", "type": "text", "required": True, "cardinality": "one"}
            ],
            "outputs": [
                {"id": "result", "type": "text", "required": False, "cardinality": "one"}
            ],
        },
    )


# ---------------------------------------------------------------------------
# Diff engine tests
# ---------------------------------------------------------------------------


class TestModuleDiff:
    """Tests for compute_module_diff."""

    def test_identical_versions_no_diff(self):
        """Identical module versions produce no changes."""
        old = _make_module(version="1.0.0")
        new = _make_module(version="1.0.0")
        diff = compute_module_diff(old, new)

        assert diff.version_from == "1.0.0"
        assert diff.version_to == "1.0.0"
        assert diff.breaking is False
        assert diff.added_fields == []
        assert diff.removed_fields == []
        assert diff.changed_fields == []
        assert diff.added_ports == []
        assert diff.removed_ports == []
        assert diff.changed_ports == []
        assert diff.provider_changes is None
        assert diff.label_changed is False
        assert diff.description_changed is False

    def test_added_field_detected(self):
        """Adding a new config field is detected and non-breaking."""
        old = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string", "title": "Model"},
                }
            }
        )
        new = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string", "title": "Model"},
                    "top_p": {"type": "number", "title": "Top P", "default": 0.9},
                }
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.added_fields) == 1
        assert diff.added_fields[0]["key"] == "top_p"
        assert diff.breaking is False

    def test_removed_field_detected_breaking(self):
        """Removing a config field is detected and breaking."""
        old = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string", "title": "Model"},
                    "temperature": {"type": "number", "title": "Temperature"},
                }
            }
        )
        new = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string", "title": "Model"},
                }
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.removed_fields) == 1
        assert diff.removed_fields[0] == "temperature"
        assert diff.breaking is True

    def test_changed_field_type_detected_breaking(self):
        """Changing a field's type is detected and breaking."""
        old = _make_module(
            config_schema={
                "properties": {
                    "temperature": {"type": "number", "title": "Temp", "default": 0.7},
                }
            }
        )
        new = _make_module(
            config_schema={
                "properties": {
                    "temperature": {"type": "string", "title": "Temp", "default": "0.7"},
                }
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.changed_fields) == 1
        assert diff.changed_fields[0]["field"] == "temperature"
        assert "type" in diff.changed_fields[0]["changes"]
        assert diff.breaking is True

    def test_changed_field_default_non_breaking(self):
        """Changing a field's default is detected but non-breaking."""
        old = _make_module(
            config_schema={
                "properties": {
                    "temperature": {"type": "number", "title": "Temp", "default": 0.7},
                }
            }
        )
        new = _make_module(
            config_schema={
                "properties": {
                    "temperature": {"type": "number", "title": "Temp", "default": 0.9},
                }
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.changed_fields) == 1
        assert diff.changed_fields[0]["changes"]["default"] == {
            "from": 0.7,
            "to": 0.9,
        }
        assert diff.breaking is False

    def test_added_port_detected(self):
        """Adding a new port is detected and non-breaking."""
        old = _make_module(
            ports={
                "inputs": [{"id": "text", "type": "text", "required": True}],
                "outputs": [],
            }
        )
        new = _make_module(
            ports={
                "inputs": [{"id": "text", "type": "text", "required": True}],
                "outputs": [
                    {"id": "image", "type": "image", "required": False},
                ],
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.added_ports) == 1
        assert diff.added_ports[0]["id"] == "image"
        assert diff.added_ports[0]["direction"] == "outputs"
        assert diff.breaking is False

    def test_removed_port_detected_breaking(self):
        """Removing a port is detected and breaking."""
        old = _make_module(
            ports={
                "inputs": [
                    {"id": "text", "type": "text", "required": True},
                    {"id": "style", "type": "text", "required": False},
                ],
                "outputs": [],
            }
        )
        new = _make_module(
            ports={
                "inputs": [{"id": "text", "type": "text", "required": True}],
                "outputs": [],
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.removed_ports) == 1
        assert diff.removed_ports[0] == "inputs/style"
        assert diff.breaking is True

    def test_changed_port_cardinality_detected(self):
        """Changing port cardinality is detected."""
        old = _make_module(
            ports={
                "inputs": [
                    {"id": "text", "type": "text", "required": True, "cardinality": "one"}
                ],
                "outputs": [],
            }
        )
        new = _make_module(
            ports={
                "inputs": [
                    {"id": "text", "type": "text", "required": True, "cardinality": "many"}
                ],
                "outputs": [],
            }
        )
        diff = compute_module_diff(old, new)

        assert len(diff.changed_ports) == 1
        assert diff.changed_ports[0]["changes"]["cardinality"] == {
            "from": "one",
            "to": "many",
        }

    def test_provider_allowed_list_changed(self):
        """Changing the provider allowed list is detected."""
        old = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["openai", "doubao"],
                default="openai",
                locked=False,
            )
        )
        new = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["doubao", "midjourney"],
                default="doubao",
                locked=False,
            )
        )
        diff = compute_module_diff(old, new)

        assert diff.provider_changes is not None
        assert "allowed" in diff.provider_changes
        assert diff.provider_changes["allowed"]["from"] == ["openai", "doubao"]
        assert diff.provider_changes["allowed"]["to"] == ["doubao", "midjourney"]

    def test_provider_default_changed(self):
        """Changing the default provider is detected."""
        old = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["openai", "doubao"],
                default="openai",
                locked=False,
            )
        )
        new = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["openai", "doubao"],
                default="doubao",
                locked=False,
            )
        )
        diff = compute_module_diff(old, new)

        assert diff.provider_changes is not None
        assert "default" in diff.provider_changes
        assert diff.provider_changes["default"]["from"] == "openai"
        assert diff.provider_changes["default"]["to"] == "doubao"

    def test_provider_locked_changed(self):
        """Changing provider locked status is detected."""
        old = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["doubao"],
                default="doubao",
                locked=False,
            )
        )
        new = _make_module(
            provider_policy=ProviderPolicy(
                capability="image",
                allowed=["doubao"],
                default="doubao",
                locked=True,
            )
        )
        diff = compute_module_diff(old, new)

        assert diff.provider_changes is not None
        assert "locked" in diff.provider_changes
        assert diff.provider_changes["locked"]["from"] is False
        assert diff.provider_changes["locked"]["to"] is True

    def test_breaking_upgrade_requires_action(self):
        """A breaking upgrade (removed field) sets breaking=True."""
        old = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string"},
                    "deprecated_field": {"type": "string"},
                }
            }
        )
        new = _make_module(
            config_schema={"properties": {"model": {"type": "string"}}}
        )
        diff = compute_module_diff(old, new)

        assert diff.breaking is True

    def test_non_breaking_upgrade_is_safe(self):
        """Adding a field or port does not set breaking=True."""
        old = _make_module()
        new = _make_module(
            config_schema={
                "properties": {
                    "model": {"type": "string"},
                    "temperature": {"type": "number"},
                    "variantCount": {"type": "integer", "default": 1},
                    "new_option": {"type": "boolean", "default": True},
                }
            },
            label="Test Module v2",
        )
        diff = compute_module_diff(old, new)

        # Adding a field is non-breaking
        assert diff.breaking is False
        assert len(diff.added_fields) == 1

    def test_label_changed_detected(self):
        """Label change is detected."""
        old = _make_module(label="Old Name")
        new = _make_module(label="New Name")
        diff = compute_module_diff(old, new)

        assert diff.label_changed is True
        assert diff.description_changed is False

    def test_description_changed_detected(self):
        """Description change is detected."""
        old = _make_module(description="Old description")
        new = _make_module(description="Updated description")
        diff = compute_module_diff(old, new)

        assert diff.description_changed is True

    def test_variant_count_change_detected(self):
        """VariantCount default change produces an estimated call diff."""
        old = _make_module(
            config_schema={
                "properties": {
                    "variantCount": {"type": "integer", "default": 1},
                }
            }
        )
        new = _make_module(
            config_schema={
                "properties": {
                    "variantCount": {"type": "integer", "default": 3},
                }
            }
        )
        diff = compute_module_diff(old, new)

        assert diff.estimated_call_diff is not None
        assert diff.estimated_call_diff["before"] == 1
        assert diff.estimated_call_diff["after"] == 3

    def test_to_dict_serialization(self):
        """ModuleDiff.to_dict produces correct camelCase keys."""
        diff = ModuleDiff(version_from="1.0.0", version_to="2.0.0", breaking=True)
        d = diff.to_dict()

        assert d["versionFrom"] == "1.0.0"
        assert d["versionTo"] == "2.0.0"
        assert d["breaking"] is True
        assert d["addedFields"] == []
        assert d["removedFields"] == []
        assert d["changedFields"] == []
        assert d["addedPorts"] == []
        assert d["removedPorts"] == []
        assert d["changedPorts"] == []
        assert d["providerChanges"] is None
        assert d["labelChanged"] is False
        assert d["descriptionChanged"] is False
        assert d["estimatedCallDiff"] is None


# ---------------------------------------------------------------------------
# is_breaking edge cases
# ---------------------------------------------------------------------------


class TestIsBreaking:
    """Edge-case tests for is_breaking classification."""

    def test_provider_restriction_is_breaking(self):
        """Removing a previously allowed provider is breaking."""
        diff = ModuleDiff(
            version_from="1.0.0",
            version_to="2.0.0",
            provider_changes={
                "allowed": {"from": ["openai", "doubao"], "to": ["doubao"]}
            },
        )
        assert is_breaking(diff) is True

    def test_provider_addition_not_breaking(self):
        """Adding a new provider to the allowed list is not breaking."""
        diff = ModuleDiff(
            version_from="1.0.0",
            version_to="2.0.0",
            provider_changes={
                "allowed": {"from": ["openai"], "to": ["openai", "doubao"]}
            },
        )
        assert is_breaking(diff) is False

    def test_locking_provider_is_breaking(self):
        """Locking a previously unlocked provider is breaking."""
        diff = ModuleDiff(
            version_from="1.0.0",
            version_to="2.0.0",
            provider_changes={"locked": {"from": False, "to": True}},
        )
        assert is_breaking(diff) is True

    def test_unlocking_provider_not_breaking(self):
        """Unlocking a locked provider is not breaking."""
        diff = ModuleDiff(
            version_from="1.0.0",
            version_to="2.0.0",
            provider_changes={"locked": {"from": True, "to": False}},
        )
        assert is_breaking(diff) is False


# ---------------------------------------------------------------------------
# Config compatibility tests
# ---------------------------------------------------------------------------


class TestConfigCompatibility:
    """Tests for check_config_compatibility."""

    def test_compatible_config_no_warnings(self):
        """Old config is fully compatible with new schema."""
        old_config = {"model": "gpt-4", "temperature": 0.7}
        old_schema = {
            "properties": {
                "model": {"type": "string"},
                "temperature": {"type": "number"},
            }
        }
        new_schema = {
            "properties": {
                "model": {"type": "string"},
                "temperature": {"type": "number"},
                "top_p": {"type": "number", "default": 1.0},
            }
        }
        messages = check_config_compatibility(old_config, old_schema, new_schema)
        assert messages == []

    def test_removed_field_in_config_warning(self):
        """Config overriding a removed field produces a warning."""
        old_config = {"model": "gpt-4", "deprecated_opt": "yes"}
        old_schema = {
            "properties": {
                "model": {"type": "string"},
                "deprecated_opt": {"type": "string"},
            }
        }
        new_schema = {
            "properties": {
                "model": {"type": "string"},
            }
        }
        messages = check_config_compatibility(old_config, old_schema, new_schema)
        assert len(messages) == 1
        assert "removed" in messages[0].lower()
        assert "deprecated_opt" in messages[0]

    def test_type_changed_in_config_error(self):
        """Config with a type-changed field produces an error."""
        old_config = {"temperature": 0.7}
        old_schema = {"properties": {"temperature": {"type": "number"}}}
        new_schema = {"properties": {"temperature": {"type": "string"}}}
        messages = check_config_compatibility(old_config, old_schema, new_schema)
        assert len(messages) == 1
        assert "type changed" in messages[0].lower()
        assert "temperature" in messages[0]

    def test_config_not_overriding_removed_field_no_warning(self):
        """If config doesn't override a removed field, no warning."""
        old_config = {"model": "gpt-4"}
        old_schema = {
            "properties": {
                "model": {"type": "string"},
                "extra": {"type": "boolean"},
            }
        }
        new_schema = {"properties": {"model": {"type": "string"}}}
        messages = check_config_compatibility(old_config, old_schema, new_schema)
        assert messages == []

    def test_new_field_not_in_old_config_no_issue(self):
        """Adding new fields doesn't cause issues for existing configs."""
        old_config = {"model": "gpt-4"}
        old_schema = {"properties": {"model": {"type": "string"}}}
        new_schema = {
            "properties": {
                "model": {"type": "string"},
                "top_p": {"type": "number"},
            }
        }
        messages = check_config_compatibility(old_config, old_schema, new_schema)
        assert messages == []


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestModuleDiffAPI:
    """Integration tests for the diff API endpoint."""

    def test_diff_endpoint_identical_version(self):
        """GET /modules/{id}/diff with same from/to returns empty diff."""
        with TestClient(app) as client:
            resp = client.get(
                "/api/modules/builtin.seedream.text-to-image/diff",
                params={"from": "1.0.0", "to": "1.0.0"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["versionFrom"] == "1.0.0"
        assert data["versionTo"] == "1.0.0"
        assert data["breaking"] is False

    def test_diff_endpoint_version_not_found(self):
        """GET /modules/{id}/diff with nonexistent version returns 404."""
        with TestClient(app) as client:
            resp = client.get(
                "/api/modules/builtin.seedream.text-to-image/diff",
                params={"from": "1.0.0", "to": "99.99.99"},
            )
        assert resp.status_code == 404

    def test_diff_endpoint_module_not_found(self):
        """GET /modules/{id}/diff for nonexistent module returns 404."""
        with TestClient(app) as client:
            resp = client.get(
                "/api/modules/nonexistent.module/diff",
                params={"from": "1.0.0", "to": "2.0.0"},
            )
        assert resp.status_code == 404

    def test_compat_check_endpoint(self):
        """POST /modules/{id}/compat-check returns compatibility results."""
        with TestClient(app) as client:
            resp = client.post(
                "/api/modules/test.module/compat-check",
                json={
                "oldConfig": {"model": "gpt-4", "extra": "value"},
                "oldSchema": {
                    "properties": {
                        "model": {"type": "string"},
                        "extra": {"type": "string"},
                    }
                },
                "newSchema": {
                    "properties": {"model": {"type": "string"}}
                },
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compatible"] is False
        assert len(data["messages"]) == 1
        assert "extra" in data["messages"][0]
