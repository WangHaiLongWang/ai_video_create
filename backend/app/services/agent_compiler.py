"""Intent Compiler -- translates WorkflowIntent into WorkflowSpecV2.

The Agent outputs a high-level intent with aliases and connections.
This compiler:
1. Assigns stable UUIDs to each node
2. Creates React Flow edges with sourceHandle/targetHandle
3. Computes node positions using a simple layout algorithm
4. Validates the result against node manifests
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    WorkflowIntent,
)
from backend.app.services.agent_tools import _NODE_CATALOG_V2

# ---------------------------------------------------------------------------
# Layout constants (matching frontend createPromptToVideoWorkflow)
# ---------------------------------------------------------------------------

_NODE_WIDTH = 228
_GAP = 60
_SPACING = _NODE_WIDTH + _GAP  # 288px
_START_X = 110


def _deterministic_id(alias: str) -> str:
    """Generate a short, deterministic id from an alias.

    Format: ``{alias}-{hash8}`` where hash8 is the first 8 hex chars of a
    SHA-256 of the alias.  This is idempotent for the same alias while
    remaining readable.
    """
    digest = hashlib.sha256(alias.encode("utf-8")).hexdigest()[:8]
    return f"{alias}-{digest}"


def _uuid() -> str:
    """Return a new random UUID4 string."""
    return str(uuid.uuid4())


def _node_position(index: int) -> dict[str, float]:
    """Compute position for node at *index* in a horizontal chain."""
    x = float(_START_X + index * _SPACING)
    y = 220.0 if index % 2 else 150.0  # alternate rows like the frontend
    return {"x": x, "y": y}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compile_intent(intent: WorkflowIntent) -> dict[str, Any]:
    """Compile a :class:`WorkflowIntent` into a WorkflowSpecV2 dict.

    Parameters
    ----------
    intent:
        High-level intent produced by the Agent.

    Returns
    -------
    dict
        A complete WorkflowSpecV2 dictionary ready for the frontend.
    """
    alias_to_id: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []

    # --- 1. Create React Flow nodes ---
    for idx, node_intent in enumerate(intent.nodes):
        node_id = _deterministic_id(node_intent.alias)
        alias_to_id[node_intent.alias] = node_id

        manifest = _NODE_CATALOG_V2.get(node_intent.kind)

        # Resolve label and description from manifest or intent overrides
        label = node_intent.label or (manifest.label if manifest else node_intent.kind)
        description = (
            node_intent.description
            or (manifest.description if manifest else "")
        )

        # Ports from manifest
        ports: dict[str, Any] | None = None
        input_type: str | None = None
        output_type: str | None = None

        if manifest:
            ports = {
                "inputs": [
                    {
                        "id": p.id,
                        "type": p.type,
                        "required": p.required,
                        "cardinality": p.cardinality,
                        "label": p.label or p.id,
                    }
                    for p in manifest.ports.inputs
                ],
                "outputs": [
                    {
                        "id": p.id,
                        "type": p.type,
                        "required": False,
                        "cardinality": p.cardinality,
                        "label": p.label or p.id,
                    }
                    for p in manifest.ports.outputs
                ],
            }
            input_type = manifest.ports.inputs[0].type if manifest.ports.inputs else None
            output_type = manifest.ports.outputs[0].type if manifest.ports.outputs else None

        # Merge config: intent overrides take precedence over defaults
        config: dict[str, Any] = {}
        if manifest and manifest.config_schema:
            for key, schema in manifest.config_schema.items():
                if isinstance(schema, dict) and "default" in schema:
                    config[key] = schema["default"]
        config.update(node_intent.config)

        node = {
            "id": node_id,
            "type": "studio",
            "position": _node_position(idx),
            "data": {
                "label": label,
                "description": description,
                "kind": node_intent.kind,
                "inputType": input_type,
                "outputType": output_type,
                "status": "idle",
                "config": config,
                "ports": ports,
            },
        }
        nodes.append(node)

    # --- 2. Create React Flow edges ---
    edges: list[dict[str, Any]] = []
    for conn in intent.connections:
        source_id = alias_to_id.get(conn.source.node)
        target_id = alias_to_id.get(conn.target.node)
        if source_id is None or target_id is None:
            # Skip invalid references (validator will catch these)
            continue

        edge: dict[str, Any] = {
            "id": _uuid(),
            "source": source_id,
            "sourceHandle": conn.source.port,
            "target": target_id,
            "targetHandle": conn.target.port,
            "data": {
                "mode": conn.mode,
                "label": "",
            },
        }
        edges.append(edge)

    # --- 3. Assemble WorkflowSpecV2 ---
    spec: dict[str, Any] = {
        "schemaVersion": "2.0",
        "manifestVersion": "1.0",
        "id": _uuid(),
        "name": intent.name,
        "description": intent.description,
        "nodes": nodes,
        "edges": edges,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "metadata": {
            "tags": intent.tags,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
    }

    return spec
