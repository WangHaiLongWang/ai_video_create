"""Tests for module dependency extraction, resolution, and degraded workflows."""

from __future__ import annotations

import pytest

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.services.module_dependency import (
    ModuleDependency,
    create_degraded_workflow,
    extract_module_dependencies,
    resolve_dependencies,
)
from backend.app.services.module_registry import ModuleRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry_with_seedream() -> ModuleRegistry:
    """Return a registry pre-loaded with the built-in Seedream module."""
    return ModuleRegistry()


def _make_workflow_spec(
    nodes: list[dict] | None = None,
    *,
    module_id: str | None = None,
    module_version: str = "1.0.0",
    node_id: str = "node-1",
) -> dict:
    """Build a minimal workflow spec with an optional module reference."""
    if nodes is None:
        nodes = []
    if module_id:
        nodes.append({
            "id": node_id,
            "type": "studio",
            "position": {"x": 0, "y": 0},
            "data": {
                "label": "Test",
                "description": "",
                "kind": "textToImage",
                "module_id": module_id,
                "module_version": module_version,
                "config": {},
            },
        })
    return {
        "id": "wf-test",
        "name": "Test Workflow",
        "nodes": nodes,
        "edges": [],
    }


def _make_workflow_with_multiple_modules() -> dict:
    """Workflow referencing two different modules."""
    return {
        "id": "wf-multi",
        "name": "Multi Module Workflow",
        "nodes": [
            {
                "id": "n1",
                "type": "studio",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Image Gen",
                    "description": "",
                    "kind": "textToImage",
                    "module_id": "builtin.seedream.text-to-image",
                    "module_version": "1.0.0",
                    "config": {},
                },
            },
            {
                "id": "n2",
                "type": "studio",
                "position": {"x": 200, "y": 0},
                "data": {
                    "label": "Missing Node",
                    "description": "",
                    "kind": "textToImage",
                    "module_id": "nonexistent.module",
                    "module_version": "2.0.0",
                    "config": {},
                },
            },
        ],
        "edges": [],
    }


# ---------------------------------------------------------------------------
# Tests — extract_module_dependencies
# ---------------------------------------------------------------------------

class TestExtractModuleDependencies:
    """Tests for extract_module_dependencies."""

    def test_extract_with_module(self):
        spec = _make_workflow_spec(module_id="builtin.seedream.text-to-image")
        deps = extract_module_dependencies(spec)
        assert len(deps) == 1
        assert deps[0].module_id == "builtin.seedream.text-to-image"
        assert deps[0].module_version == "1.0.0"
        assert deps[0].node_ids == ["node-1"]

    def test_extract_without_modules(self):
        spec = _make_workflow_spec()
        deps = extract_module_dependencies(spec)
        assert deps == []

    def test_extract_deduplicates_same_module(self):
        spec = _make_workflow_spec()
        spec["nodes"] = [
            {
                "id": "n1",
                "type": "studio",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "A",
                    "description": "",
                    "kind": "textToImage",
                    "module_id": "builtin.seedream.text-to-image",
                    "module_version": "1.0.0",
                    "config": {},
                },
            },
            {
                "id": "n2",
                "type": "studio",
                "position": {"x": 100, "y": 0},
                "data": {
                    "label": "B",
                    "description": "",
                    "kind": "textToImage",
                    "module_id": "builtin.seedream.text-to-image",
                    "module_version": "1.0.0",
                    "config": {},
                },
            },
        ]
        deps = extract_module_dependencies(spec)
        assert len(deps) == 1
        assert set(deps[0].node_ids) == {"n1", "n2"}

    def test_extract_multiple_different_modules(self):
        spec = _make_workflow_with_multiple_modules()
        deps = extract_module_dependencies(spec)
        assert len(deps) == 2
        ids = {d.module_id for d in deps}
        assert "builtin.seedream.text-to-image" in ids
        assert "nonexistent.module" in ids

    def test_extract_camel_case_keys(self):
        """Should handle both snake_case and camelCase node data keys."""
        spec = {
            "id": "wf-camel",
            "name": "Camel",
            "nodes": [
                {
                    "id": "n1",
                    "type": "studio",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "label": "X",
                        "description": "",
                        "kind": "textToImage",
                        "moduleId": "some.module",
                        "moduleVersion": "3.0.0",
                        "config": {},
                    },
                },
            ],
            "edges": [],
        }
        deps = extract_module_dependencies(spec)
        assert len(deps) == 1
        assert deps[0].module_id == "some.module"
        assert deps[0].module_version == "3.0.0"

    def test_empty_workflow_no_nodes(self):
        spec = {"id": "wf-empty", "name": "Empty", "nodes": [], "edges": []}
        deps = extract_module_dependencies(spec)
        assert deps == []


# ---------------------------------------------------------------------------
# Tests — resolve_dependencies
# ---------------------------------------------------------------------------

class TestResolveDependencies:
    """Tests for resolve_dependencies."""

    def test_all_resolved(self):
        registry = _make_registry_with_seedream()
        deps = [ModuleDependency(module_id="builtin.seedream.text-to-image", module_version="1.0.0")]
        all_resolved, result = resolve_dependencies(deps, registry)
        assert all_resolved is True
        assert all(d.found for d in result)
        assert all(d.required for d in result)

    def test_one_missing_module(self):
        registry = _make_registry_with_seedream()
        deps = [ModuleDependency(module_id="missing.module", module_version="1.0.0")]
        all_resolved, result = resolve_dependencies(deps, registry)
        assert all_resolved is False
        assert result[0].found is False

    def test_multiple_missing_modules(self):
        registry = _make_registry_with_seedream()
        deps = [
            ModuleDependency(module_id="missing.a", module_version="1.0.0"),
            ModuleDependency(module_id="missing.b", module_version="2.0.0"),
        ]
        all_resolved, result = resolve_dependencies(deps, registry)
        assert all_resolved is False
        assert all(not d.found for d in result)

    def test_mixed_resolved_and_missing(self):
        registry = _make_registry_with_seedream()
        deps = [
            ModuleDependency(module_id="builtin.seedream.text-to-image", module_version="1.0.0"),
            ModuleDependency(module_id="missing.module", module_version="1.0.0"),
        ]
        all_resolved, result = resolve_dependencies(deps, registry)
        assert all_resolved is False
        found_ids = {d.module_id for d in result if d.found}
        missing_ids = {d.module_id for d in result if not d.found}
        assert "builtin.seedream.text-to-image" in found_ids
        assert "missing.module" in missing_ids

    def test_empty_dependencies(self):
        registry = _make_registry_with_seedream()
        all_resolved, result = resolve_dependencies([], registry)
        assert all_resolved is True
        assert result == []

    def test_module_version_mismatch(self):
        """Module exists but at a different version."""
        registry = _make_registry_with_seedream()
        deps = [ModuleDependency(module_id="builtin.seedream.text-to-image", module_version="9.9.9")]
        all_resolved, result = resolve_dependencies(deps, registry)
        assert all_resolved is False
        assert result[0].found is False

    def test_resolve_uses_global_registry_when_none(self):
        """When registry is None, should use global singleton."""
        deps = [ModuleDependency(module_id="builtin.seedream.text-to-image", module_version="1.0.0")]
        all_resolved, result = resolve_dependencies(deps, None)
        assert all_resolved is True
        assert result[0].found is True


# ---------------------------------------------------------------------------
# Tests — create_degraded_workflow
# ---------------------------------------------------------------------------

class TestCreateDegradedWorkflow:
    """Tests for create_degraded_workflow."""

    def test_degraded_flag_set(self):
        spec = _make_workflow_spec(module_id="missing.module")
        unresolved = [ModuleDependency(module_id="missing.module", module_version="1.0.0", node_ids=["node-1"])]
        degraded = create_degraded_workflow(spec, unresolved)
        assert degraded["degraded"] is True

    def test_degraded_preserves_structure(self):
        spec = _make_workflow_spec(module_id="missing.module")
        original_nodes = list(spec["nodes"])
        unresolved = [ModuleDependency(module_id="missing.module", module_version="1.0.0", node_ids=["node-1"])]
        degraded = create_degraded_workflow(spec, unresolved)
        # Original nodes and edges preserved
        assert degraded["nodes"] == original_nodes
        assert degraded["edges"] == spec["edges"]
        assert degraded["id"] == spec["id"]
        assert degraded["name"] == spec["name"]

    def test_missing_modules_list(self):
        spec = _make_workflow_with_multiple_modules()
        unresolved = [
            ModuleDependency(module_id="nonexistent.module", module_version="2.0.0", node_ids=["n2"]),
        ]
        degraded = create_degraded_workflow(spec, unresolved)
        assert "missing_modules" in degraded
        assert len(degraded["missing_modules"]) == 1
        assert degraded["missing_modules"][0]["module_id"] == "nonexistent.module"
        assert degraded["missing_modules"][0]["node_ids"] == ["n2"]

    def test_degradation_reason_message(self):
        spec = _make_workflow_spec(module_id="missing.module")
        unresolved = [ModuleDependency(module_id="missing.module", module_version="1.0.0", node_ids=["node-1"])]
        degraded = create_degraded_workflow(spec, unresolved)
        reason = degraded["degradation_reason"]
        assert "missing.module@1.0.0" in reason
        assert "not found" in reason.lower()

    def test_status_is_degraded(self):
        spec = _make_workflow_spec(module_id="missing.module")
        unresolved = [ModuleDependency(module_id="missing.module", module_version="1.0.0", node_ids=["node-1"])]
        degraded = create_degraded_workflow(spec, unresolved)
        assert degraded["status"] == "degraded"


# ---------------------------------------------------------------------------
# Tests — Export with embedded modules
# ---------------------------------------------------------------------------

class TestExportEmbedsModules:
    """Verify that export embeds module definitions inline."""

    def test_export_includes_embedded_modules(self):
        """Export should add embeddedModules when nodes reference modules."""
        from backend.app.services.module_registry import ModuleRegistry
        registry = ModuleRegistry()
        module = registry.get_module("builtin.seedream.text-to-image")
        assert module is not None

        # Simulate what the API export does
        spec = _make_workflow_spec(
            module_id="builtin.seedream.text-to-image",
            node_id="n1",
        )
        deps = extract_module_dependencies(spec)
        module_definitions = []
        for dep in deps:
            m = registry.get_module(dep.module_id, dep.module_version or None)
            if m is not None:
                module_definitions.append(m.model_dump())

        if module_definitions:
            spec["embeddedModules"] = module_definitions

        assert "embeddedModules" in spec
        assert len(spec["embeddedModules"]) == 1
        assert spec["embeddedModules"][0]["id"] == "builtin.seedream.text-to-image"

    def test_export_no_embedded_when_no_modules(self):
        """Export should not add embeddedModules when no modules referenced."""
        registry = ModuleRegistry()
        spec = _make_workflow_spec()
        deps = extract_module_dependencies(spec)
        module_definitions = []
        for dep in deps:
            m = registry.get_module(dep.module_id, dep.module_version or None)
            if m is not None:
                module_definitions.append(m.model_dump())

        if module_definitions:
            spec["embeddedModules"] = module_definitions

        assert "embeddedModules" not in spec


# ---------------------------------------------------------------------------
# Tests — Import with module resolution
# ---------------------------------------------------------------------------

class TestImportModuleResolution:
    """Verify import detects missing modules and degrades."""

    def test_import_all_modules_present(self):
        """Import with all modules present should produce normal workflow."""
        spec = _make_workflow_spec(
            module_id="builtin.seedream.text-to-image",
            node_id="n1",
        )
        registry = _make_registry_with_seedream()
        deps = extract_module_dependencies(spec)
        all_resolved, deps_with_status = resolve_dependencies(deps, registry)
        assert all_resolved is True
        # No degradation needed
        assert not any(not d.found for d in deps_with_status)

    def test_import_with_missing_modules(self):
        """Import with missing modules should flag degradation."""
        spec = _make_workflow_with_multiple_modules()
        registry = _make_registry_with_seedream()
        deps = extract_module_dependencies(spec)
        all_resolved, deps_with_status = resolve_dependencies(deps, registry)
        assert all_resolved is False
        unresolved = [d for d in deps_with_status if not d.found]
        assert len(unresolved) == 1
        assert unresolved[0].module_id == "nonexistent.module"

        degraded = create_degraded_workflow(spec, unresolved)
        assert degraded["degraded"] is True
        assert degraded["status"] == "degraded"
