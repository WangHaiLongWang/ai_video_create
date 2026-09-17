"""Intent Repair -- validates and attempts to fix a WorkflowIntent.

The repair loop:
1. Validate the intent
2. If errors, attempt automatic fixes
3. Re-validate
4. Repeat up to ``max_repairs`` times
5. Return the (repaired) intent + remaining errors + repair log
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)
from backend.app.services.agent_tools import validate_intent


# ---------------------------------------------------------------------------
# Repair result
# ---------------------------------------------------------------------------


@dataclass
class RepairResult:
    """Outcome of a repair attempt."""

    repaired_intent: WorkflowIntent
    """The intent after all repair passes."""
    errors: list[dict[str, Any]] = field(default_factory=list)
    """Remaining validation errors that could not be auto-fixed."""
    warnings: list[str] = field(default_factory=list)
    """Warnings carried over from validation."""
    repairs: list[str] = field(default_factory=list)
    """Human-readable log of repairs applied."""
    attempts: int = 0
    """Number of validation + repair rounds executed."""


# ---------------------------------------------------------------------------
# Repair strategies
# ---------------------------------------------------------------------------


def _repair_duplicate_alias(intents: list[NodeIntent]) -> tuple[list[NodeIntent], list[str]]:
    """Deduplicate aliases by keeping the first occurrence and renaming later ones."""
    seen: set[str] = set()
    repaired: list[NodeIntent] = []
    logs: list[str] = []
    for node in intents:
        if node.alias in seen:
            # Append suffix to disambiguate
            suffix = 2
            while f"{node.alias}_{suffix}" in seen:
                suffix += 1
            new_alias = f"{node.alias}_{suffix}"
            logs.append(
                f"Renamed duplicate alias '{node.alias}' -> '{new_alias}'"
            )
            repaired.append(node.model_copy(update={"alias": new_alias}))
            seen.add(new_alias)
        else:
            seen.add(node.alias)
            repaired.append(node)
    return repaired, logs


def _repair_unknown_kind(
    nodes: list[NodeIntent],
    connections: list[ConnectionIntent],
) -> tuple[list[NodeIntent], list[ConnectionIntent], list[str]]:
    """Remove nodes with unknown kinds and their associated connections."""
    from backend.app.services.agent_tools import _NODE_CATALOG_V2

    bad_aliases: set[str] = set()
    repaired_nodes: list[NodeIntent] = []
    logs: list[str] = []

    for node in nodes:
        if node.kind not in _NODE_CATALOG_V2:
            bad_aliases.add(node.alias)
            logs.append(f"Removed node '{node.alias}' with unknown kind '{node.kind}'")
        else:
            repaired_nodes.append(node)

    # Remove connections referencing removed nodes
    repaired_conns = [
        c
        for c in connections
        if c.source.node not in bad_aliases and c.target.node not in bad_aliases
    ]
    removed_count = len(connections) - len(repaired_conns)
    if removed_count > 0:
        logs.append(f"Removed {removed_count} connection(s) referencing deleted nodes")

    return repaired_nodes, repaired_conns, logs


def _repair_duplicate_connections(connections: list[ConnectionIntent]) -> tuple[list[ConnectionIntent], list[str]]:
    """Remove duplicate connections (same source/target port pair)."""
    seen: set[tuple[str, str, str, str]] = set()
    repaired: list[ConnectionIntent] = []
    logs: list[str] = []

    for conn in connections:
        key = (conn.source.node, conn.source.port, conn.target.node, conn.target.port)
        if key in seen:
            logs.append(
                f"Removed duplicate connection: {conn.source.node}.{conn.source.port} "
                f"-> {conn.target.node}.{conn.target.port}"
            )
        else:
            seen.add(key)
            repaired.append(conn)

    return repaired, logs


def _repair_self_loops(connections: list[ConnectionIntent]) -> tuple[list[ConnectionIntent], list[str]]:
    """Remove self-loop connections."""
    repaired: list[ConnectionIntent] = []
    logs: list[str] = []

    for conn in connections:
        if conn.source.node == conn.target.node:
            logs.append(
                f"Removed self-loop connection on node '{conn.source.node}'"
            )
        else:
            repaired.append(conn)

    return repaired, logs


def _repair_unknown_port(
    nodes: list[NodeIntent],
    connections: list[ConnectionIntent],
) -> tuple[list[ConnectionIntent], list[str]]:
    """Remove connections that reference ports not present on the respective node's manifest."""
    from backend.app.services.agent_tools import _NODE_CATALOG_V2

    alias_to_node = {n.alias: n for n in nodes}
    repaired: list[ConnectionIntent] = []
    logs: list[str] = []

    for conn in connections:
        # Check source node and port
        src_node = alias_to_node.get(conn.source.node)
        if src_node is not None:
            src_manifest = _NODE_CATALOG_V2.get(src_node.kind)
            if src_manifest is not None:
                src_port = next(
                    (p for p in src_manifest.ports.outputs if p.id == conn.source.port),
                    None,
                )
                if src_port is None:
                    logs.append(
                        f"Removed connection with unknown source port "
                        f"'{conn.source.port}' on '{conn.source.node}'"
                    )
                    continue

        # Check target node and port
        tgt_node = alias_to_node.get(conn.target.node)
        if tgt_node is not None:
            tgt_manifest = _NODE_CATALOG_V2.get(tgt_node.kind)
            if tgt_manifest is not None:
                tgt_port = next(
                    (p for p in tgt_manifest.ports.inputs if p.id == conn.target.port),
                    None,
                )
                if tgt_port is None:
                    logs.append(
                        f"Removed connection with unknown target port "
                        f"'{conn.target.port}' on '{conn.target.node}'"
                    )
                    continue

        repaired.append(conn)

    return repaired, logs


def _repair_unknown_node(
    nodes: list[NodeIntent],
    connections: list[ConnectionIntent],
) -> tuple[list[ConnectionIntent], list[str]]:
    """Remove connections referencing nodes that no longer exist."""
    valid_aliases = {n.alias for n in nodes}
    repaired: list[ConnectionIntent] = []
    logs: list[str] = []

    for conn in connections:
        if conn.source.node not in valid_aliases:
            logs.append(
                f"Removed connection referencing unknown source node '{conn.source.node}'"
            )
            continue
        if conn.target.node not in valid_aliases:
            logs.append(
                f"Removed connection referencing unknown target node '{conn.target.node}'"
            )
            continue
        repaired.append(conn)

    return repaired, logs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def repair_intent(
    intent: WorkflowIntent,
    max_repairs: int = 2,
) -> RepairResult:
    """Validate a :class:`WorkflowIntent` and attempt automatic repairs.

    The function runs up to *max_repairs* rounds of:
        validate -> repair -> re-validate

    Parameters
    ----------
    intent:
        The potentially broken intent to repair.
    max_repairs:
        Maximum number of repair iterations (default 2).

    Returns
    -------
    RepairResult
        Contains the repaired intent, any remaining errors, a repair log,
        and the number of attempts made.
    """
    # Work on a deep copy to avoid mutating the original
    current_nodes = [n.model_copy(deep=True) for n in intent.nodes]
    current_conns = [c.model_copy(deep=True) for c in intent.connections]
    all_repairs: list[str] = []
    remaining_warnings: list[str] = list(intent.warnings)

    for attempt in range(1, max_repairs + 1):
        # Build a temporary intent for validation
        temp_intent = WorkflowIntent(
            name=intent.name,
            description=intent.description,
            template_id=intent.template_id,
            nodes=current_nodes,
            connections=current_conns,
            tags=intent.tags,
            scene_count=intent.scene_count,
            variant_count=intent.variant_count,
            duration=intent.duration,
            resolution=intent.resolution,
            warnings=remaining_warnings,
        )

        validation = validate_intent(temp_intent)
        if validation.success:
            return RepairResult(
                repaired_intent=temp_intent,
                errors=[],
                warnings=remaining_warnings,
                repairs=all_repairs,
                attempts=attempt,
            )

        errors = validation.data.get("errors", [])
        remaining_warnings = validation.data.get("warnings", [])
        round_logs: list[str] = []

        # --- Apply repairs based on error codes ---
        codes = {e.get("code") for e in errors}

        if "DUPLICATE_ALIAS" in codes:
            current_nodes, logs = _repair_duplicate_alias(current_nodes)
            all_repairs.extend(logs)
            round_logs.extend(logs)

        if "UNKNOWN_KIND" in codes:
            current_nodes, current_conns, logs = _repair_unknown_kind(
                current_nodes, current_conns
            )
            all_repairs.extend(logs)
            round_logs.extend(logs)

        if "SELF_LOOP" in codes:
            current_conns, logs = _repair_self_loops(current_conns)
            all_repairs.extend(logs)
            round_logs.extend(logs)

        if "DUPLICATE_CONNECTION" in codes:
            current_conns, logs = _repair_duplicate_connections(current_conns)
            all_repairs.extend(logs)
            round_logs.extend(logs)

        if "UNKNOWN_NODE" in codes:
            current_conns, logs = _repair_unknown_node(current_nodes, current_conns)
            all_repairs.extend(logs)
            round_logs.extend(logs)

        if "UNKNOWN_PORT" in codes:
            current_conns, logs = _repair_unknown_port(current_nodes, current_conns)
            all_repairs.extend(logs)
            round_logs.extend(logs)

        # TYPE_MISMATCH is not auto-repaired, just noted
        if "TYPE_MISMATCH" in codes:
            all_repairs.append(
                "TYPE_MISMATCH detected but not auto-repaired (requires manual intervention)"
            )

        # If no repairs were applied this round, stop early
        if not round_logs:
            break

    # Final validation after all rounds
    final_intent = WorkflowIntent(
        name=intent.name,
        description=intent.description,
        template_id=intent.template_id,
        nodes=current_nodes,
        connections=current_conns,
        tags=intent.tags,
        scene_count=intent.scene_count,
        variant_count=intent.variant_count,
        duration=intent.duration,
        resolution=intent.resolution,
        warnings=remaining_warnings,
    )
    final_validation = validate_intent(final_intent)
    final_errors = final_validation.data.get("errors", []) if not final_validation.success else []
    final_warnings = final_validation.data.get("warnings", []) if not final_validation.success else remaining_warnings

    return RepairResult(
        repaired_intent=final_intent,
        errors=final_errors,
        warnings=final_warnings if not final_validation.success else remaining_warnings,
        repairs=all_repairs,
        attempts=max_repairs,
    )
