"""Modules API — module definition management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.schemas.module_definition import ModuleDefinition
from backend.app.services.module_registry import get_module_registry


router = APIRouter(prefix="/api/modules", tags=["modules"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UpdateDraftRequest(BaseModel):
    """Request body for updating a draft module."""

    definition: ModuleDefinition
    expected_version: int = Field(..., alias="expectedVersion")


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
async def publish(module_id: str) -> ModuleDefinition:
    """Publish a draft module. expected_version is auto-resolved from DB."""
    registry = get_module_registry()
    module = registry.get_module(module_id)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.publish_draft(module_id, module.version)
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        raise HTTPException(400, str(e))


@router.post("/{module_id}/archive")
async def archive(module_id: str) -> ModuleDefinition:
    """Archive a published module. expected_version is auto-resolved from DB."""
    registry = get_module_registry()
    module = registry.get_module(module_id)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.archive_draft(module_id, module.version)
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        raise HTTPException(400, str(e))


@router.post("/{module_id}/clone", status_code=201)
async def clone_module(module_id: str) -> ModuleDefinition:
    """Clone a module into a new draft with incremented version."""
    registry = get_module_registry()
    module = registry.get_module(module_id)
    if not module:
        raise HTTPException(404, f"Module not found: {module_id}")
    try:
        return registry.clone_draft(module_id, module.version)
    except Exception as e:
        from backend.app.repositories.module_repository import ConflictError, ModuleNotFoundError

        if isinstance(e, ConflictError):
            raise HTTPException(409, str(e))
        if isinstance(e, ModuleNotFoundError):
            raise HTTPException(404, str(e))
        raise HTTPException(400, str(e))
