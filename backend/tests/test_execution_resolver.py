"""Tests for Execution Resolver — module config resolution and validation."""

from __future__ import annotations

import pytest
from typing import Any

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_registry import ModuleRegistry
from backend.app.services.execution_resolver import (
    ExecutionResolver,
    ResolutionResult,
    ResolutionError,
    NodeResolution,
    _validate_config_schema,
    resolve_execution_config,
    materialize_execution_spec,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seedream_module() -> ModuleDefinition:
    """Return the built-in Seedream module definition."""
    return ModuleDefinition(
        id="builtin.seedream.text-to-image",
        version="1.0.0",
        status="published",
        baseKind="textToImage",
        category="image",
        label="Seedream 文生图",
        description="Test module",
        icon="image",
        providerPolicy=ProviderPolicy(
            capability="image",
            allowed=["doubao"],
            default="doubao",
            locked=True,
        ),
        configSchema={
            "properties": {
                "image_model": {"type": "string", "title": "模型"},
                "size": {"type": "string", "title": "尺寸", "default": "1280x720"},
            },
            "required": ["image_model"],
        },
        defaultConfig={
            "provider": "doubao",
            "image_model": "doubao-seedream-5-0-pro-260628",
            "size": "1280x720",
        },
        ports={
            "inputs": [{"id": "scene", "type": "scene", "required": True, "cardinality": "one"}],
            "outputs": [{"id": "image", "type": "image", "required": False, "cardinality": "one"}],
        },
        execution=ExecutionHints(**{"mapOver": "scene"}),
    )


def _video_module() -> ModuleDefinition:
    """Return a second built-in module for multi-module tests."""
    return ModuleDefinition(
        id="builtin.test.image-to-video",
        version="1.0.0",
        status="published",
        baseKind="imageToVideo",
        category="video",
        label="Test I2V",
        description="Test video module",
        configSchema={
            "properties": {
                "model": {"type": "string"},
                "duration": {"type": "integer"},
            },
            "required": ["model"],
        },
        defaultConfig={
            "model": "test-model",
            "duration": 5,
        },
    )


def _make_registry(*modules: ModuleDefinition) -> ModuleRegistry:
    """Create a registry with specific modules."""
    registry = ModuleRegistry()
    # Override internal modules with custom ones
    registry._modules.clear()
    for mod in modules:
        # Resolver fixtures represent executable catalog entries. ModuleDefinition
        # defaults to draft for authoring, but execution only accepts published
        # immutable versions.
        mod = mod.model_copy(update={"status": "published"})
        registry._modules.setdefault(mod.id, {})[mod.version] = mod
    return registry


def _make_node(
    node_id: str,
    kind: str,
    config: dict | None = None,
    module_id: str | None = None,
    module_version: str | None = None,
    config_overrides: dict | None = None,
) -> dict:
    """Build a workflow node dict."""
    data: dict[str, Any] = {"kind": kind}
    if config is not None:
        data["config"] = config
    if module_id is not None:
        data["moduleId"] = module_id
    if module_version is not None:
        data["moduleVersion"] = module_version
    if config_overrides is not None:
        data["configOverrides"] = config_overrides
    return {"id": node_id, "data": data}


def _make_spec(nodes: list[dict], wf_id: str = "wf-test") -> dict:
    """Build a minimal workflow spec dict."""
    return {"id": wf_id, "name": "Test Workflow", "nodes": nodes, "edges": []}


# ---------------------------------------------------------------------------
# Tests: Module found and config merged correctly
# ---------------------------------------------------------------------------


class TestResolveModuleFound:
    """Node with moduleId — module found, config merged."""

    def test_module_found_config_merged(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            config_overrides={"size": "1920x1080"},
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert len(result.nodes) == 1
        nr = result.nodes[0]
        assert nr.node_id == "n1"
        assert nr.module_id == "builtin.seedream.text-to-image"
        assert nr.module_version == "1.0.0"
        # Overrides applied on top of defaults
        assert nr.resolved_config["size"] == "1920x1080"
        # Defaults still present
        assert nr.resolved_config["provider"] == "doubao"
        assert nr.resolved_config["image_model"] == "doubao-seedream-5-0-pro-260628"

    def test_module_found_no_overrides(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        nr = result.nodes[0]
        assert nr.resolved_config["image_model"] == "doubao-seedream-5-0-pro-260628"
        assert nr.resolved_config["size"] == "1280x720"

    def test_module_version_inferred_when_not_specified(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            # no module_version
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].module_version == "1.0.0"


# ---------------------------------------------------------------------------
# Tests: Module not found
# ---------------------------------------------------------------------------


class TestResolveModuleNotFound:
    """Node with moduleId that does not exist in registry."""

    def test_module_not_found(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="nonexistent.module",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.error_type == "module_not_found"
        assert "nonexistent.module" in err.message
        assert err.node_id == "n1"


# ---------------------------------------------------------------------------
# Tests: Version mismatch
# ---------------------------------------------------------------------------


class TestResolveVersionMismatch:
    """Node with moduleId that exists but at a different version."""

    def test_version_mismatch(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="9.9.9",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.error_type == "version_mismatch"
        assert "9.9.9" in err.message
        assert "1.0.0" in err.message
        assert err.details["latest_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Tests: baseKind mismatch
# ---------------------------------------------------------------------------


class TestResolveKindMismatch:
    """Node kind does not match the module's baseKind."""

    def test_kind_mismatch(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        # Node kind is "imageToVideo" but module baseKind is "textToImage"
        node = _make_node(
            "n1", "imageToVideo",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.error_type == "kind_mismatch"
        assert "imageToVideo" in err.message
        assert "textToImage" in err.message
        assert err.details["module_base_kind"] == "textToImage"


# ---------------------------------------------------------------------------
# Tests: Config validation fails
# ---------------------------------------------------------------------------


class TestResolveConfigValidation:
    """Config does not pass the module's configSchema validation."""

    def test_required_field_missing(self):
        """Remove image_model (required) from effective config."""
        # Create a module where required field is not in defaults
        mod = ModuleDefinition(
            id="test.missing-required",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test",
            configSchema={
                "properties": {
                    "api_key": {"type": "string"},
                },
                "required": ["api_key"],
            },
            defaultConfig={
                # api_key is NOT in defaults — so merge won't supply it
            },
        )
        registry = _make_registry(mod)
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="test.missing-required",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        assert len(result.errors) == 1
        err = result.errors[0]
        assert err.error_type == "config_validation"
        assert "api_key" in err.message
        assert "Missing required field" in err.message

    def test_wrong_type_rejected(self):
        """Config field has wrong type per schema."""
        mod = ModuleDefinition(
            id="test.wrong-type",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test",
            configSchema={
                "properties": {
                    "count": {"type": "integer"},
                },
                "required": [],
            },
            defaultConfig={"count": 5},
        )
        registry = _make_registry(mod)
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="test.wrong-type",
            module_version="1.0.0",
            config_overrides={"count": "not-an-int"},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        err = result.errors[0]
        assert err.error_type == "config_validation"
        assert "count" in err.message
        assert "integer" in err.message


# ---------------------------------------------------------------------------
# Tests: Nodes without moduleId pass through
# ---------------------------------------------------------------------------


class TestResolvePassThrough:
    """Nodes without moduleId are passed through unchanged."""

    def test_no_module_id_passthrough(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node("n1", "textInput", config={"prompt": "hello"})
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert len(result.nodes) == 1
        nr = result.nodes[0]
        assert nr.module_id is None
        assert nr.resolved_config == {"prompt": "hello"}

    def test_empty_config_passthrough(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node("n1", "output")
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].resolved_config == {}


# ---------------------------------------------------------------------------
# Tests: defaultConfig + configOverrides merge
# ---------------------------------------------------------------------------


class TestConfigMerge:
    """Verify defaultConfig + configOverrides merge semantics."""

    def test_override_replaces_default(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides={"image_model": "custom-model"},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].resolved_config["image_model"] == "custom-model"
        # Other defaults preserved
        assert result.nodes[0].resolved_config["provider"] == "doubao"

    def test_empty_overrides_preserves_defaults(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides={},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].resolved_config == {
            "provider": "doubao",
            "image_model": "doubao-seedream-5-0-pro-260628",
            "size": "1280x720",
        }


# ---------------------------------------------------------------------------
# Tests: Required fields validation (edge cases)
# ---------------------------------------------------------------------------


class TestRequiredFieldsEdgeCases:
    """Edge cases for required field validation."""

    def test_required_field_provided_via_override(self):
        """Required field provided through configOverrides."""
        mod = ModuleDefinition(
            id="test.override-required",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test",
            configSchema={
                "properties": {"api_key": {"type": "string"}},
                "required": ["api_key"],
            },
            defaultConfig={"size": "1280x720"},
        )
        registry = _make_registry(mod)
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="test.override-required",
            module_version="1.0.0",
            config_overrides={"api_key": "sk-abc123"},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].resolved_config["api_key"] == "sk-abc123"

    def test_empty_schema_always_validates(self):
        """Module with no configSchema always passes validation."""
        mod = ModuleDefinition(
            id="test.no-schema",
            version="1.0.0",
            baseKind="textToImage",
            category="image",
            label="Test",
            configSchema={},
            defaultConfig={"any": "thing"},
        )
        registry = _make_registry(mod)
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="test.no-schema",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True


# ---------------------------------------------------------------------------
# Tests: Empty config overrides
# ---------------------------------------------------------------------------


class TestEmptyOverrides:
    """configOverrides=None or {} should not break resolution."""

    def test_none_overrides(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides=None,
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert result.nodes[0].resolved_config["image_model"] == "doubao-seedream-5-0-pro-260628"


# ---------------------------------------------------------------------------
# Tests: Multiple module nodes
# ---------------------------------------------------------------------------


class TestMultipleModules:
    """Workflow with multiple module-referenced nodes."""

    def test_two_modules_both_resolve(self):
        seedream = _seedream_module()
        i2v = _video_module()
        registry = _make_registry(seedream, i2v)
        resolver = ExecutionResolver(registry)

        nodes = [
            _make_node(
                "n1", "textToImage",
                module_id="builtin.seedream.text-to-image",
                module_version="1.0.0",
                config_overrides={"size": "1024x768"},
            ),
            _make_node(
                "n2", "imageToVideo",
                module_id="builtin.test.image-to-video",
                module_version="1.0.0",
                config_overrides={"duration": 10},
            ),
        ]
        spec = _make_spec(nodes)
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert len(result.nodes) == 2
        n1 = next(n for n in result.nodes if n.node_id == "n1")
        n2 = next(n for n in result.nodes if n.node_id == "n2")
        assert n1.resolved_config["size"] == "1024x768"
        assert n1.resolved_config["provider"] == "doubao"
        assert n2.resolved_config["duration"] == 10
        assert n2.resolved_config["model"] == "test-model"

    def test_one_module_fails_others_still_resolved(self):
        """When one module fails validation, errors are returned but
        the successful node is still in the result.nodes list."""
        seedream = _seedream_module()
        registry = _make_registry(seedream)
        resolver = ExecutionResolver(registry)

        nodes = [
            _make_node(
                "n1", "textToImage",
                module_id="builtin.seedream.text-to-image",
                module_version="1.0.0",
            ),
            _make_node(
                "n2", "textToImage",
                module_id="nonexistent.module",
            ),
        ]
        spec = _make_spec(nodes)
        result = resolver.resolve_workflow(spec)

        assert result.success is False
        # n1 resolved successfully
        assert len(result.nodes) == 1
        assert result.nodes[0].node_id == "n1"
        # n2 failed
        assert len(result.errors) == 1
        assert result.errors[0].node_id == "n2"


# ---------------------------------------------------------------------------
# Tests: ExecutionSnapshot contains resolved config
# ---------------------------------------------------------------------------


class TestNodeResolution:
    """Verify NodeResolution dataclass fields are populated."""

    def test_snapshot_fields(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides={"seed": 42},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        nr = result.nodes[0]
        assert nr.node_id == "n1"
        assert nr.node_kind == "textToImage"
        assert nr.module_id == "builtin.seedream.text-to-image"
        assert nr.module_version == "1.0.0"
        assert nr.resolved_config["seed"] == 42
        assert nr.resolved_config["image_model"] == "doubao-seedream-5-0-pro-260628"

    def test_snapshot_for_no_module_node(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        node = _make_node("n1", "textInput", config={"prompt": "hi"})
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        nr = result.nodes[0]
        assert nr.node_id == "n1"
        assert nr.module_id is None
        assert nr.module_version is None
        assert nr.resolved_config == {"prompt": "hi"}


# ---------------------------------------------------------------------------
# Tests: Error summary
# ---------------------------------------------------------------------------


class TestErrorSummary:
    """ResolutionResult.error_summary formatting."""

    def test_error_summary_multiple(self):
        err1 = ResolutionError(
            node_id="n1", node_kind="textToImage",
            error_type="module_not_found", message="Module 'a' not found",
        )
        err2 = ResolutionError(
            node_id="n2", node_kind="imageToVideo",
            error_type="version_mismatch", message="Version mismatch",
        )
        res = ResolutionResult(success=False, errors=[err1, err2])
        summary = res.error_summary
        assert "n1" in summary
        assert "n2" in summary
        assert "module_not_found" in summary
        assert "version_mismatch" in summary

    def test_error_summary_empty(self):
        res = ResolutionResult(success=True)
        assert res.error_summary == ""


# ---------------------------------------------------------------------------
# Tests: resolve_execution_config convenience function
# ---------------------------------------------------------------------------


class TestResolveExecutionConfig:
    """Test the module-level convenience function."""

    def test_convenience_function(self):
        spec = _make_spec([
            _make_node("n1", "textInput", config={"prompt": "hello"}),
        ])
        result = resolve_execution_config(spec)
        assert result.success is True
        assert len(result.nodes) == 1


class TestMaterializeExecutionSpec:
    """Effective module config must reach the compiler without mutating draft."""

    def test_materializes_defaults_and_overrides(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)
        original = _make_spec([
            _make_node(
                "n1",
                "textToImage",
                module_id="builtin.seedream.text-to-image",
                module_version="1.0.0",
                config={"legacy": "draft-only"},
                config_overrides={"size": "1920x1080", "seed": 42},
            ),
        ])

        materialized, result = materialize_execution_spec(original, resolver)

        assert result.success is True
        config = materialized["nodes"][0]["data"]["config"]
        assert config["provider"] == "doubao"
        assert config["size"] == "1920x1080"
        assert config["seed"] == 42
        assert "legacy" not in config
        assert materialized["metadata"]["modulesResolved"] is True
        assert original["nodes"][0]["data"]["config"] == {"legacy": "draft-only"}

    def test_compiler_receives_effective_config(self):
        from backend.app.engine.compiler import compile_workflow

        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)
        node = _make_node(
            "n1",
            "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides={"size": "1024x1024", "seed": 7},
        )
        # Keep this a non-map compiler assertion; map behavior is covered by
        # compiler/scheduler integration tests.
        node["data"]["configOverrides"]["mapOver"] = False
        materialized, result = materialize_execution_spec(
            _make_spec([node]), resolver
        )

        assert result.success is True
        plan = compile_workflow(materialized)
        assert plan.tasks[0].config["provider"] == "doubao"
        assert plan.tasks[0].config["size"] == "1024x1024"
        assert plan.tasks[0].config["seed"] == 7

    def test_invalid_module_returns_unmodified_copy(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)
        original = _make_spec([
            _make_node("n1", "textToImage", module_id="missing.module"),
        ])

        materialized, result = materialize_execution_spec(original, resolver)

        assert result.success is False
        assert materialized == original


# ---------------------------------------------------------------------------
# Tests: Empty workflow
# ---------------------------------------------------------------------------


class TestEmptyWorkflow:
    """Workflow with no nodes resolves successfully."""

    def test_empty_nodes(self):
        spec = _make_spec([])
        result = resolve_execution_config(spec)
        assert result.success is True
        assert len(result.nodes) == 0


# ---------------------------------------------------------------------------
# Tests: Mixed module and non-module nodes
# ---------------------------------------------------------------------------


class TestMixedNodes:
    """Workflow mixing module-referenced and plain nodes."""

    def test_mixed_passthrough_and_module(self):
        registry = _make_registry(_seedream_module())
        resolver = ExecutionResolver(registry)

        nodes = [
            _make_node("n1", "textInput", config={"prompt": "hello"}),
            _make_node(
                "n2", "textToImage",
                module_id="builtin.seedream.text-to-image",
                module_version="1.0.0",
            ),
            _make_node("n3", "output"),
        ]
        spec = _make_spec(nodes)
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        assert len(result.nodes) == 3
        by_id = {n.node_id: n for n in result.nodes}
        assert by_id["n1"].module_id is None
        assert by_id["n2"].module_id == "builtin.seedream.text-to-image"
        assert by_id["n3"].module_id is None


# ---------------------------------------------------------------------------
# Tests: Config schema validation helper
# ---------------------------------------------------------------------------


class TestValidateConfigSchema:
    """Direct tests for _validate_config_schema helper."""

    def test_valid_config(self):
        schema = {"properties": {"x": {"type": "integer"}}, "required": ["x"]}
        errors = _validate_config_schema({"x": 5}, schema, "n1")
        assert errors == []

    def test_missing_required(self):
        schema = {"properties": {"x": {"type": "integer"}}, "required": ["x"]}
        errors = _validate_config_schema({}, schema, "n1")
        assert len(errors) == 1
        assert "x" in errors[0]

    def test_wrong_type(self):
        schema = {"properties": {"x": {"type": "integer"}}}
        errors = _validate_config_schema({"x": "oops"}, schema, "n1")
        assert len(errors) == 1
        assert "integer" in errors[0]

    def test_empty_schema_no_errors(self):
        errors = _validate_config_schema({"anything": 1}, {}, "n1")
        assert errors == []

    def test_optional_field_absent_no_error(self):
        schema = {"properties": {"x": {"type": "integer"}}, "required": []}
        errors = _validate_config_schema({}, schema, "n1")
        assert errors == []

    def test_boolean_type_check(self):
        schema = {"properties": {"flag": {"type": "boolean"}}}
        errors = _validate_config_schema({"flag": "yes"}, schema, "n1")
        assert len(errors) == 1
        assert "boolean" in errors[0]

    def test_multiple_required_fields(self):
        schema = {"required": ["a", "b", "c"]}
        errors = _validate_config_schema({"a": 1}, schema, "n1")
        assert len(errors) == 2
        field_names = " ".join(errors)
        assert "b" in field_names
        assert "c" in field_names


# ---------------------------------------------------------------------------
# Tests: Integration with real builtin modules
# ---------------------------------------------------------------------------


class TestWithBuiltinModules:
    """Tests using the real BUILTIN_MODULES registry."""

    def test_seedream_module_resolves_with_real_registry(self):
        from backend.app.services.module_registry import get_module_registry
        registry = get_module_registry()
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        nr = result.nodes[0]
        assert nr.resolved_config["image_model"] == "doubao-seedream-5-0-pro-260628"
        assert nr.resolved_config["provider"] == "doubao"
        assert nr.resolved_config["size"] == "1280x720"

    def test_seedream_module_with_overrides_resolves(self):
        from backend.app.services.module_registry import get_module_registry
        registry = get_module_registry()
        resolver = ExecutionResolver(registry)

        node = _make_node(
            "n1", "textToImage",
            module_id="builtin.seedream.text-to-image",
            module_version="1.0.0",
            config_overrides={"size": "720x480", "seed": 123},
        )
        spec = _make_spec([node])
        result = resolver.resolve_workflow(spec)

        assert result.success is True
        nr = result.nodes[0]
        assert nr.resolved_config["size"] == "720x480"
        assert nr.resolved_config["seed"] == 123
        assert nr.resolved_config["provider"] == "doubao"
