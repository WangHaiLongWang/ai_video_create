from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .node_manifest import PortDefinition, ExecutionHints


class ProviderPolicy(BaseModel):
    """Controls which providers are allowed for a given capability."""

    capability: str = ""  # "text", "image", "video"
    allowed: list[str] = Field(default_factory=list)
    default: str | None = None
    locked: bool = False


class ModuleDefinition(BaseModel):
    """Defines a reusable node module that can be instantiated in workflows."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # e.g. "builtin.seedream.text-to-image"
    version: str  # semver
    status: Literal["draft", "published", "archived"] = "draft"
    expected_version: int = Field(default=1, alias="expectedVersion", ge=1)
    base_kind: str = Field(alias="baseKind")  # must match existing NodeKind
    category: str  # "input", "transform", "image", "video", "output"
    label: str
    description: str = ""
    icon: str = "puzzle-piece"
    provider_policy: ProviderPolicy = Field(
        default_factory=ProviderPolicy, alias="providerPolicy"
    )
    config_schema: dict = Field(default_factory=dict, alias="configSchema")
    default_config: dict = Field(default_factory=dict, alias="defaultConfig")
    ports: dict = Field(default_factory=lambda: {"inputs": [], "outputs": []})
    execution: ExecutionHints | None = None
    metadata: dict = Field(default_factory=dict)


class NodeInstanceData(BaseModel):
    """Extension to existing NodeData for module references."""

    module_id: str | None = Field(default=None, alias="moduleId")
    module_version: str | None = Field(default=None, alias="moduleVersion")
    config_overrides: dict = Field(default_factory=dict, alias="configOverrides")
