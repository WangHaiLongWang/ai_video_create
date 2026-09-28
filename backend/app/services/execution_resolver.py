"""Execution Resolver — pre-execution module config resolution and validation.

Takes a compiled workflow spec and resolves module references (moduleId /
moduleVersion / configOverrides) on each node, merging them with the module's
defaultConfig via the ModuleRegistry.  Returns structured errors *before*
execution starts so that the API can return 400 instead of 500.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from backend.app.services.module_registry import (
    ModuleRegistry,
    get_module_registry,
)
from backend.app.services.module_port_validator import PortBindingValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class NodeResolution:
    """Resolved state for a single node in the workflow."""

    node_id: str
    node_kind: str
    resolved_config: dict[str, Any]
    module_id: str | None = None
    module_version: str | None = None


@dataclass
class ResolutionError:
    """A single validation error for a node."""

    node_id: str
    node_kind: str
    error_type: str  # "module_not_found", "version_mismatch", "kind_mismatch", "config_validation"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    """Outcome of resolving an entire workflow spec."""

    success: bool
    nodes: list[NodeResolution] = field(default_factory=list)
    errors: list[ResolutionError] = field(default_factory=list)

    @property
    def error_summary(self) -> str:
        parts = [f"[{e.error_type}] {e.node_id}: {e.message}" for e in self.errors]
        return "; ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Config schema validation
# ---------------------------------------------------------------------------


def _validate_config_schema(
    config: dict[str, Any],
    schema: dict[str, Any],
    node_id: str,
) -> list[str]:
    """Validate *config* against a JSON-schema-like *schema* dict.

    Supports ``required`` array and ``properties`` type checks.
    Returns a list of human-readable error strings (empty if valid).
    """
    errors: list[str] = []

    if not schema:
        return errors

    # Required fields
    required = schema.get("required", [])
    for field_name in required:
        if field_name not in config:
            errors.append(f"Missing required field '{field_name}'")

    # Type checks (basic)
    properties = schema.get("properties", {})
    for prop_name, prop_def in properties.items():
        if prop_name not in config:
            continue
        value = config[prop_name]
        expected_type = prop_def.get("type")
        if expected_type is None:
            continue
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(expected_type)
        if python_type and not isinstance(value, python_type):
            errors.append(
                f"Field '{prop_name}' expected type '{expected_type}', "
                f"got '{type(value).__name__}'"
            )

    return errors


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------


class ExecutionResolver:
    """Resolves module references in a workflow spec before execution."""

    def __init__(self, registry: ModuleRegistry | None = None) -> None:
        self._registry = registry or get_module_registry()

    def resolve_workflow(self, spec: dict) -> ResolutionResult:
        """Resolve all module references in a workflow spec.

        For each node in ``spec["nodes"]``:
        1. If the node has ``data.moduleId``, look up the module.
        2. Validate version, baseKind, and config schema.
        3. Merge defaultConfig + configOverrides.
        4. Produce a :class:`NodeResolution` with the effective config.

        Nodes *without* ``data.moduleId`` pass through unchanged (their existing
        ``data.config`` is used as-is).

        Returns a :class:`ResolutionResult` with either all resolved nodes or
        a list of errors.
        """
        nodes = spec.get("nodes", [])
        result = ResolutionResult(success=True)

        for node in nodes:
            node_id = node.get("id", "unknown")
            data = node.get("data", {})
            node_kind = data.get("kind", "unknown")

            module_id = data.get("moduleId") or data.get("module_id")
            module_version = data.get("moduleVersion") or data.get("module_version")
            config_overrides = data.get("configOverrides", data.get("config_overrides", {}))

            if not module_id:
                # No module reference — pass through existing config
                result.nodes.append(
                    NodeResolution(
                        node_id=node_id,
                        node_kind=node_kind,
                        resolved_config=dict(data.get("config", {})),
                    )
                )
                continue

            # --- Module-referenced node: validate & resolve ---

            # 1. Module existence
            module = self._registry.get_module(module_id, version=module_version)
            if module is None:
                # Distinguish version mismatch from not-found
                latest = self._registry.get_module(module_id)
                if latest is not None and module_version:
                    result.errors.append(
                        ResolutionError(
                            node_id=node_id,
                            node_kind=node_kind,
                            error_type="version_mismatch",
                            message=(
                                f"Module '{module_id}' exists but version "
                                f"'{module_version}' not found (latest: {latest.version})"
                            ),
                            details={
                                "module_id": module_id,
                                "requested_version": module_version,
                                "latest_version": latest.version,
                            },
                        )
                    )
                else:
                    result.errors.append(
                        ResolutionError(
                            node_id=node_id,
                            node_kind=node_kind,
                            error_type="module_not_found",
                            message=f"Module '{module_id}' not found in registry",
                            details={"module_id": module_id},
                        )
                    )
                continue

            # 2. baseKind match
            if module.base_kind != node_kind:
                result.errors.append(
                    ResolutionError(
                        node_id=node_id,
                        node_kind=node_kind,
                        error_type="kind_mismatch",
                        message=(
                            f"Node kind '{node_kind}' does not match module "
                            f"'{module_id}' baseKind '{module.base_kind}'"
                        ),
                        details={
                            "node_kind": node_kind,
                            "module_base_kind": module.base_kind,
                        },
                    )
                )
                continue

            # 2b. Port binding validation
            port_errors = PortBindingValidator().validate_ports(module)
            if port_errors:
                for pe in port_errors:
                    result.errors.append(
                        ResolutionError(
                            node_id=node_id,
                            node_kind=node_kind,
                            error_type="unbound_module_port",
                            message=pe.message,
                            details={
                                "module_id": module_id,
                                "field": pe.field,
                                "error_code": pe.error,
                            },
                        )
                    )
                continue

            # 3. Merge config: defaultConfig + configOverrides
            try:
                effective_config = self._registry.resolve_effective_config(
                    module_id,
                    instance_overrides=config_overrides or None,
                    version=module_version,
                )
            except KeyError as exc:
                # Should not happen since we just verified module exists
                result.errors.append(
                    ResolutionError(
                        node_id=node_id,
                        node_kind=node_kind,
                        error_type="module_not_found",
                        message=str(exc),
                        details={"module_id": module_id},
                    )
                )
                continue

            # 4. Validate against configSchema
            schema_errors = _validate_config_schema(
                effective_config, module.config_schema, node_id
            )
            if schema_errors:
                result.errors.append(
                    ResolutionError(
                        node_id=node_id,
                        node_kind=node_kind,
                        error_type="config_validation",
                        message="; ".join(schema_errors),
                        details={
                            "module_id": module_id,
                            "validation_errors": schema_errors,
                        },
                    )
                )
                continue

            # 5. Success — emit NodeResolution
            result.nodes.append(
                NodeResolution(
                    node_id=node_id,
                    node_kind=node_kind,
                    resolved_config=effective_config,
                    module_id=module_id,
                    module_version=module_version or module.version,
                )
            )

        # If any errors, mark as failed
        if result.errors:
            result.success = False
            logger.warning(
                f"ExecutionResolver: {len(result.errors)} error(s) "
                f"while resolving workflow '{spec.get('id', '?')}'"
            )

        return result


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def resolve_execution_config(spec: dict) -> ResolutionResult:
    """One-shot helper: resolve a workflow spec using the global registry."""
    return ExecutionResolver().resolve_workflow(spec)


def materialize_execution_spec(
    spec: dict,
    resolver: ExecutionResolver | None = None,
) -> tuple[dict, ResolutionResult]:
    """Return an immutable execution-ready copy with effective node configs.

    Module definitions remain referenced by exact id/version for auditability,
    while ``data.config`` is replaced with the resolver's effective config so
    the compiler, queue and handler all consume the same values.  The editable
    workflow input is never mutated.
    """
    active_resolver = resolver or ExecutionResolver()
    result = active_resolver.resolve_workflow(spec)
    materialized = deepcopy(spec)
    if not result.success:
        return materialized, result

    resolved_by_id = {node.node_id: node for node in result.nodes}
    for node in materialized.get("nodes", []):
        resolved = resolved_by_id.get(node.get("id"))
        if resolved is None:
            continue
        data = node.setdefault("data", {})
        data["config"] = deepcopy(resolved.resolved_config)
        if resolved.module_id:
            data["moduleId"] = resolved.module_id
            data["moduleVersion"] = resolved.module_version

    metadata = materialized.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        materialized["metadata"] = metadata
    metadata["modulesResolved"] = True
    metadata["resolvedModules"] = [
        {
            "nodeId": node.node_id,
            "moduleId": node.module_id,
            "moduleVersion": node.module_version,
        }
        for node in result.nodes
        if node.module_id
    ]
    return materialized, result
