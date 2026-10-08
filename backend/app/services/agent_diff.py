"""Agent diff helpers — GraphPatch diffing, destructive checks, module diffs.

Shared by the v1 Agent API (``backend/app/api/agent.py``) and the v2 Agent API
(``backend/app/api/agent_v2.py``) so the human-readable wording stays identical.
"""

from __future__ import annotations

import copy
from typing import Any

from backend.app.models import GraphPatch, NodeUpdate, WorkflowEdge, WorkflowNode


# ---------------------------------------------------------------------------
# Human-readable diff / destructive warnings (wording shared with v1)
# ---------------------------------------------------------------------------


def generate_diff(spec: Any, patch: GraphPatch) -> str:
    """Generate a human-readable diff summary for a GraphPatch."""
    lines: list[str] = []
    if patch.add_nodes:
        lines.append(f"+ 新增 {len(patch.add_nodes)} 个节点: "
                     f"{', '.join(n.data.label for n in patch.add_nodes)}")
    if patch.remove_nodes:
        lines.append(f"- 删除 {len(patch.remove_nodes)} 个节点: "
                     f"{', '.join(patch.remove_nodes)}")
    if patch.update_nodes:
        lines.append(f"~ 更新 {len(patch.update_nodes)} 个节点: "
                     f"{', '.join(u.id for u in patch.update_nodes)}")
    if patch.add_edges:
        lines.append(f"+ 新增 {len(patch.add_edges)} 条连线")
    if patch.remove_edges:
        lines.append(f"- 删除 {len(patch.remove_edges)} 条连线")
    if not lines:
        lines.append("(无变更)")
    return "\n".join(lines)


def check_destructive(patch: GraphPatch) -> list[str]:
    """Return warnings for destructive operations in a patch."""
    warnings: list[str] = []
    if patch.remove_nodes:
        warnings.append(f"将删除 {len(patch.remove_nodes)} 个节点")
    if patch.remove_edges:
        warnings.append(f"将删除 {len(patch.remove_edges)} 条连线")
    return warnings


def is_destructive(patch: GraphPatch) -> bool:
    """True when the patch removes nodes or edges."""
    return len(patch.remove_nodes) > 0 or len(patch.remove_edges) > 0


# ---------------------------------------------------------------------------
# GraphPatch computation (existing spec vs compiled spec)
# ---------------------------------------------------------------------------


def _node_field(data: dict[str, Any], camel: str, snake: str) -> Any:
    """Read a node data field tolerating camelCase / snake_case specs."""
    if camel in data:
        return data.get(camel)
    return data.get(snake)


def _node_semantics(data: dict[str, Any]) -> tuple:
    """Comparable semantic fields of a node's data dict."""
    return (
        data.get("label"),
        data.get("config"),
        _node_field(data, "moduleId", "module_id"),
        _node_field(data, "moduleVersion", "module_version"),
        _node_field(data, "configOverrides", "config_overrides"),
    )


def _edge_key(edge: dict[str, Any]) -> tuple:
    """Topology key for an edge — ids are regenerated per compile."""
    source_handle = edge.get("sourceHandle", edge.get("source_handle"))
    target_handle = edge.get("targetHandle", edge.get("target_handle"))
    return (edge.get("source"), source_handle, edge.get("target"), target_handle)


def compute_graph_patch(existing: dict[str, Any], compiled: dict[str, Any]) -> GraphPatch:
    """Diff two WorkflowSpec-shaped dicts into an incremental GraphPatch.

    Nodes are matched by id (the compiler preserves original ids when known).
    Edges are matched by topology ``(source, handle, target, handle)`` so
    regenerated edge ids do not count as churn.  Untouched nodes/edges are
    omitted from the patch entirely.
    """
    existing_nodes = {n.get("id"): n for n in existing.get("nodes", []) if isinstance(n, dict)}
    compiled_nodes = {n.get("id"): n for n in compiled.get("nodes", []) if isinstance(n, dict)}

    remove_nodes = [nid for nid in existing_nodes if nid not in compiled_nodes]
    add_nodes = [
        WorkflowNode.model_validate(n)
        for nid, n in compiled_nodes.items()
        if nid not in existing_nodes
    ]

    update_nodes: list[NodeUpdate] = []
    for nid, old_node in existing_nodes.items():
        new_node = compiled_nodes.get(nid)
        if new_node is None:
            continue
        old_data = old_node.get("data") or {}
        new_data = new_node.get("data") or {}
        if _node_semantics(old_data) == _node_semantics(new_data):
            continue
        label_changed = old_data.get("label") != new_data.get("label")
        config_changed = old_data.get("config") != new_data.get("config")
        update_nodes.append(NodeUpdate(
            id=nid,
            label=new_data.get("label") if label_changed else None,
            config=new_data.get("config") if config_changed else None,
        ))

    existing_edges = {_edge_key(e): e for e in existing.get("edges", []) if isinstance(e, dict)}
    compiled_edges = {_edge_key(e): e for e in compiled.get("edges", []) if isinstance(e, dict)}

    remove_edges = [
        e.get("id") for key, e in existing_edges.items() if key not in compiled_edges
    ]
    add_edges = [
        WorkflowEdge.model_validate(e)
        for key, e in compiled_edges.items()
        if key not in existing_edges
    ]

    return GraphPatch(
        description="增量修改",
        add_nodes=add_nodes,
        remove_nodes=remove_nodes,
        update_nodes=update_nodes,
        add_edges=add_edges,
        remove_edges=remove_edges,
    )


# ---------------------------------------------------------------------------
# Incremental patch application
# ---------------------------------------------------------------------------


def apply_graph_patch(
    existing: dict[str, Any],
    patch: GraphPatch,
    compiled: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a GraphPatch to a WorkflowSpec-shaped dict.

    Mirrors ``POST /api/agent/apply-patch`` semantics: remove nodes/edges by
    id, update the listed nodes, append added nodes/edges, and leave every
    untouched node/edge byte-identical (ids, positions, edge ids preserved).

    When *compiled* is provided, updated nodes also take the compiled data
    wholesale (except ``status``) so module upgrades/reconfigures land too.
    Raises ``ValueError`` on patch conflicts (caller maps to 400).
    """
    patch.validate_no_conflicts()

    remove_node_ids = set(patch.remove_nodes)
    remove_edge_ids = set(patch.remove_edges)

    remaining_nodes = [
        n for n in existing.get("nodes", [])
        if isinstance(n, dict) and n.get("id") not in remove_node_ids
    ]
    remaining_edges = [
        e for e in existing.get("edges", [])
        if isinstance(e, dict)
        and e.get("id") not in remove_edge_ids
        and e.get("source") not in remove_node_ids
        and e.get("target") not in remove_node_ids
    ]

    compiled_by_id = {
        n.get("id"): n
        for n in (compiled or {}).get("nodes", [])
        if isinstance(n, dict)
    }
    update_map = {u.id: u for u in patch.update_nodes}

    new_nodes: list[dict[str, Any]] = []
    for node in remaining_nodes:
        nid = node.get("id")
        if nid not in update_map:
            new_nodes.append(node)
            continue
        node = copy.deepcopy(node)
        u = update_map[nid]
        src = compiled_by_id.get(nid)
        if src is not None:
            new_data = copy.deepcopy(src.get("data") or {})
            old_data = node.get("data") or {}
            if "status" in old_data:
                new_data["status"] = old_data["status"]
            node["data"] = new_data
        else:
            data = dict(node.get("data") or {})
            if u.label is not None:
                data["label"] = u.label
            if u.config is not None:
                data["config"] = u.config
            node["data"] = data
        new_nodes.append(node)

    added_nodes = [n.model_dump(by_alias=True) for n in patch.add_nodes]
    added_edges = [e.model_dump(by_alias=True) for e in patch.add_edges]

    patched = copy.deepcopy(existing)
    patched["nodes"] = new_nodes + added_nodes
    patched["edges"] = remaining_edges + added_edges
    return patched


# ---------------------------------------------------------------------------
# Module diffs (moduleId / moduleVersion / configOverrides per node)
# ---------------------------------------------------------------------------


def _module_identity(data: dict[str, Any]) -> tuple[str | None, str | None, dict[str, Any]]:
    module_id = _node_field(data, "moduleId", "module_id")
    module_version = _node_field(data, "moduleVersion", "module_version")
    overrides = _node_field(data, "configOverrides", "config_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    return module_id, module_version, overrides


def _module_upgrade_details(module_id: str, old_version: str | None, new_version: str | None) -> dict[str, Any]:
    """compute_module_diff(old, new).to_dict() when both versions resolve."""
    try:
        from backend.app.services.module_diff import compute_module_diff
        from backend.app.services.module_registry import get_module_registry

        registry = get_module_registry()
        old_module = registry.get_module(module_id, old_version) if old_version else None
        new_module = registry.get_module(module_id, new_version) if new_version else None
        if old_module is not None and new_module is not None:
            return compute_module_diff(old_module, new_module).to_dict()
    except Exception:
        pass
    return {"versionFrom": old_version, "versionTo": new_version, "breaking": False}


def compute_module_diffs(existing: dict[str, Any], compiled: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-node module diffs between the existing and the compiled workflow.

    Each entry: ``{"nodeId", "moduleId", "from", "to", "type", "details"}``
    where ``type`` is ``added`` | ``removed`` | ``upgraded`` | ``reconfigured``
    and ``from``/``to`` are module version strings (None when absent).
    """
    existing_nodes = {n.get("id"): n for n in existing.get("nodes", []) if isinstance(n, dict)}
    compiled_nodes = {n.get("id"): n for n in compiled.get("nodes", []) if isinstance(n, dict)}
    entries: list[dict[str, Any]] = []

    def _entry(node_id, module_id, from_version, to_version, type_, details):
        entries.append({
            "nodeId": node_id,
            "moduleId": module_id,
            "from": from_version,
            "to": to_version,
            "type": type_,
            "details": details,
        })

    # Nodes present on only one side
    for nid, node in existing_nodes.items():
        if nid in compiled_nodes:
            continue
        module_id, version, _ = _module_identity(node.get("data") or {})
        if module_id:
            _entry(nid, module_id, version, None, "removed", {})

    for nid, node in compiled_nodes.items():
        if nid in existing_nodes:
            continue
        module_id, version, _ = _module_identity(node.get("data") or {})
        if module_id:
            _entry(nid, module_id, None, version, "added", {})

    # Nodes present on both sides
    for nid, old_node in existing_nodes.items():
        new_node = compiled_nodes.get(nid)
        if new_node is None:
            continue
        old_id, old_ver, old_ov = _module_identity(old_node.get("data") or {})
        new_id, new_ver, new_ov = _module_identity(new_node.get("data") or {})

        if old_id == new_id and old_ver == new_ver and old_ov == new_ov:
            continue

        if old_id and not new_id:
            _entry(nid, old_id, old_ver, None, "removed", {})
            continue
        if new_id and not old_id:
            _entry(nid, new_id, None, new_ver, "added", {})
            continue
        if not old_id and not new_id:
            continue

        if old_id != new_id:
            # Module swap — report as removal of the old and addition of the new.
            _entry(nid, old_id, old_ver, None, "removed", {})
            _entry(nid, new_id, None, new_ver, "added", {})
            continue

        if old_ver != new_ver:
            _entry(
                nid, new_id, old_ver, new_ver, "upgraded",
                _module_upgrade_details(new_id, old_ver, new_ver),
            )
            continue

        # Same module + version, different configOverrides
        changed_keys = sorted(
            key for key in set(old_ov) | set(new_ov) if old_ov.get(key) != new_ov.get(key)
        )
        _entry(
            nid, new_id, old_ver, new_ver, "reconfigured",
            {
                "changedKeys": changed_keys,
                "from": {key: old_ov.get(key) for key in changed_keys},
                "to": {key: new_ov.get(key) for key in changed_keys},
            },
        )

    return entries
