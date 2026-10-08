"""Tests for Module Port Binding Validator."""

from __future__ import annotations

import pytest

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_port_validator import PortBindingValidator, PortError
from backend.app.services.module_registry import ModuleRegistry, BUILTIN_MODULES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(
    base_kind: str = "textToImage",
    ports: dict | None = None,
    **kwargs,
) -> ModuleDefinition:
    """Create a minimal ModuleDefinition for testing."""
    if ports is None:
        ports = {"inputs": [], "outputs": []}
    defaults = dict(
        id="test.module",
        version="1.0.0",
        baseKind=base_kind,
        category="image",
        label="Test Module",
        ports=ports,
    )
    defaults.update(kwargs)
    return ModuleDefinition(**defaults)


# ---------------------------------------------------------------------------
# 1. Valid module passes validation
# ---------------------------------------------------------------------------


class TestValidModule:
    def test_valid_module_passes(self):
        """A module with correct core ports and no extensions passes."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        assert errors == []


# ---------------------------------------------------------------------------
# 2. Core port ID mismatch
# ---------------------------------------------------------------------------


class TestCorePortIdMismatch:
    def test_core_input_port_id_mismatch(self):
        """Core port with wrong ID produces error."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "wrong_id", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        # wrong_id is not a core port for textToImage, so it's an extension
        # and needs a binding -- no CORE_PORT mismatch, but UNBOUND_EXTENSION
        errors = PortBindingValidator().validate_ports(module)
        # The validator treats "wrong_id" as an extension (not in core), so no core error
        # but it IS an extension port without binding
        assert any(e.error == "UNBOUND_MODULE_PORT" for e in errors)


# ---------------------------------------------------------------------------
# 3. Core port type mismatch
# ---------------------------------------------------------------------------


class TestCorePortTypeMismatch:
    def test_core_input_type_mismatch(self):
        """Core port with wrong type produces CORE_PORT_TYPE_MISMATCH."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "video", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        type_errors = [e for e in errors if e.error == "CORE_PORT_TYPE_MISMATCH"]
        assert len(type_errors) == 1
        assert "scene" in type_errors[0].message
        assert type_errors[0].field == "ports.inputs[0].type"


# ---------------------------------------------------------------------------
# 4. Core port direction mismatch (output port given as input)
# ---------------------------------------------------------------------------


class TestCorePortDirectionMismatch:
    def test_output_port_wrong_direction(self):
        """If an output port id is placed in inputs, it's an extension (not core)
        and will need a binding."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        # "image" in inputs is NOT a core input for textToImage, so it's an extension
        # needing binding
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert any("image" in e.message for e in unbound)


# ---------------------------------------------------------------------------
# 5. Extension port without binding -> UNBOUND_MODULE_PORT
# ---------------------------------------------------------------------------


class TestExtensionPortWithoutBinding:
    def test_extension_input_without_binding(self):
        """Extension input port without binding triggers UNBOUND_MODULE_PORT."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "reference_image", "type": "image", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert len(unbound) == 1
        assert "reference_image" in unbound[0].message
        assert unbound[0].field == "ports.inputs[1].binding"

    def test_extension_output_without_binding(self):
        """Extension output port without binding triggers UNBOUND_MODULE_PORT."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"},
                    {"id": "thumbnail", "type": "image", "required": False, "cardinality": "one"},
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert len(unbound) == 1
        assert "thumbnail" in unbound[0].message
        assert unbound[0].field == "ports.outputs[1].binding"


# ---------------------------------------------------------------------------
# 6. Extension port with valid binding -> passes
# ---------------------------------------------------------------------------


class TestExtensionPortWithBinding:
    def test_extension_input_with_binding_passes(self):
        """Extension input port with a binding to config field passes."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "reference_image", "type": "image", "required": False,
                     "cardinality": "one", "binding": "ref_image_url"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert unbound == []

    def test_extension_output_with_binding_passes(self):
        """Extension output port with a binding passes."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"},
                    {"id": "thumbnail", "type": "image", "required": False,
                     "cardinality": "one", "binding": "output_thumbnail"},
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert unbound == []


# ---------------------------------------------------------------------------
# 7. Duplicate port IDs
# ---------------------------------------------------------------------------


class TestDuplicatePortIds:
    def test_duplicate_input_port_ids(self):
        """Duplicate port IDs within inputs produce DUPLICATE_PORT_ID error."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "scene", "type": "scene", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        dup = [e for e in errors if e.error == "DUPLICATE_PORT_ID"]
        assert len(dup) == 1
        assert "scene" in dup[0].message

    def test_duplicate_output_port_ids(self):
        """Duplicate port IDs within outputs produce DUPLICATE_PORT_ID error."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"},
                    {"id": "image", "type": "image", "required": False, "cardinality": "one"},
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        dup = [e for e in errors if e.error == "DUPLICATE_PORT_ID"]
        assert len(dup) == 1


# ---------------------------------------------------------------------------
# 8. Invalid cardinality
# ---------------------------------------------------------------------------


class TestInvalidCardinality:
    def test_invalid_cardinality_value(self):
        """Invalid cardinality is caught by Pydantic validation on PortDefinition,
        but the raw dict port with wrong cardinality won't match manifest."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "invalid"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        # The cardinality mismatch is caught
        cardinality_errors = [e for e in errors if "cardinality" in e.error.lower()]
        assert len(cardinality_errors) >= 1


# ---------------------------------------------------------------------------
# 9. Empty ports -> passes
# ---------------------------------------------------------------------------


class TestEmptyPorts:
    def test_empty_ports_passes(self):
        """Module with no extension ports passes validation."""
        module = _make_module(
            ports={"inputs": [], "outputs": []}
        )
        errors = PortBindingValidator().validate_ports(module)
        assert errors == []


# ---------------------------------------------------------------------------
# 10. Multiple extension ports, some unbound
# ---------------------------------------------------------------------------


class TestMultipleExtensionPorts:
    def test_some_bound_some_unbound(self):
        """Multiple extension ports with mixed binding status."""
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "ref_img", "type": "image", "required": False,
                     "cardinality": "one", "binding": "ref_url"},
                    {"id": "mask", "type": "image", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"},
                    {"id": "debug", "type": "any", "required": False,
                     "cardinality": "one", "binding": "debug_output"},
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        unbound = [e for e in errors if e.error == "UNBOUND_MODULE_PORT"]
        assert len(unbound) == 1
        assert "mask" in unbound[0].message


# ---------------------------------------------------------------------------
# 11. textToImage core ports
# ---------------------------------------------------------------------------


class TestTextToImageCorePorts:
    def test_textToImage_has_correct_core_ports(self):
        """textToImage core ports: input scene, output image."""
        module = _make_module(
            base_kind="textToImage",
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        assert errors == []


# ---------------------------------------------------------------------------
# 12. imageToVideo core ports
# ---------------------------------------------------------------------------


class TestImageToVideoCorePorts:
    def test_imageToVideo_has_correct_core_ports(self):
        """imageToVideo core ports: input image, output video (one).

        Canonical contract is the frontend node-manifest (MOD-R3-002 drift fix).
        """
        module = _make_module(
            base_kind="imageToVideo",
            ports={
                "inputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "video", "type": "video", "required": True, "cardinality": "one"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        assert errors == []

    def test_imageToVideo_wrong_cardinality_fails(self):
        """imageToVideo output 'video' must have cardinality 'one'."""
        module = _make_module(
            base_kind="imageToVideo",
            ports={
                "inputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "video", "type": "video", "required": True, "cardinality": "many"}
                ],
            }
        )
        errors = PortBindingValidator().validate_ports(module)
        card_errors = [e for e in errors if "CARDINALITY" in e.error]
        assert len(card_errors) == 1


# ---------------------------------------------------------------------------
# 13. publish() rejects module with binding errors
# ---------------------------------------------------------------------------


class TestPublishRejectsBindingErrors:
    def test_publish_rejects_unbound_ports(self):
        """publish() returns False when module has unbound extension ports."""
        registry = ModuleRegistry()
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "extra_input", "type": "text", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        success, errors = registry.publish(module)
        assert success is False
        assert any(
            isinstance(e, dict) and e.get("error") == "UNBOUND_MODULE_PORT"
            for e in errors
        )

    def test_publish_accepts_valid_module(self):
        """publish() returns True for a valid module with no binding errors."""
        registry = ModuleRegistry()
        module = _make_module(
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        success, errors = registry.publish(module)
        assert success is True
        assert errors == []


# ---------------------------------------------------------------------------
# 14. Execution resolver rejects unbound ports
# ---------------------------------------------------------------------------


class TestExecutionResolverRejectsUnboundPorts:
    def test_resolver_rejects_unbound_extension(self):
        """ExecutionResolver returns UNBOUND_MODULE_PORT error for unbound extension."""
        from backend.app.services.execution_resolver import ExecutionResolver

        registry = ModuleRegistry()
        # Register a module with an unbound extension port directly into the registry
        module = _make_module(
            id="test.unbound",
            status="published",
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "extra", "type": "text", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            }
        )
        # Manually insert into registry _modules (bypassing publish which would reject)
        registry._modules.setdefault(module.id, {})[module.version] = module

        resolver = ExecutionResolver(registry=registry)
        spec = {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "kind": "textToImage",
                        "moduleId": "test.unbound",
                        "moduleVersion": "1.0.0",
                        "configOverrides": {},
                    },
                }
            ]
        }
        result = resolver.resolve_workflow(spec)
        assert result.success is False
        assert any(
            e.error_type == "unbound_module_port" for e in result.errors
        )

    def test_resolver_passes_valid_module(self):
        """ExecutionResolver resolves successfully when ports are valid."""
        from backend.app.services.execution_resolver import ExecutionResolver

        registry = ModuleRegistry()
        module = _make_module(
            id="test.bound",
            status="published",
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"}
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": True, "cardinality": "one"}
                ],
            },
        )
        registry._modules.setdefault(module.id, {})[module.version] = module

        resolver = ExecutionResolver(registry=registry)
        spec = {
            "nodes": [
                {
                    "id": "node1",
                    "data": {
                        "kind": "textToImage",
                        "moduleId": "test.bound",
                        "moduleVersion": "1.0.0",
                        "configOverrides": {},
                    },
                }
            ]
        }
        result = resolver.resolve_workflow(spec)
        assert result.success is True
        assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# 15. Builtin modules pass validation
# ---------------------------------------------------------------------------


class TestBuiltinModulesPassValidation:
    def test_seedream_passes_validation(self):
        """The Seedream builtin module passes port validation."""
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        errors = PortBindingValidator().validate_ports(module)
        assert errors == []

    def test_seedream_passes_registry_validate(self):
        """The Seedream builtin module passes full registry validation."""
        registry = ModuleRegistry()
        module = BUILTIN_MODULES["builtin.seedream.text-to-image"]
        errors = registry.validate_module(module)
        # No errors expected for the builtin
        port_errors = [e for e in errors if isinstance(e, dict)]
        assert port_errors == []
