from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from .node_manifest import PortDefinition, ExecutionHints


class ProviderPolicy(BaseModel):
    """Controls which providers are allowed for a given capability."""

    capability: str = ""  # "text", "image", "video"
    allowed: list[str] = Field(default_factory=list)
    default: str | None = None
    locked: bool = False
    provider_config_id: str | None = Field(default=None, alias="providerConfigId")


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

    @model_validator(mode="after")
    def _remove_persisted_credentials(self) -> "ModuleDefinition":
        """Module definitions reference profiles; credentials live separately."""
        secret_names = {
            "api_key", "access_token", "secret", "password", "token",
            "api_url", "base_url", "endpoint_url",
        }

        def clean(value):
            if isinstance(value, dict):
                return {
                    key: clean(item)
                    for key, item in value.items()
                    if str(key).lower() not in secret_names
                    and not str(key).lower().endswith("_api_key")
                }
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value

        self.default_config = clean(self.default_config)
        return self


class NodeInstanceData(BaseModel):
    """Extension to existing NodeData for module references."""

    module_id: str | None = Field(default=None, alias="moduleId")
    module_version: str | None = Field(default=None, alias="moduleVersion")
    config_overrides: dict = Field(default_factory=dict, alias="configOverrides")
