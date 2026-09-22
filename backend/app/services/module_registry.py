"""Module Registry — manages built-in and custom module definitions."""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints


# ---------------------------------------------------------------------------
# Built-in Module Definitions
# ---------------------------------------------------------------------------

BUILTIN_MODULES: dict[str, ModuleDefinition] = {}


def _register_builtin(module: ModuleDefinition) -> None:
    BUILTIN_MODULES[module.id] = module


_register_builtin(
    ModuleDefinition(
        id="builtin.seedream.text-to-image",
        version="1.0.0",
        status="published",
        baseKind="textToImage",
        category="image",
        label="Seedream 文生图",
        description="使用豆包 Seedream 模型从文本生成图片",
        icon="image",
        providerPolicy=ProviderPolicy(
            capability="image",
            allowed=["doubao"],
            default="doubao",
            locked=True,
        ),
        configSchema={
            "properties": {
                "image_model": {"type": "string", "title": "模型"},
                "size": {"type": "string", "title": "尺寸", "default": "1280x720"},
                "negative_prompt": {"type": "string", "title": "反向提示词", "default": ""},
                "seed": {"type": "integer", "title": "随机种子", "default": -1},
                "watermark": {"type": "boolean", "title": "水印", "default": False},
                "variantCount": {"type": "integer", "title": "变体数量", "default": 1},
            },
            "required": ["image_model"],
        },
        defaultConfig={
            "provider": "doubao",
            "image_model": "doubao-seedream-5-0-pro-260628",
            "size": "1280x720",
            "mapOver": True,
        },
        ports={
            "inputs": [
                {"id": "scene", "type": "scene", "required": True, "cardinality": "one", "label": "场景"}
            ],
            "outputs": [
                {"id": "image", "type": "image", "required": False, "cardinality": "one", "label": "图片"}
            ],
        },
        execution=ExecutionHints(**{"mapOver": "scene"}),
        metadata={"builtin": True, "author": "system"},
    )
)

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$")


class ModuleRegistry:
    """In-memory registry for module definitions."""

    def __init__(self) -> None:
        self._modules: dict[str, dict[str, ModuleDefinition]] = {}
        # Load built-in modules
        for module_id, module in BUILTIN_MODULES.items():
            self._modules.setdefault(module_id, {})[module.version] = module

    def list_modules(
        self,
        status: str | None = None,
        capability: str | None = None,
    ) -> list[ModuleDefinition]:
        """Return modules, optionally filtered by status or capability."""
        result: list[ModuleDefinition] = []
        for versions in self._modules.values():
            # Pick the latest version for each module
            latest = max(versions.values(), key=lambda m: m.version)
            if status and latest.status != status:
                continue
            if capability and latest.provider_policy.capability != capability:
                continue
            result.append(latest)
        return result

    def get_module(
        self, module_id: str, version: str | None = None
    ) -> ModuleDefinition | None:
        """Get a specific module, optionally at a specific version."""
        versions = self._modules.get(module_id)
        if not versions:
            return None
        if version:
            return versions.get(version)
        return max(versions.values(), key=lambda m: m.version)

    def validate_module(self, module_definition: ModuleDefinition) -> list[str]:
        """Validate a module definition, returning a list of error messages.

        Returns an empty list if the definition is valid.
        """
        errors: list[str] = []

        if not module_definition.base_kind:
            errors.append("base_kind is required")

        if not _SEMVER_RE.match(module_definition.version):
            errors.append(
                f"Invalid version format: {module_definition.version!r} "
                "(expected semver, e.g. 1.0.0)"
            )

        if not module_definition.id:
            errors.append("id is required")

        if not module_definition.label:
            errors.append("label is required")

        if not module_definition.category:
            errors.append("category is required")

        return errors

    def resolve_effective_config(
        self,
        module_id: str,
        instance_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge module defaultConfig with instance-level overrides.

        Returns the resulting config dict.
        """
        module = self.get_module(module_id)
        if module is None:
            raise KeyError(f"Module not found: {module_id}")

        merged = dict(module.default_config)
        if instance_overrides:
            merged.update(instance_overrides)
        return merged


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_registry: ModuleRegistry | None = None


def get_module_registry() -> ModuleRegistry:
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry
