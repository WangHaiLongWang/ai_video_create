from __future__ import annotations

from collections import defaultdict

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


def _find_output_port(manifest: NodeManifest, handle_id: str | None) -> PortDefinition | None:
    for p in manifest.ports.outputs:
        if p.id == handle_id:
            return p
    return None


def _find_input_port(manifest: NodeManifest, handle_id: str | None) -> PortDefinition | None:
    for p in manifest.ports.inputs:
        if p.id == handle_id:
            return p
    return None


def validate_graph(
    spec: dict,
    catalog: dict[str, NodeManifest],
) -> list[GraphValidationError]:
    """Validate a workflow graph spec against the node manifest catalog.

    Parameters
    ----------
    spec:
        Dict with "nodes" (list of {id, kind}) and "edges" (list of {id, source, sourceHandle?, target, targetHandle?}).
    catalog:
        Mapping of node kind string to :class:`NodeManifest`.

    Returns
    -------
    List of :class:`GraphValidationError` (empty if valid).
    """
    errors: list[GraphValidationError] = []

    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

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

        src_manifest = catalog.get(src_node["kind"])
        tgt_manifest = catalog.get(tgt_node["kind"])
        if not src_manifest or not tgt_manifest:
            continue

        src_port = _find_output_port(src_manifest, edge.get("sourceHandle"))
        tgt_port = _find_input_port(tgt_manifest, edge.get("targetHandle"))

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
        node = node_map.get(node_id)
        if not node:
            continue
        manifest = catalog.get(node.get("kind", ""))
        if not manifest:
            continue
        port = _find_input_port(manifest, port_handle)
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
        manifest = catalog.get(node.get("kind", ""))
        if not manifest:
            continue
        for port in manifest.ports.inputs:
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

    # 7. Direction — output->output or input->input
    for edge in edges:
        src_node = node_map.get(edge["source"])
        tgt_node = node_map.get(edge["target"])
        if not src_node or not tgt_node:
            continue

        src_manifest = catalog.get(src_node.get("kind", ""))
        tgt_manifest = catalog.get(tgt_node.get("kind", ""))
        if not src_manifest or not tgt_manifest:
            continue

        src_output = _find_output_port(src_manifest, edge.get("sourceHandle"))
        src_input = _find_input_port(src_manifest, edge.get("sourceHandle"))
        tgt_output = _find_output_port(tgt_manifest, edge.get("targetHandle"))
        tgt_input = _find_input_port(tgt_manifest, edge.get("targetHandle"))

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
