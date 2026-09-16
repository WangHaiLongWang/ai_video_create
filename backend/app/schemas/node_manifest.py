from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PortDefinition(BaseModel):
    """Definition of a single input or output port on a node."""

    id: str
    type: Literal["text", "scene", "image", "video", "audio", "asset", "any"]
    required: bool = False
    cardinality: Literal["one", "many"] = "one"
    label: str | None = None


class PortGroup(BaseModel):
    """Group of input and output port definitions."""

    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)


class ExecutionHints(BaseModel):
    """Hints for the execution engine about how to process ports."""

    map_over: str | None = Field(default=None, alias="mapOver")
    aggregate: str | None = Field(default=None, alias="aggregate")


class NodeManifest(BaseModel):
    """Complete manifest describing a node kind."""

    kind: str
    version: str = "1.0"
    category: str
    label: str
    description: str = ""
    ports: PortGroup
    config_schema: dict = Field(default_factory=dict, alias="configSchema")
    execution: ExecutionHints | None = None
