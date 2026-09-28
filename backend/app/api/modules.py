"""Modules API — module definition management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.module_definition import ModuleDefinition
from backend.app.services.module_diff import ModuleDiff, compute_module_diff, check_config_compatibility
from backend.app.services.module_registry import get_module_registry


router = APIRouter(prefix="/api/modules", tags=["modules"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UpdateDraftRequest(BaseModel):
    """Request body for updating a draft module."""

    model_config = ConfigDict(populate_by_name=True)

    definition: ModuleDefinition
    expected_version: int = Field(..., alias="expectedVersion")


class ModuleMutationRequest(BaseModel):
    """Optimistic-lock token and optional exact version for lifecycle writes."""

    model_config = ConfigDict(populate_by_name=True)

    version: str | None = None
    expected_version: int | None = Field(default=None, alias="expectedVersion")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_modules(
    status: str | None = Query(default=None, description="Filter by status"),
    capability: str | None = Query(default=None, description="Filter by capability"),
) -> list[ModuleDefinition]:
    """List all module definitions (merged builtin + persisted)."""
    registry = get_module_registry()
    return registry.list_modules(status=status, capability=capability)


@router.get("/{module_id}")
async def get_module(module_id: str) -> ModuleDefinition:
    """Get module details (latest version)."""
    registry = get_module_registry()
    module = registry.get_module(module_id)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    return module


@router.get("/{module_id}/versions/{version}")
async def get_module_version(module_id: str, version: str) -> ModuleDefinition:
    """Get a specific version of a module."""
    registry = get_module_registry()
    module = registry.get_module(module_id, version=version)
    if not module:
        raise HTTPException(404, f"Module version not found: {module_id}@{version}")
    return module


# ---------------------------------------------------------------------------
# Diff / Compatibility
# ---------------------------------------------------------------------------


class ConfigCompatRequest(BaseModel):
    """Request body for config compatibility check."""

    old_config: dict = Field(..., alias="oldConfig")
    old_schema: dict = Field(..., alias="oldSchema")
    new_schema: dict = Field(..., alias="newSchema")


@router.get("/{module_id}/diff")
async def diff_modules(
    module_id: str,
    from_version: str = Query(..., alias="from", description="Source version (semver)"),
    to_version: str = Query(..., alias="to", description="Target version (semver)"),
) -> dict:
    """Get structural diff between two module versions."""
    registry = get_module_registry()
    old = registry.get_module(module_id, version=from_version)
    if not old:
        raise HTTPException(
            404, f"Module version not found: {module_id}@{from_version}"
        )
    new = registry.get_module(module_id, version=to_version)
    if not new:
        raise HTTPException(
            404, f"Module version not found: {module_id}@{to_version}"
        )
    diff = compute_module_diff(old, new)
    return diff.to_dict()


@router.post("/{module_id}/compat-check")
async def compat_check(
    module_id: str, body: ConfigCompatRequest
) -> dict:
    """Check if existing config overrides are compatible with a new schema."""
    messages = check_config_compatibility(
        body.old_config, body.old_schema, body.new_schema
    )
    return {"compatible": len(messages) == 0, "messages": messages}


@router.post("", status_code=201)
async def create_draft(definition: ModuleDefinition) -> ModuleDefinition:
    """Create a new draft module definition."""
    registry = get_module_registry()
    try:
        return registry.create_draft(definition)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{module_id}/draft")
async def update_draft(module_id: str, body: UpdateDraftRequest) -> ModuleDefinition:
    """Update a draft module definition (optimistic lock)."""
    registry = get_module_registry()
    try:
        return registry.update_draft(
            module_id,
            body.definition.version,
            body.definition,
            body.expected_version,
        )
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError, ModuleNotFoundError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        if isinstance(e, ModuleNotFoundError):
            raise HTTPException(404, str(e))
        raise HTTPException(400, str(e))


@router.post("/{module_id}/publish")
async def publish(
    module_id: str, body: ModuleMutationRequest | None = None
) -> ModuleDefinition:
    """Publish a draft module. expected_version is auto-resolved from DB."""
    registry = get_module_registry()
    module = registry.get_module(module_id, version=body.version if body else None)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.publish_draft(
            module_id, module.version, body.expected_version if body else None
        )
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError
        from backend.app.services.module_registry import ModuleValidationError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        if isinstance(e, ModuleValidationError):
            raise HTTPException(
                422, {"code": "MODULE_VALIDATION_FAILED", "errors": e.errors}
            )
        raise HTTPException(400, str(e))


@router.post("/{module_id}/archive")
async def archive(
    module_id: str, body: ModuleMutationRequest | None = None
) -> ModuleDefinition:
    """Archive a published module. expected_version is auto-resolved from DB."""
    registry = get_module_registry()
    module = registry.get_module(module_id, version=body.version if body else None)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.archive_draft(
            module_id, module.version, body.expected_version if body else None
        )
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        raise HTTPException(400, str(e))


@router.post("/{module_id}/clone", status_code=201)
async def clone_module(
    module_id: str, body: ModuleMutationRequest | None = None
) -> ModuleDefinition:
    """Clone a module into a new draft with incremented version."""
    registry = get_module_registry()
    module = registry.get_module(module_id, version=body.version if body else None)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.clone_draft(
            module_id, module.version, body.expected_version if body else None
        )
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError, ModuleNotFoundError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        if isinstance(e, ModuleNotFoundError):
            raise HTTPException(404, str(e))
        raise HTTPException(400, str(e))
