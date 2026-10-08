from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from .node_manifest import NodeManifest, PortDefinition


class GraphValidationError(BaseModel):
    """A single validation error found in a workflow graph."""

    code: str
    message: str
    edge_id: str | None = None
    node_id: str | None = None
    port_id: str | None = None


def _types_compatible(a: str, b: str) -> bool:
    """Two types are compatible when identical or either side is 'any'."""
    return a == b or a == "any" or b == "any"


def _find_output_port(ports: list[PortDefinition], handle_id: str | None) -> PortDefinition | None:
    for p in ports:
        if p.id == handle_id:
            return p
    return None


def _find_input_port(ports: list[PortDefinition], handle_id: str | None) -> PortDefinition | None:
    for p in ports:
        if p.id == handle_id:
            return p
    return None


def _coerce_port(raw: Any) -> PortDefinition:
    """Coerce a raw port dict (or PortDefinition) into a PortDefinition."""
    if isinstance(raw, PortDefinition):
        return raw
    return PortDefinition(**raw)


def _module_ports(module_id: str, module_version: str | None) -> tuple[list[PortDefinition], list[PortDefinition]] | None:
    """Resolve a module's ports from the module registry, or None on failure."""
    try:
        from backend.app.services.module_registry import get_module_registry

        module = get_module_registry().get_module(module_id, module_version)
    except Exception:
        return None
    if module is None:
        return None
    raw = module.ports or {}
    inputs = [_coerce_port(p) for p in raw.get("inputs", [])]
    outputs = [_coerce_port(p) for p in raw.get("outputs", [])]
    return inputs, outputs


def _effective_ports(
    node: dict, catalog: dict[str, NodeManifest]
) -> tuple[list[PortDefinition], list[PortDefinition], bool]:
    """Resolve a node's effective input/output ports.

    Resolution order (first match wins):

    1. Instance-level ``data.ports`` — what the canvas renders and edits
       (module extension ports, per-instance port CRUD).
    2. Module registry via ``data.moduleId`` / ``data.moduleVersion``.
    3. The kind-keyed catalog (``_NODE_CATALOG_V2``) — covers legacy nodes
       and V1 exports where ports were stripped.

    Returns ``(inputs, outputs, resolved)``. ``resolved`` is False only when
    no port source could be found (unknown kind, no instance ports, no module).
    """
    data = node.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    raw_ports = data.get("ports")
    if isinstance(raw_ports, dict):
        inputs = [_coerce_port(p) for p in raw_ports.get("inputs", [])]
        outputs = [_coerce_port(p) for p in raw_ports.get("outputs", [])]
        return inputs, outputs, True

    module_id = data.get("moduleId")
    if module_id:
        resolved = _module_ports(module_id, data.get("moduleVersion"))
        if resolved is not None:
            return resolved[0], resolved[1], True

    kind = node.get("kind") or data.get("kind")
    manifest = catalog.get(kind) if kind else None
    if manifest is not None:
        return list(manifest.ports.inputs), list(manifest.ports.outputs), True

    return [], [], False


def validate_graph(
    spec: dict,
    catalog: dict[str, NodeManifest],
) -> list[GraphValidationError]:
    """Validate a workflow graph spec against each node's effective ports.

    Ports are resolved per node from ``data.ports`` (preferred), then the
    module registry via ``data.moduleId``/``data.moduleVersion``, then the
    kind-keyed catalog. This keeps save/start conclusions aligned with what
    the canvas renders for module-aware nodes.

    Parameters
    ----------
    spec:
        Dict with "nodes" (list of {id, kind, data?}) and "edges" (list of
        {id, source, sourceHandle?, target, targetHandle?}).
    catalog:
        Mapping of node kind string to :class:`NodeManifest` (fallback source).

    Returns
    -------
    List of :class:`GraphValidationError` (empty if valid).
    """
    errors: list[GraphValidationError] = []

    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # Effective ports per node (data.ports > module registry > catalog)
    ports_map: dict[str, tuple[list[PortDefinition], list[PortDefinition], bool]] = {
        n["id"]: _effective_ports(n, catalog) for n in nodes
    }

    # UNKNOWN_NODE_KIND — no port source at all for this node
    for node in nodes:
        _, _, resolved = ports_map[node["id"]]
        if not resolved:
            data = node.get("data") or {}
            kind = node.get("kind") or (data.get("kind") if isinstance(data, dict) else None)
            errors.append(
                GraphValidationError(
                    code="UNKNOWN_NODE_KIND",
                    message=f"节点 {node['id']} 的类型 {kind or '?'} 未在节点目录中注册",
                    node_id=node["id"],
                )
            )

    # 1. Self-loop
    for edge in edges:
        if edge["source"] == edge["target"]:
            errors.append(
                GraphValidationError(
                    code="SELF_LOOP",
                    message=f"连线 {edge['id']} 不能连接节点自身",
                    edge_id=edge["id"],
                )
            )

    # 2. Duplicate edge
    seen_keys: set[str] = set()
    for edge in edges:
        key = f"{edge['source']}::{edge.get('sourceHandle', '')}>>{edge['target']}::{edge.get('targetHandle', '')}"
        if key in seen_keys:
            errors.append(
                GraphValidationError(
                    code="DUPLICATE_EDGE",
                    message=f"连线 {edge['id']} 重复：相同的源端口已连接到相同的目标端口",
                    edge_id=edge["id"],
                )
            )
        seen_keys.add(key)

    # 3. Type mismatch
    for edge in edges:
        src_node = node_map.get(edge["source"])
        tgt_node = node_map.get(edge["target"])
        if not src_node or not tgt_node:
            continue

        src_entry = ports_map.get(edge["source"])
        tgt_entry = ports_map.get(edge["target"])
        if not src_entry or not tgt_entry:
            continue

        _, src_outputs, _ = src_entry
        tgt_inputs, _, _ = tgt_entry

        src_port = _find_output_port(src_outputs, edge.get("sourceHandle"))
        tgt_port = _find_input_port(tgt_inputs, edge.get("targetHandle"))

        if src_port and tgt_port and not _types_compatible(src_port.type, tgt_port.type):
            errors.append(
                GraphValidationError(
                    code="TYPE_MISMATCH",
                    message=f"端口类型不兼容：{edge['source']} 的 {src_port.type} 不能连接到 {edge['target']} 的 {tgt_port.type}",
                    edge_id=edge["id"],
                    node_id=edge["target"],
                    port_id=tgt_port.id,
                )
            )

    # 4. Cardinality violation
    input_edge_count: dict[str, int] = defaultdict(int)
    for edge in edges:
        key = f"{edge['target']}::{edge.get('targetHandle', '')}"
        input_edge_count[key] += 1

    for key, count in input_edge_count.items():
        if count <= 1:
            continue
        node_id, port_handle = key.split("::", 1)
        entry = ports_map.get(node_id)
        if not entry:
            continue
        port = _find_input_port(entry[0], port_handle)
        if port and port.cardinality == "one" and count > 1:
            errors.append(
                GraphValidationError(
                    code="CARDINALITY_VIOLATION",
                    message=f"端口 {port.id} 的基数为 \"one\"，但已连接 {count} 条边",
                    node_id=node_id,
                    port_id=port.id,
                )
            )

    # 5. Required port warning
    for node in nodes:
        entry = ports_map.get(node["id"])
        if not entry:
            continue
        for port in entry[0]:
            if not port.required:
                continue
            has_edge = any(
                e["target"] == node["id"] and e.get("targetHandle", "") == port.id
                for e in edges
            )
            if not has_edge:
                errors.append(
                    GraphValidationError(
                        code="REQUIRED_PORT",
                        message=f"节点 {node['id']} 的必需输入端口 {port.id} 未连接",
                        node_id=node["id"],
                        port_id=port.id,
                    )
                )

    # 6. Cycle detection — DFS
    adjacency: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        adjacency[node["id"]] = []
    for edge in edges:
        adjacency[edge["source"]].append(edge["target"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n["id"]: WHITE for n in nodes}

    has_cycle = False
    cycle_edge_id: str | None = None

    def dfs(u: str) -> None:
        nonlocal has_cycle, cycle_edge_id
        if has_cycle:
            return
        color[u] = GRAY
        for v in adjacency.get(u, []):
            if has_cycle:
                return
            if color.get(v) == GRAY:
                cycle_edge = next(
                    (e for e in edges if e["source"] == u and e["target"] == v), None
                )
                cycle_edge_id = cycle_edge["id"] if cycle_edge else None
                has_cycle = True
                return
            if color.get(v) == WHITE:
                dfs(v)
        color[u] = BLACK

    for n in nodes:
        if color[n["id"]] == WHITE:
            dfs(n["id"])
            if has_cycle:
                break

    if has_cycle:
        errors.append(
            GraphValidationError(
                code="CYCLE",
                message="图中存在环路，工作流不能包含循环",
                edge_id=cycle_edge_id,
            )
        )

    # 7. Unknown handle + direction — output->output or input->input
    for edge in edges:
        src_node = node_map.get(edge["source"])
        tgt_node = node_map.get(edge["target"])
        if not src_node or not tgt_node:
            continue

        src_entry = ports_map.get(edge["source"])
        tgt_entry = ports_map.get(edge["target"])
        if not src_entry or not tgt_entry:
            continue

        src_inputs, src_outputs, _ = src_entry
        tgt_inputs, tgt_outputs, _ = tgt_entry

        src_output = _find_output_port(src_outputs, edge.get("sourceHandle"))
        src_input = _find_input_port(src_inputs, edge.get("sourceHandle"))
        tgt_output = _find_output_port(tgt_outputs, edge.get("targetHandle"))
        tgt_input = _find_input_port(tgt_inputs, edge.get("targetHandle"))

        # UNKNOWN_HANDLE — a named handle must exist in the effective ports
        if edge.get("sourceHandle") and not src_output and not src_input:
            errors.append(
                GraphValidationError(
                    code="UNKNOWN_HANDLE",
                    message=(
                        f"连线 {edge['id']} 的源端口 {edge['sourceHandle']} "
                        f"不存在于节点 {edge['source']} 的端口列表"
                    ),
                    edge_id=edge["id"],
                    node_id=edge["source"],
                    port_id=edge["sourceHandle"],
                )
            )
        if edge.get("targetHandle") and not tgt_input and not tgt_output:
            errors.append(
                GraphValidationError(
                    code="UNKNOWN_HANDLE",
                    message=(
                        f"连线 {edge['id']} 的目标端口 {edge['targetHandle']} "
                        f"不存在于节点 {edge['target']} 的端口列表"
                    ),
                    edge_id=edge["id"],
                    node_id=edge["target"],
                    port_id=edge["targetHandle"],
                )
            )

        if not src_output and src_input:
            errors.append(
                GraphValidationError(
                    code="DIRECTION",
                    message=f"连线 {edge['id']} 不能从输入端口 {edge.get('sourceHandle', '')} 发出",
                    edge_id=edge["id"],
                )
            )

        if not tgt_input and tgt_output:
            errors.append(
                GraphValidationError(
                    code="DIRECTION",
                    message=f"连线 {edge['id']} 不能连接到输出端口 {edge.get('targetHandle', '')}",
                    edge_id=edge["id"],
                )
            )

    return errors
