"""WorkflowIntent -- structured output from the Agent.

Instead of having the LLM generate raw React Flow JSON (nodes, edges, coordinates),
the Agent outputs a high-level WorkflowIntent with aliases and connections.
The backend Compiler then translates this into stable IDs, React Flow edges, and positions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PortRef(BaseModel):
    """Reference to a node port by alias and port ID."""

    node: str = Field(..., description="Node alias, e.g. 'story'")
    port: str = Field(..., description="Port ID, e.g. 'scenes'")


class ConnectionIntent(BaseModel):
    """A connection between two ports."""

    source: PortRef
    target: PortRef
    mode: str = Field(
        "direct",
        description="Connection mode: 'direct', 'map', 'aggregate'",
    )


class NodeIntent(BaseModel):
    """A node in the workflow, specified by kind and config."""

    alias: str = Field(..., description="Unique alias for this node, e.g. 'story'")
    kind: str = Field(..., description="Node kind from NODE_CATALOG")
    config: dict = Field(default_factory=dict, description="Node configuration overrides")
    label: Optional[str] = Field(None, description="Display label override")
    description: Optional[str] = Field(None, description="Description override")


class WorkflowIntent(BaseModel):
    """High-level workflow specification from the Agent.

    The Compiler translates this into a full WorkflowSpecV2 with:
    - Stable UUIDs for nodes
    - React Flow edges with sourceHandle/targetHandle
    - Computed positions (layout service)
    - Port compatibility validation
    """

    name: str = Field(..., description="Workflow display name")
    description: Optional[str] = Field(None, description="Workflow description")
    template_id: Optional[str] = Field(None, description="Template to base this on")
    nodes: list[NodeIntent] = Field(..., min_length=1, description="Nodes to create")
    connections: list[ConnectionIntent] = Field(
        default_factory=list,
        description="Connections between ports",
    )
    tags: list[str] = Field(default_factory=list, description="Workflow tags")

    # Constraints the Agent extracted from user prompt
    scene_count: Optional[int] = Field(None, description="Number of scenes (from prompt)")
    variant_count: Optional[int] = Field(None, description="Variants per scene")
    duration: Optional[int] = Field(None, description="Video duration in seconds")
    resolution: Optional[str] = Field(None, description="Output resolution")

    # Warnings from the Agent
    warnings: list[str] = Field(
        default_factory=list,
        description="Uncertainty warnings",
    )
