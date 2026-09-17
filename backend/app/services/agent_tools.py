"""Agent Tool Layer -- structured tools the Agent can call.

These tools wrap existing services and expose them as structured functions
the LLM can invoke via tool-calling or JSON function definitions.
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.node_manifest import (
    ExecutionHints,
    NodeManifest,
    PortDefinition,
    PortGroup,
)
from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)

# ---------------------------------------------------------------------------
# V2 NODE_CATALOG -- rich manifests with typed ports
# ---------------------------------------------------------------------------

_NODE_CATALOG_V2: dict[str, NodeManifest] = {
    "textInput": NodeManifest(
        kind="textInput",
        category="input",
        label="TextInput",
        description="输入提示词，作为工作流的起点",
        ports=PortGroup(
            inputs=[],
            outputs=[
                PortDefinition(id="text", type="text", required=True, label="Text"),
            ],
        ),
        config_schema={"prompt": {"type": "string", "default": ""}},
    ),
    "storyboard": NodeManifest(
        kind="storyboard",
        category="generator",
        label="Storyboard",
        description="将文本拆分为多个场景（分镜），每个场景包含叙述、图片提示词、视频提示词",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="prompt", type="text", required=True, label="Prompt"),
            ],
            outputs=[
                PortDefinition(id="scenes", type="scene", required=True, cardinality="many", label="Scenes"),
            ],
        ),
        config_schema={
            "scenes": {"type": "integer", "default": 5},
            "style": {"type": "string", "default": "cinematic"},
        },
    ),
    "textToImage": NodeManifest(
        kind="textToImage",
        category="generator",
        label="TextToImage",
        description="为每个场景生成一张图片（支持 mapOver 展开）",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="scene", type="scene", required=True, label="Scene"),
            ],
            outputs=[
                PortDefinition(id="images", type="image", required=True, cardinality="many", label="Images"),
            ],
        ),
        config_schema={
            "mapOver": {"type": "boolean", "default": True},
            "variantCount": {"type": "integer", "default": 1},
        },
        execution=ExecutionHints(mapOver="scene"),
    ),
    "imageToVideo": NodeManifest(
        kind="imageToVideo",
        category="generator",
        label="ImageToVideo",
        description="将图片转为视频片段（支持 mapOver 展开）",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="image", type="image", required=True, label="Image"),
            ],
            outputs=[
                PortDefinition(id="videos", type="video", required=True, cardinality="many", label="Videos"),
            ],
        ),
        config_schema={
            "mapOver": {"type": "boolean", "default": True},
            "duration": {"type": "number", "default": 4},
            "resolution": {"type": "string", "default": "720P"},
        },
        execution=ExecutionHints(mapOver="image"),
    ),
    "videoConcat": NodeManifest(
        kind="videoConcat",
        category="compositor",
        label="VideoConcat",
        description="将多个视频片段拼接为一个完整视频",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="videos", type="video", required=True, cardinality="many", label="Videos"),
            ],
            outputs=[
                PortDefinition(id="video", type="video", required=True, label="Video"),
            ],
        ),
        config_schema={
            "filename": {"type": "string", "default": "output.mp4"},
        },
    ),
    "output": NodeManifest(
        kind="output",
        category="output",
        label="Output",
        description="工作流的终点，输出最终视频",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="video", type="video", required=True, label="Video"),
            ],
            outputs=[],
        ),
    ),
}


# ---------------------------------------------------------------------------
# AgentToolResult
# ---------------------------------------------------------------------------

class AgentToolResult:
    """Standardised result from an agent tool call."""

    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.data = data or {}
        self.error = error

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"AgentToolResult({status}, data={self.data!r}, error={self.error!r})"


# ---------------------------------------------------------------------------
# Tool: list_node_manifests
# ---------------------------------------------------------------------------

def list_node_manifests() -> AgentToolResult:
    """List all available node types with their ports and config schemas."""
    catalog: dict[str, Any] = {}
    for kind, manifest in _NODE_CATALOG_V2.items():
        catalog[kind] = {
            "kind": manifest.kind,
            "label": manifest.label,
            "description": manifest.description,
            "category": manifest.category,
            "inputs": [
                {"id": p.id, "type": p.type, "required": p.required, "cardinality": p.cardinality}
                for p in manifest.ports.inputs
            ],
            "outputs": [
                {"id": p.id, "type": p.type, "required": p.required, "cardinality": p.cardinality}
                for p in manifest.ports.outputs
            ],
            "configSchema": manifest.config_schema,
        }
    return AgentToolResult(success=True, data=catalog)


# ---------------------------------------------------------------------------
# Tool: list_templates
# ---------------------------------------------------------------------------

def list_templates() -> AgentToolResult:
    """List available workflow templates."""
    try:
        from backend.app.services.templates import get_template_service
        svc = get_template_service()
        templates = svc.list_templates()
        return AgentToolResult(
            success=True,
            data={
                "templates": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "description": t.description,
                        "tags": t.tags,
                        "node_count": t.node_count,
                    }
                    for t in templates
                ]
            },
        )
    except Exception as exc:
        return AgentToolResult(success=False, error=f"Failed to list templates: {exc}")


# ---------------------------------------------------------------------------
# Tool: get_node_manifest
# ---------------------------------------------------------------------------

def get_node_manifest(kind: str) -> AgentToolResult:
    """Get detailed manifest for a specific node kind."""
    manifest = _NODE_CATALOG_V2.get(kind)
    if manifest is None:
        available = list(_NODE_CATALOG_V2.keys())
        return AgentToolResult(
            success=False,
            error=f"Unknown node kind '{kind}'. Available: {available}",
        )
    return AgentToolResult(
        success=True,
        data={
            "kind": manifest.kind,
            "label": manifest.label,
            "description": manifest.description,
            "category": manifest.category,
            "version": manifest.version,
            "inputs": [
                {"id": p.id, "type": p.type, "required": p.required, "cardinality": p.cardinality}
                for p in manifest.ports.inputs
            ],
            "outputs": [
                {"id": p.id, "type": p.type, "required": p.required, "cardinality": p.cardinality}
                for p in manifest.ports.outputs
            ],
            "configSchema": manifest.config_schema,
            "execution": {
                "mapOver": manifest.execution.map_over,
                "aggregate": manifest.execution.aggregate,
            } if manifest.execution else None,
        },
    )


# ---------------------------------------------------------------------------
# Tool: validate_intent
# ---------------------------------------------------------------------------

def _types_compatible(src_type: str, tgt_type: str) -> bool:
    """Two port types are compatible when identical or either side is 'any'."""
    return src_type == tgt_type or src_type == "any" or tgt_type == "any"


def validate_intent(intent: WorkflowIntent) -> AgentToolResult:
    """Validate a WorkflowIntent against node manifests.

    Checks:
    - All node kinds exist in NODE_CATALOG
    - All aliases are unique
    - All port references are valid
    - Source port type matches target port type
    - No self-loops
    - No duplicate connections
    - Required ports are connected
    """
    errors: list[dict[str, Any]] = []
    warnings: list[str] = list(intent.warnings)

    # 1. Validate unique aliases
    aliases = [n.alias for n in intent.nodes]
    seen_aliases: set[str] = set()
    for alias in aliases:
        if alias in seen_aliases:
            errors.append({
                "code": "DUPLICATE_ALIAS",
                "message": f"Duplicate node alias '{alias}'",
            })
        seen_aliases.add(alias)

    # 2. Validate node kinds exist
    alias_to_node: dict[str, NodeIntent] = {n.alias: n for n in intent.nodes}
    alias_to_manifest: dict[str, NodeManifest] = {}
    for node in intent.nodes:
        manifest = _NODE_CATALOG_V2.get(node.kind)
        if manifest is None:
            errors.append({
                "code": "UNKNOWN_KIND",
                "message": f"Node '{node.alias}' has unknown kind '{node.kind}'",
                "node": node.alias,
            })
        else:
            alias_to_manifest[node.alias] = manifest

    # 3. Validate connections
    for i, conn in enumerate(intent.connections):
        edge_label = f"connection[{i}]"

        # 3a. Source and target aliases must reference existing nodes
        if conn.source.node not in alias_to_node:
            errors.append({
                "code": "UNKNOWN_NODE",
                "message": f"{edge_label}: source alias '{conn.source.node}' not found",
                "node": conn.source.node,
            })
            continue
        if conn.target.node not in alias_to_node:
            errors.append({
                "code": "UNKNOWN_NODE",
                "message": f"{edge_label}: target alias '{conn.target.node}' not found",
                "node": conn.target.node,
            })
            continue

        # 3b. Self-loop
        if conn.source.node == conn.target.node:
            errors.append({
                "code": "SELF_LOOP",
                "message": f"{edge_label}: connection from '{conn.source.node}' to itself",
                "edge_index": i,
            })

        # 3c. Port validation
        src_manifest = alias_to_manifest.get(conn.source.node)
        tgt_manifest = alias_to_manifest.get(conn.target.node)

        if src_manifest is not None:
            src_port = next(
                (p for p in src_manifest.ports.outputs if p.id == conn.source.port),
                None,
            )
            if src_port is None:
                available = [p.id for p in src_manifest.ports.outputs]
                errors.append({
                    "code": "UNKNOWN_PORT",
                    "message": f"{edge_label}: source port '{conn.source.port}' not found on '{conn.source.node}'. Available: {available}",
                    "node": conn.source.node,
                    "port": conn.source.port,
                })

        if tgt_manifest is not None:
            tgt_port = next(
                (p for p in tgt_manifest.ports.inputs if p.id == conn.target.port),
                None,
            )
            if tgt_port is None:
                available = [p.id for p in tgt_manifest.ports.inputs]
                errors.append({
                    "code": "UNKNOWN_PORT",
                    "message": f"{edge_label}: target port '{conn.target.port}' not found on '{conn.target.node}'. Available: {available}",
                    "node": conn.target.node,
                    "port": conn.target.port,
                })

        # 3d. Type compatibility
        if (
            src_manifest is not None
            and tgt_manifest is not None
        ):
            src_port = next(
                (p for p in src_manifest.ports.outputs if p.id == conn.source.port),
                None,
            )
            tgt_port = next(
                (p for p in tgt_manifest.ports.inputs if p.id == conn.target.port),
                None,
            )
            if src_port is not None and tgt_port is not None:
                if not _types_compatible(src_port.type, tgt_port.type):
                    errors.append({
                        "code": "TYPE_MISMATCH",
                        "message": (
                            f"{edge_label}: port type mismatch -- "
                            f"{conn.source.node}.{conn.source.port} ({src_port.type}) "
                            f"-> {conn.target.node}.{conn.target.port} ({tgt_port.type})"
                        ),
                        "edge_index": i,
                    })

    # 4. Duplicate connection check
    seen_conns: set[tuple[str, str, str, str]] = set()
    for conn in intent.connections:
        key = (conn.source.node, conn.source.port, conn.target.node, conn.target.port)
        if key in seen_conns:
            errors.append({
                "code": "DUPLICATE_CONNECTION",
                "message": f"Duplicate connection: {conn.source.node}.{conn.source.port} -> {conn.target.node}.{conn.target.port}",
            })
        seen_conns.add(key)

    # 5. Required port check -- warn about unconnected required input ports
    connected_target_ports: set[tuple[str, str]] = set()
    for conn in intent.connections:
        connected_target_ports.add((conn.target.node, conn.target.port))

    for node in intent.nodes:
        manifest = alias_to_manifest.get(node.alias)
        if manifest is None:
            continue
        for port in manifest.ports.inputs:
            if port.required and (node.alias, port.id) not in connected_target_ports:
                #textInput nodes have no required input ports so this won't fire for them
                warnings.append(
                    f"Node '{node.alias}' has unconnected required input port '{port.id}'"
                )

    if errors:
        return AgentToolResult(
            success=False,
            data={"errors": errors, "warnings": warnings},
            error=f"Validation failed with {len(errors)} error(s)",
        )
    return AgentToolResult(
        success=True,
        data={"errors": [], "warnings": warnings},
    )


# ---------------------------------------------------------------------------
# Tool: estimate_calls
# ---------------------------------------------------------------------------

def estimate_calls(intent: WorkflowIntent) -> AgentToolResult:
    """Estimate the number of API calls this workflow will make.

    Based on:
    - Number of scenes
    - Variant count
    - mapOver nodes (textToImage, imageToVideo)
    - Provider costs
    """
    scene_count = intent.scene_count or _infer_scene_count(intent)
    variant_count = intent.variant_count or 1
    image_calls = 0
    video_calls = 0
    other_calls: list[str] = []

    alias_to_node: dict[str, NodeIntent] = {n.alias: n for n in intent.nodes}

    for node in intent.nodes:
        if node.kind == "textToImage":
            # Each scene generates variant_count images
            image_calls = scene_count * variant_count
        elif node.kind == "imageToVideo":
            # Each image generates a video
            video_calls = scene_count * variant_count
        elif node.kind == "storyboard":
            other_calls.append(f"storyboard({scene_count} scenes)")
        elif node.kind == "videoConcat":
            other_calls.append("videoConcat(1)")

    total = image_calls + video_calls + len(other_calls)

    return AgentToolResult(
        success=True,
        data={
            "scene_count": scene_count,
            "variant_count": variant_count,
            "image_calls": image_calls,
            "video_calls": video_calls,
            "other_calls": other_calls,
            "total_estimated_calls": total,
            "estimated_cost_hint": f"~{total} API calls",
        },
    )


def _infer_scene_count(intent: WorkflowIntent) -> int:
    """Try to infer scene count from node configs or connections."""
    for node in intent.nodes:
        if node.kind == "storyboard":
            scenes = node.config.get("scenes")
            if isinstance(scenes, int) and scenes > 0:
                return scenes
    return 1  # default


# ---------------------------------------------------------------------------
# Utility: intent_to_compact_prompt
# ---------------------------------------------------------------------------

def intent_to_compact_prompt(intent: WorkflowIntent) -> str:
    """Convert a WorkflowIntent to a compact text representation for the LLM.

    Example::

        "Workflow: 滑雪教学
         Nodes: story(storyboard) -> img(textToImage) -> vid(imageToVideo) -> concat(videoConcat) -> out(output)
         Connections: story.scenes -> img.scene [map], img.images -> vid.image [map], vid.videos -> concat.videos [many]"
    """
    parts: list[str] = [f"Workflow: {intent.name}"]

    if intent.description:
        parts.append(f"  Description: {intent.description}")

    # Node list
    node_strs = [f"{n.alias}({n.kind})" for n in intent.nodes]
    parts.append(f"  Nodes: {' -> '.join(node_strs)}")

    # Connection list
    if intent.connections:
        conn_strs = []
        for c in intent.connections:
            mode_tag = f" [{c.mode}]" if c.mode != "direct" else ""
            conn_strs.append(
                f"{c.source.node}.{c.source.port} -> {c.target.node}.{c.target.port}{mode_tag}"
            )
        parts.append(f"  Connections: {', '.join(conn_strs)}")

    # Constraints
    constraints: list[str] = []
    if intent.scene_count is not None:
        constraints.append(f"scenes={intent.scene_count}")
    if intent.variant_count is not None:
        constraints.append(f"variants={intent.variant_count}")
    if intent.duration is not None:
        constraints.append(f"duration={intent.duration}s")
    if intent.resolution:
        constraints.append(f"resolution={intent.resolution}")
    if constraints:
        parts.append(f"  Constraints: {', '.join(constraints)}")

    # Warnings
    if intent.warnings:
        parts.append(f"  Warnings: {'; '.join(intent.warnings)}")

    return "\n".join(parts)
