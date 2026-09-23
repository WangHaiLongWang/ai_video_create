"""Tests for Module Security Validator (MOD-204)."""

from __future__ import annotations

import json
import pytest

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.services.module_security import (
    SecurityViolation,
    validate_module_security,
    MAX_CONFIG_SIZE_BYTES,
    MAX_JSON_DEPTH,
    MAX_PORTS,
    MAX_FIELDS,
    MAX_LABEL_LENGTH,
    MAX_DESCRIPTION_LENGTH,
)
from backend.app.services.module_registry import ModuleRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_module(**overrides) -> ModuleDefinition:
    """Create a minimal valid module definition."""
    defaults = dict(
        id="test.secure-module",
        version="1.0.0",
        baseKind="textToImage",
        category="image",
        label="Secure Test Module",
        description="A module for testing security limits.",
        configSchema={
            "properties": {
                "model": {"type": "string", "title": "Model"},
                "size": {"type": "string", "title": "Size"},
            },
            "required": ["model"],
        },
        ports={
            "inputs": [
                {"id": "scene", "type": "scene", "required": True, "cardinality": "one", "label": "Scene"}
            ],
            "outputs": [
                {"id": "image", "type": "image", "required": False, "cardinality": "one", "label": "Image"}
            ],
        },
    )
    defaults.update(overrides)
    return ModuleDefinition(**defaults)


def _deep_schema(depth: int) -> dict:
    """Build a nested schema whose _json_depth equals the given depth.

    _json_depth counts the maximum nesting of dicts/lists.  Each
    ``{"properties": {"x": ...}}`` adds 2 levels (the properties dict + the
    named key dict), so we recurse with depth-2 and wrap with properties.
    """
    if depth <= 0:
        return {}
    if depth == 1:
        return {"type": "object"}
    return {"properties": {"level_0": _deep_schema(depth - 2)}}


def _large_schema_properties(count: int) -> dict:
    """Build a schema with many properties."""
    return {
        "properties": {f"field_{i}": {"type": "string", "title": f"Field {i}"} for i in range(count)}
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidModulePasses:
    """A well-formed module should pass security validation."""

    def test_valid_module_no_violations(self):
        module = _make_valid_module()
        violations = validate_module_security(module)
        assert violations == []

    def test_empty_module_no_violations(self):
        """Empty config/ports should still pass."""
        module = _make_valid_module(
            configSchema={},
            ports={"inputs": [], "outputs": []},
        )
        violations = validate_module_security(module)
        assert violations == []


class TestMaxConfigSize:
    """configSchema JSON must be under 64 KB."""

    def test_config_too_large(self):
        large_value = "x" * (MAX_CONFIG_SIZE_BYTES + 1000)
        module = _make_valid_module(
            configSchema={
                "properties": {
                    "blob": {"type": "string", "title": "Blob", "default": large_value}
                }
            }
        )
        violations = validate_module_security(module)
        assert any(v.rule == "MAX_CONFIG_SIZE" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_config_just_under_limit_passes(self):
        # ~63 KB of property names should be fine
        props = {f"field_{i:04d}": {"type": "string", "title": f"F{i}"} for i in range(500)}
        module = _make_valid_module(configSchema={"properties": props})
        violations = validate_module_security(module)
        assert not any(v.rule == "MAX_CONFIG_SIZE" for v in violations)


class TestMaxJsonDepth:
    """configSchema nesting must not exceed 5 levels."""

    def test_schema_too_deep(self):
        module = _make_valid_module(configSchema=_deep_schema(MAX_JSON_DEPTH + 2))
        violations = validate_module_security(module)
        assert any(v.rule == "MAX_JSON_DEPTH" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_schema_just_at_limit_passes(self):
        module = _make_valid_module(configSchema=_deep_schema(MAX_JSON_DEPTH))
        violations = validate_module_security(module)
        assert not any(v.rule == "MAX_JSON_DEPTH" for v in violations)


class TestMaxPorts:
    """Total ports (inputs + outputs) must not exceed 20."""

    def test_too_many_ports(self):
        inputs = [{"id": f"in_{i}", "type": "string", "required": False, "cardinality": "one", "label": f"In {i}"} for i in range(15)]
        outputs = [{"id": f"out_{i}", "type": "string", "required": False, "cardinality": "one", "label": f"Out {i}"} for i in range(10)]
        module = _make_valid_module(ports={"inputs": inputs, "outputs": outputs})
        violations = validate_module_security(module)
        assert any(v.rule == "MAX_PORTS" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_exactly_at_limit_passes(self):
        inputs = [{"id": f"in_{i}", "type": "string", "required": False, "cardinality": "one", "label": f"In {i}"} for i in range(10)]
        outputs = [{"id": f"out_{i}", "type": "string", "required": False, "cardinality": "one", "label": f"Out {i}"} for i in range(10)]
        module = _make_valid_module(ports={"inputs": inputs, "outputs": outputs})
        violations = validate_module_security(module)
        assert not any(v.rule == "MAX_PORTS" for v in violations)


class TestMaxFields:
    """configSchema properties must not exceed 50."""

    def test_too_many_fields(self):
        module = _make_valid_module(configSchema=_large_schema_properties(MAX_FIELDS + 10))
        violations = validate_module_security(module)
        assert any(v.rule == "MAX_FIELDS" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_exactly_at_limit_passes(self):
        module = _make_valid_module(configSchema=_large_schema_properties(MAX_FIELDS))
        violations = validate_module_security(module)
        assert not any(v.rule == "MAX_FIELDS" for v in violations)


class TestSecretRejection:
    """Field keys containing secret-related keywords must be rejected."""

    @pytest.mark.parametrize("keyword", ["key", "secret", "token", "password"])
    def test_secret_keyword_rejected(self, keyword: str):
        module = _make_valid_module(
            configSchema={"properties": {f"my_{keyword}_here": {"type": "string", "title": "Value"}}}
        )
        violations = validate_module_security(module)
        assert any(v.rule == "SECRET_REJECTION" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_nested_secret_rejected(self):
        module = _make_valid_module(
            configSchema={
                "properties": {
                    "auth": {
                        "type": "object",
                        "title": "Auth",
                        "properties": {
                            "api_key": {"type": "string", "title": "API Key"}
                        },
                    }
                }
            }
        )
        violations = validate_module_security(module)
        assert any(v.rule == "SECRET_REJECTION" for v in violations)

    def test_safe_keys_pass(self):
        module = _make_valid_module(
            configSchema={"properties": {"model": {"type": "string", "title": "Model"}}}
        )
        violations = validate_module_security(module)
        assert not any(v.rule == "SECRET_REJECTION" for v in violations)


class TestPortIdFormat:
    """Port IDs must be alphanumeric + underscore only."""

    def test_invalid_port_id_rejected(self):
        module = _make_valid_module(
            ports={
                "inputs": [{"id": "my-port!", "type": "string", "required": False, "cardinality": "one", "label": "Bad"}],
                "outputs": [],
            }
        )
        violations = validate_module_security(module)
        assert any(v.rule == "PORT_ID_FORMAT" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_hyphen_in_port_id_rejected(self):
        module = _make_valid_module(
            ports={
                "inputs": [{"id": "my-port", "type": "string", "required": False, "cardinality": "one", "label": "Bad"}],
                "outputs": [],
            }
        )
        violations = validate_module_security(module)
        assert any(v.rule == "PORT_ID_FORMAT" for v in violations)

    def test_valid_port_ids_pass(self):
        module = _make_valid_module(
            ports={
                "inputs": [{"id": "scene_1", "type": "scene", "required": True, "cardinality": "one", "label": "Scene"}],
                "outputs": [{"id": "image_out", "type": "image", "required": False, "cardinality": "one", "label": "Image"}],
            }
        )
        violations = validate_module_security(module)
        assert not any(v.rule == "PORT_ID_FORMAT" for v in violations)


class TestLabelLength:
    """Module label must not exceed 100 characters (warning)."""

    def test_label_too_long(self):
        module = _make_valid_module(label="A" * (MAX_LABEL_LENGTH + 1))
        violations = validate_module_security(module)
        assert any(v.rule == "LABEL_LENGTH" for v in violations)
        assert any(v.severity == "warning" for v in violations)

    def test_label_at_limit_passes(self):
        module = _make_valid_module(label="A" * MAX_LABEL_LENGTH)
        violations = validate_module_security(module)
        assert not any(v.rule == "LABEL_LENGTH" for v in violations)


class TestDescriptionLength:
    """Description must not exceed 500 characters (warning)."""

    def test_description_too_long(self):
        module = _make_valid_module(description="B" * (MAX_DESCRIPTION_LENGTH + 1))
        violations = validate_module_security(module)
        assert any(v.rule == "DESCRIPTION_LENGTH" for v in violations)
        assert any(v.severity == "warning" for v in violations)

    def test_description_at_limit_passes(self):
        module = _make_valid_module(description="B" * MAX_DESCRIPTION_LENGTH)
        violations = validate_module_security(module)
        assert not any(v.rule == "DESCRIPTION_LENGTH" for v in violations)


class TestNoExecutionInSchema:
    """Config schema titles must not contain eval/exec/import/require."""

    @pytest.mark.parametrize("keyword", ["eval", "exec", "import", "require"])
    def test_execution_keyword_rejected(self, keyword: str):
        module = _make_valid_module(
            configSchema={
                "properties": {
                    "cmd": {"type": "string", "title": f"Run {keyword} command"}
                }
            }
        )
        violations = validate_module_security(module)
        assert any(v.rule == "NO_EXECUTION_IN_SCHEMA" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_safe_titles_pass(self):
        module = _make_valid_module(
            configSchema={
                "properties": {
                    "model": {"type": "string", "title": "Model Name"},
                    "size": {"type": "string", "title": "Image Size"},
                }
            }
        )
        violations = validate_module_security(module)
        assert not any(v.rule == "NO_EXECUTION_IN_SCHEMA" for v in violations)


class TestProviderLockdown:
    """Locked provider policy must not have an empty allowed list."""

    def test_locked_empty_allowed_rejected(self):
        module = _make_valid_module(
            providerPolicy=ProviderPolicy(
                capability="image",
                allowed=[],
                default=None,
                locked=True,
            )
        )
        violations = validate_module_security(module)
        assert any(v.rule == "PROVIDER_LOCKDOWN" for v in violations)
        assert any(v.severity == "error" for v in violations)

    def test_locked_with_allowed_passes(self):
        module = _make_valid_module(
            providerPolicy=ProviderPolicy(
                capability="image",
                allowed=["doubao"],
                default="doubao",
                locked=True,
            )
        )
        violations = validate_module_security(module)
        assert not any(v.rule == "PROVIDER_LOCKDOWN" for v in violations)

    def test_unlocked_empty_allowed_passes(self):
        module = _make_valid_module(
            providerPolicy=ProviderPolicy(
                capability="image",
                allowed=[],
                locked=False,
            )
        )
        violations = validate_module_security(module)
        assert not any(v.rule == "PROVIDER_LOCKDOWN" for v in violations)


# ---------------------------------------------------------------------------
# Integration with ModuleRegistry
# ---------------------------------------------------------------------------


class TestRegistrySecurityIntegration:
    """Verify that ModuleRegistry.validate_module and publish respect security."""

    def test_validate_module_includes_security_violations(self):
        registry = ModuleRegistry()
        module = _make_valid_module(
            configSchema={"properties": {"my_secret": {"type": "string", "title": "Secret"}}}
        )
        errors = registry.validate_module(module)
        # Should include the SECRET_REJECTION error
        rule_names = [e["error"] for e in errors if isinstance(e, dict)]
        assert "SECRET_REJECTION" in rule_names

    def test_publish_rejects_security_errors(self):
        registry = ModuleRegistry()
        module = _make_valid_module(
            configSchema={"properties": {"my_token": {"type": "string", "title": "Token"}}}
        )
        success, errors = registry.publish(module)
        assert success is False
        rule_names = [e["error"] for e in errors if isinstance(e, dict)]
        assert "SECRET_REJECTION" in rule_names

    def test_publish_allows_warnings(self):
        """Warnings (label/description too long) should not block publish."""
        registry = ModuleRegistry()
        module = _make_valid_module(
            label="A" * (MAX_LABEL_LENGTH + 1),
            description="B" * (MAX_DESCRIPTION_LENGTH + 1),
        )
        success, errors = registry.publish(module)
        assert success is True
        # Warnings should still be in the response
        warning_rules = [e["error"] for e in errors if isinstance(e, dict) and e.get("severity") == "warning"]
        assert "LABEL_LENGTH" in warning_rules
        assert "DESCRIPTION_LENGTH" in warning_rules

    def test_builtin_module_passes_security(self):
        """The built-in Seedream module must pass security validation."""
        registry = ModuleRegistry()
        module = registry.get_module("builtin.seedream.text-to-image")
        assert module is not None
        violations = validate_module_security(module)
        errors = [v for v in violations if v.severity == "error"]
        assert errors == []


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_config_schema_passes(self):
        module = _make_valid_module(configSchema={})
        violations = validate_module_security(module)
        # No errors expected for empty schema
        assert not any(v.severity == "error" for v in violations)

    def test_multiple_violations_at_once(self):
        """A module can trigger multiple violations simultaneously."""
        module = _make_valid_module(
            label="A" * (MAX_LABEL_LENGTH + 1),
            description="B" * (MAX_DESCRIPTION_LENGTH + 1),
            configSchema={
                "properties": {
                    f"field_{i}": {"type": "string", "title": f"Field {i} Run eval"} for i in range(MAX_FIELDS + 5)
                }
            },
        )
        violations = validate_module_security(module)
        rules = {v.rule for v in violations}
        assert "LABEL_LENGTH" in rules
        assert "DESCRIPTION_LENGTH" in rules
        assert "MAX_FIELDS" in rules
        assert "NO_EXECUTION_IN_SCHEMA" in rules
