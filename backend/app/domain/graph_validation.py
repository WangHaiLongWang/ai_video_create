"""Backend authoritative graph validation service.

This module is the single entry point for validating workflow graphs at ALL
mutation boundaries: create, update, import, agent generate/modify/apply, and
execution start.

It delegates to the schema-level ``validate_graph`` (which handles self-loops,
duplicate edges, type mismatches, cardinality, required ports, cycle detection,
unknown handles/kinds, and direction checks) and wraps the result into a
structured error envelope suitable for HTTP422 responses.

Port resolution is module-aware and matches what the canvas renders: each
node's effective ports come from ``data.ports`` (preferred), then the module
registry via ``data.moduleId``/``data.moduleVersion``, then the kind-keyed
catalog. Start-time conclusions therefore agree with connect/reconnect
validation on the frontend without reordering the execution pipeline.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from backend.app.schemas.graph_validator import (
    GraphValidationError,
    validate_graph as _validate_graph,
)
from backend.app.schemas.node_manifest import NodeManifest


# ---------------------------------------------------------------------------
# Default catalog -- HARD-101: loaded from schemas/base-node-manifest.json
# via backend.app.schemas.node_catalog (single source of truth).
# ---------------------------------------------------------------------------

_default_catalog: dict[str, NodeManifest] | None = None


def get_node_catalog() -> dict[str, NodeManifest]:
    """Return the authoritative node manifest catalog.

    Port id/type/cardinality come from the shared base-node-manifest.json
    (HARD-101). Lazy-loaded so module import order stays cheap.
    """
    global _default_catalog
    if _default_catalog is None:
        from backend.app.schemas.node_catalog import load_node_catalog

        _default_catalog = dict(load_node_catalog())
    return _default_catalog


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

# Error codes used in structured responses
CODE_GRAPH_INVALID = "WORKFLOW_GRAPH_INVALID"


def validate_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    catalog: dict[str, NodeManifest] | None = None,
) -> list[GraphValidationError]:
    """Validate a workflow graph and return a list of errors.

    Parameters
    ----------
    nodes:
        List of node dicts. Each must have at least ``id`` and ``kind`` keys.
        ``data.ports`` / ``data.moduleId`` are honoured when present so
        module-instance nodes are validated against their effective ports.
    edges:
        List of edge dicts. Each must have at least ``id``, ``source``,
        ``target`` keys; ``sourceHandle`` and ``targetHandle`` are optional.
    catalog:
        Node manifest catalog (fallback port source). Falls back to the
        global default if *None*.

    Returns
    -------
    List of :class:`GraphValidationError` (empty if valid).
    """
    if catalog is None:
        catalog = get_node_catalog()

    # Normalise nodes -- the schema validator expects a ``kind`` key at top
    # level.  WorkflowSpec nodes store it inside ``data.kind``; we accept both.
    norm_nodes: list[dict[str, Any]] = []
    for n in nodes:
        kind = n.get("kind") or (n.get("data") or {}).get("kind")
        if kind is None:
            # Still pass through -- the schema-level validator will simply
            # skip manifest-based checks for this node.
            norm_nodes.append(n)
        else:
            norm_nodes.append({**n, "kind": kind})

    spec = {"nodes": norm_nodes, "edges": edges}
    return _validate_graph(spec, catalog)


# ---------------------------------------------------------------------------
# Structured422 error envelope
# ---------------------------------------------------------------------------

def build_422_response(errors: list[GraphValidationError]) -> dict[str, Any]:
    """Build the structured422 JSON body.

    Returns
    -------
    dict suitable for ``raise HTTPException(422, detail=...)``.
    """
    error_details = [
        {
            "code": e.code,
            "message": e.message,
            **({"nodeId": e.node_id} if e.node_id else {}),
            **({"edgeId": e.edge_id} if e.edge_id else {}),
            **({"portId": e.port_id} if e.port_id else {}),
        }
        for e in errors
    ]

    return {
        "error": {
            "code": CODE_GRAPH_INVALID,
            "message": f"工作流包含 {len(errors)} 个连接错误",
            "details": {"errors": error_details},
        }
    }


def raise_if_invalid(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    catalog: dict[str, NodeManifest] | None = None,
) -> list[GraphValidationError]:
    """Validate the graph and raise HTTPException422 if there are errors.

    This is the convenience function that API endpoints should call.

    Returns
    -------
    Empty list if valid (caller can use the result for success-path logic).

    Raises
    ------
    HTTPException422 with the structured error envelope if validation fails.
    """
    errors = validate_graph(nodes, edges, catalog)
    if errors:
        detail = build_422_response(errors)
        raise HTTPException(status_code=422, detail=detail)
    return errors


# ---------------------------------------------------------------------------
# Helpers for extracting nodes/edges from various input formats
# ---------------------------------------------------------------------------

def extract_nodes_edges_from_spec(spec: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Extract nodes and edges dicts from a WorkflowSpec-like dict.

    Handles both V1 format (nodes have ``data.kind``) and V2 format
    (nodes have ``kind`` at top level).
    """
    raw_nodes = spec.get("nodes", [])
    raw_edges = spec.get("edges", [])
    return raw_nodes, raw_edges
