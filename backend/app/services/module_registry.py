"""Module Registry — manages built-in and custom module definitions."""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_port_validator import PortBindingValidator, PortError
from backend.app.services.module_security import validate_module_security


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
    """Registry for module definitions.

    Optionally backed by a :class:`ModuleRepository` for persistent storage.
    When a repository is provided, list/get queries merge builtin modules with
    database-stored modules.  ``create_draft``, ``publish``, and ``archive``
    delegate to the repository.
    """

    def __init__(self, repository: Any | None = None) -> None:
        self._repository = repository
        self._modules: dict[str, dict[str, ModuleDefinition]] = {}
        # Load built-in modules
        for module_id, module in BUILTIN_MODULES.items():
            self._modules.setdefault(module_id, {})[module.version] = module

    # ------------------------------------------------------------------
    # Query helpers (builtin + DB merge)
    # ------------------------------------------------------------------

    def _all_modules(self) -> dict[str, dict[str, ModuleDefinition]]:
        """Return combined in-memory + DB module map."""
        combined: dict[str, dict[str, ModuleDefinition]] = {}
        # In-memory modules (includes builtins loaded in __init__)
        for module_id, versions in self._modules.items():
            combined.setdefault(module_id, {}).update(versions)
        # DB modules
        if self._repository is not None:
            db_modules = self._repository.list_modules()
            for m in db_modules:
                combined.setdefault(m.id, {})[m.version] = m
        return combined

    def list_modules(
        self,
        status: str | None = None,
        capability: str | None = None,
    ) -> list[ModuleDefinition]:
        """Return modules, optionally filtered by status or capability."""
        combined = self._all_modules()
        result: list[ModuleDefinition] = []
        for versions in combined.values():
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
        combined = self._all_modules()
        versions = combined.get(module_id)
        if not versions:
            return None
        if version:
            return versions.get(version)
        return max(versions.values(), key=lambda m: m.version)

    # ------------------------------------------------------------------
    # Mutation helpers (delegate to repository)
    # ------------------------------------------------------------------

    def create_draft(self, definition: ModuleDefinition) -> ModuleDefinition:
        """Create a new draft module definition.

        Requires a repository to be configured.
        """
        if self._repository is None:
            raise RuntimeError("Repository not configured — cannot persist modules")
        return self._repository.create_draft(definition)

    def update_draft(
        self,
        module_id: str,
        version: str,
        definition: ModuleDefinition,
        expected_version: int,
    ) -> ModuleDefinition:
        """Update a draft module with optimistic locking."""
        if self._repository is None:
            raise RuntimeError("Repository not configured — cannot persist modules")
        return self._repository.update_draft(module_id, version, definition, expected_version)

    def publish_draft(
        self, module_id: str, version: str, expected_version: int | None = None
    ) -> ModuleDefinition:
        """Publish a draft module via the repository (persistent storage)."""
        if self._repository is None:
            raise RuntimeError("Repository not configured — cannot persist modules")
        return self._repository.publish(module_id, version, expected_version)

    def archive_draft(
        self, module_id: str, version: str, expected_version: int | None = None
    ) -> ModuleDefinition:
        """Archive a published module via the repository (persistent storage)."""
        if self._repository is None:
            raise RuntimeError("Repository not configured — cannot persist modules")
        return self._repository.archive(module_id, version, expected_version)

    def clone_draft(
        self, module_id: str, version: str, expected_version: int | None = None
    ) -> ModuleDefinition:
        """Clone a module into a new draft with incremented version."""
        source = self.get_module(module_id, version)
        if source is None:
            from backend.app.repositories.module_repository import ModuleNotFoundError
            raise ModuleNotFoundError(f"Module not found: {module_id}@{version}")

        # New ID with -copy suffix, increment version: 1.0.0 → 1.0.1
        new_id = f"{source.id}-copy"
        parts = source.version.split(".")
        parts[2] = str(int(parts[2]) + 1)
        new_version = ".".join(parts)

        cloned = ModuleDefinition(
            id=new_id,
            version=new_version,
            status="draft",
            base_kind=source.base_kind,
            category=source.category,
            label=f"{source.label} (copy)",
            description=source.description,
            icon=source.icon,
            provider_policy=source.provider_policy,
            config_schema=source.config_schema,
            default_config=source.default_config,
            ports=source.ports,
            execution=source.execution,
            metadata={**source.metadata, "cloned_from": f"{module_id}@{version}"},
        )

        if self._repository is not None:
            return self._repository.create_draft(cloned)

        # In-memory fallback when no repository is configured
        self._modules[cloned.id] = cloned
        return cloned

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_module(
        self, module_definition: ModuleDefinition
    ) -> list[str | dict[str, str]]:
        """Validate a module definition, returning a list of error messages.

        Includes basic field validation and port binding validation.
        Returns an empty list if the definition is valid.
        """
        errors: list[str | dict[str, str]] = []

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

        # Port binding validation
        port_errors = PortBindingValidator().validate_ports(module_definition)
        for pe in port_errors:
            errors.append(
                {
                    "field": pe.field,
                    "error": pe.error,
                    "message": pe.message,
                }
            )

        # Security validation
        security_violations = validate_module_security(module_definition)
        for sv in security_violations:
            errors.append(
                {
                    "field": sv.field,
                    "error": sv.rule,
                    "message": sv.message,
                    "severity": sv.severity,
                }
            )

        return errors

    def publish(
        self, module_definition: ModuleDefinition
    ) -> tuple[bool, list[str | dict[str, str]]]:
        """Attempt to publish a module definition.

        Returns (success, errors). Cannot publish if there are any validation
        errors with severity "error".  Warnings are included in the response
        but do not block publishing.
        """
        errors = self.validate_module(module_definition)
        # Block only on errors (severity == "error" or no severity field for legacy errors)
        blocking = [
            e
            for e in errors
            if not isinstance(e, dict) or e.get("severity", "error") == "error"
        ]
        if blocking:
            return False, errors

        # Set status to published and register
        module_definition.status = "published"
        self._modules.setdefault(module_definition.id, {})[
            module_definition.version
        ] = module_definition
        return True, errors

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
