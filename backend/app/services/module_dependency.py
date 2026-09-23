"""Module dependency resolver for workflow export/import.

When workflows are exported, they may reference module IDs.  When imported
into another system those modules might not exist.  This service detects
missing modules and produces degraded/read-only workflows so that the
structure is preserved but execution is blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.app.services.module_registry import ModuleRegistry


@dataclass
class ModuleDependency:
    """Describes one module reference found inside a workflow spec."""

    module_id: str
    module_version: str
    required: bool = True  # workflow cannot run without it
    found: bool = False    # whether the module exists in the current registry
    node_ids: list[str] = field(default_factory=list)


def extract_module_dependencies(workflow_spec: dict) -> list[ModuleDependency]:
    """Extract all module references from a workflow spec.

    Walks every node in ``workflow_spec["nodes"]`` and collects unique
    ``(module_id, module_version)`` pairs.  Nodes without ``module_id``
    in their ``data`` are silently skipped.
    """
    dep_map: dict[tuple[str, str], ModuleDependency] = {}

    for node in workflow_spec.get("nodes", []):
        data = node.get("data", {})
        module_id = data.get("module_id") or data.get("moduleId")
        if not module_id:
            continue
        module_version = data.get("module_version") or data.get("moduleVersion") or ""
        key = (module_id, module_version)
        if key not in dep_map:
            dep_map[key] = ModuleDependency(
                module_id=module_id,
                module_version=module_version,
            )
        dep_map[key].node_ids.append(node.get("id", ""))

    return list(dep_map.values())


def resolve_dependencies(
    dependencies: list[ModuleDependency],
    registry: Any | None = None,
) -> tuple[bool, list[ModuleDependency]]:
    """Check whether every dependency is satisfied by *registry*.

    Parameters
    ----------
    dependencies:
        Output of :func:`extract_module_dependencies`.
    registry:
        A :class:`ModuleRegistry` instance.  When *None* the global
        singleton is used.

    Returns
    -------
    (all_resolved, dependencies_with_status)
        *all_resolved* is ``True`` only when every dependency has
        ``found=True``.  The second element is the (mutated) list of
        ``ModuleDependency`` objects with ``found`` set accordingly and
        ``required`` set to ``True`` for all entries.
    """
    if registry is None:
        from backend.app.services.module_registry import get_module_registry

        registry = get_module_registry()

    all_resolved = True
    for dep in dependencies:
        dep.required = True
        module = registry.get_module(dep.module_id, dep.module_version or None)
        if module is not None:
            dep.found = True
        else:
            dep.found = False
            all_resolved = False

    return all_resolved, dependencies


def create_degraded_workflow(
    workflow_spec: dict,
    unresolved: list[ModuleDependency],
) -> dict:
    """Create a degraded/read-only version of the workflow.

    The returned spec is a shallow copy of *workflow_spec* with:
    * ``"degraded": True`` added at the top level
    * ``"missing_modules"`` list added with module-id/version pairs
    * ``"status": "degraded"`` added
    * ``"degradation_reason"`` human-readable string added
    """
    missing = [
        {"module_id": d.module_id, "module_version": d.module_version, "node_ids": d.node_ids}
        for d in unresolved
    ]
    missing_ids = [f"{d.module_id}@{d.module_version}" if d.module_version else d.module_id for d in unresolved]

    degraded = dict(workflow_spec)
    degraded["degraded"] = True
    degraded["status"] = "degraded"
    degraded["missing_modules"] = missing
    degraded["degradation_reason"] = (
        f"This workflow references modules not found in this system: [{', '.join(missing_ids)}]"
    )
    return degraded
