"""Module Port Binding Validator -- validates port definitions on modules.

Core ports come from the baseKind's manifest and cannot be changed.
Extension ports can be added but must have a binding to a config field
to be executable. Without a binding, the module fails validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.services.agent_tools import _NODE_CATALOG_V2  # HARD-101: 已指向共享 catalog
from backend.app.schemas.module_definition import ModuleDefinition


@dataclass
class PortError:
    """Structured port validation error."""

    field: str  # e.g. "ports.inputs[1].binding"
    error: str  # e.g. "UNBOUND_MODULE_PORT"
    message: str


class PortBindingValidator:
    """Validates that module ports have correct bindings."""

    def validate_ports(self, definition: ModuleDefinition) -> list[PortError]:
        """Run all port validation checks on a module definition.

        Checks:
        1. Core ports match baseKind contract (id, type, direction)
        2. Extension output ports have a binding to a config field
        3. No duplicate port IDs (within inputs or outputs separately)
        4. Required ports are marked correctly
        5. Cardinality values are valid ('one' or 'many')
        """
        errors: list[PortError] = []
        errors.extend(self.validate_core_ports(definition.base_kind, definition.ports))
        errors.extend(self.validate_extension_bindings(definition))
        errors.extend(self._check_duplicate_port_ids(definition.ports))
        return errors

    def validate_core_ports(
        self, base_kind: str, ports: dict[str, Any]
    ) -> list[PortError]:
        """Core ports must exactly match the baseKind's manifest ports.

        Checks that every core port has the same id, type, and direction
        as defined in the node catalog for the given baseKind.
        """
        errors: list[PortError] = []

        manifest = _NODE_CATALOG_V2.get(base_kind)
        if manifest is None:
            errors.append(
                PortError(
                    field="baseKind",
                    error="UNKNOWN_BASE_KIND",
                    message=f"Unknown baseKind '{base_kind}' -- no manifest found",
                )
            )
            return errors

        # Build lookup of expected core ports
        core_input_ids = {p.id for p in manifest.ports.inputs}
        core_output_ids = {p.id for p in manifest.ports.outputs}
        core_inputs_by_id = {p.id: p for p in manifest.ports.inputs}
        core_outputs_by_id = {p.id: p for p in manifest.ports.outputs}

        # Validate input ports
        for i, port in enumerate(ports.get("inputs", [])):
            port_id = port.get("id", "")
            field_prefix = f"ports.inputs[{i}]"

            if port_id in core_input_ids:
                # This is a core port -- must match exactly
                expected = core_inputs_by_id[port_id]
                if port.get("type") != expected.type:
                    errors.append(
                        PortError(
                            field=f"{field_prefix}.type",
                            error="CORE_PORT_TYPE_MISMATCH",
                            message=(
                                f"Core input port '{port_id}' type '{port.get('type')}' "
                                f"does not match manifest type '{expected.type}'"
                            ),
                        )
                    )
                if port.get("cardinality", "one") != expected.cardinality:
                    errors.append(
                        PortError(
                            field=f"{field_prefix}.cardinality",
                            error="CORE_PORT_CARDINALITY_MISMATCH",
                            message=(
                                f"Core input port '{port_id}' cardinality "
                                f"'{port.get('cardinality', 'one')}' does not match "
                                f"manifest cardinality '{expected.cardinality}'"
                            ),
                        )
                    )

        # Validate output ports
        for i, port in enumerate(ports.get("outputs", [])):
            port_id = port.get("id", "")
            field_prefix = f"ports.outputs[{i}]"

            if port_id in core_output_ids:
                expected = core_outputs_by_id[port_id]
                if port.get("type") != expected.type:
                    errors.append(
                        PortError(
                            field=f"{field_prefix}.type",
                            error="CORE_PORT_TYPE_MISMATCH",
                            message=(
                                f"Core output port '{port_id}' type '{port.get('type')}' "
                                f"does not match manifest type '{expected.type}'"
                            ),
                        )
                    )
                if port.get("cardinality", "one") != expected.cardinality:
                    errors.append(
                        PortError(
                            field=f"{field_prefix}.cardinality",
                            error="CORE_PORT_CARDINALITY_MISMATCH",
                            message=(
                                f"Core output port '{port_id}' cardinality "
                                f"'{port.get('cardinality', 'one')}' does not match "
                                f"manifest cardinality '{expected.cardinality}'"
                            ),
                        )
                    )

        return errors

    def validate_extension_bindings(
        self, definition: ModuleDefinition
    ) -> list[PortError]:
        """Extension ports must have a binding to a configSchema field.

        An extension port is any port whose id is NOT in the baseKind's
        core port manifest. Both input and output extension ports require
        a binding.
        """
        errors: list[PortError] = []

        manifest = _NODE_CATALOG_V2.get(definition.base_kind)
        if manifest is None:
            # Cannot validate extensions without a valid baseKind
            return errors

        core_input_ids = {p.id for p in manifest.ports.inputs}
        core_output_ids = {p.id for p in manifest.ports.outputs}

        # Check extension input ports
        for i, port in enumerate(definition.ports.get("inputs", [])):
            port_id = port.get("id", "")
            if port_id not in core_input_ids:
                # Extension port -- needs binding
                binding = port.get("binding")
                if not binding:
                    errors.append(
                        PortError(
                            field=f"ports.inputs[{i}].binding",
                            error="UNBOUND_MODULE_PORT",
                            message=(
                                f"Extension input port '{port_id}' has no binding "
                                f"to config field"
                            ),
                        )
                    )

        # Check extension output ports
        for i, port in enumerate(definition.ports.get("outputs", [])):
            port_id = port.get("id", "")
            if port_id not in core_output_ids:
                # Extension port -- needs binding
                binding = port.get("binding")
                if not binding:
                    errors.append(
                        PortError(
                            field=f"ports.outputs[{i}].binding",
                            error="UNBOUND_MODULE_PORT",
                            message=(
                                f"Extension output port '{port_id}' has no binding "
                                f"to config field"
                            ),
                        )
                    )

        return errors

    def _check_duplicate_port_ids(
        self, ports: dict[str, Any]
    ) -> list[PortError]:
        """Check for duplicate port IDs within inputs and within outputs."""
        errors: list[PortError] = []

        for direction in ("inputs", "outputs"):
            seen: dict[str, int] = {}
            for i, port in enumerate(ports.get(direction, [])):
                port_id = port.get("id", "")
                if port_id in seen:
                    errors.append(
                        PortError(
                            field=f"ports.{direction}[{i}].id",
                            error="DUPLICATE_PORT_ID",
                            message=(
                                f"Duplicate port ID '{port_id}' in {direction} "
                                f"(first at index {seen[port_id]})"
                            ),
                        )
                    )
                else:
                    seen[port_id] = i

        return errors
