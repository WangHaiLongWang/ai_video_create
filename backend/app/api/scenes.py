"""Scene API — Scene Draft CRUD and export endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..schemas.scene_bundle import ScenePromptBundle
from ..schemas.scene_exporter import (
    export_to_csv,
    export_to_json,
    export_to_markdown,
    export_to_text,
    export_to_qwen_jsonl,
    export_to_wan3_jsonl,
    scan_bundle_security,
)
from ..services.scene_service import SceneService

router = APIRouter(prefix="/api", tags=["scenes"])

# Singleton service
_scene_service = SceneService()


class CreateDraftRequest(BaseModel):
    bundle: dict[str, Any]


class UpdateDraftRequest(BaseModel):
    bundle: dict[str, Any] | None = None
    name: str | None = None
    source: str | None = None


class UpdateSceneRequest(BaseModel):
    updates: dict[str, Any]


class ImportBundleRequest(BaseModel):
    bundle: dict[str, Any]


class MergeExecutionRequest(BaseModel):
    execution_bundle: dict[str, Any]


class LockSceneByIndexRequest(BaseModel):
    pass  # No body needed, scene_index in URL


class LockSceneByIdRequest(BaseModel):
    scene_id: str


# ---------------------------------------------------------------------------
# Draft CRUD
# ---------------------------------------------------------------------------


@router.post("/workflows/{workflow_id}/scene-drafts")
async def create_scene_draft(workflow_id: str, req: CreateDraftRequest) -> dict[str, Any]:
    """Create a new scene draft from a bundle."""
    try:
        bundle = ScenePromptBundle(**req.bundle)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid bundle: {e}")

    draft_id = _scene_service.create_draft(bundle, workflow_id=workflow_id)
    return {"draft_id": draft_id, "workflow_id": workflow_id, "scene_count": len(bundle.scenes)}


@router.get("/workflows/{workflow_id}/scene-drafts")
async def list_scene_drafts(workflow_id: str) -> list[dict[str, Any]]:
    """List all scene drafts for a workflow."""
    return _scene_service.list_drafts(workflow_id=workflow_id)


@router.get("/workflows/{workflow_id}/scene-drafts/{draft_id}")
async def get_scene_draft(workflow_id: str, draft_id: str) -> dict[str, Any]:
    """Get a specific scene draft."""
    bundle = _scene_service.get_draft(draft_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
    return bundle.model_dump(by_alias=True)


@router.put("/workflows/{workflow_id}/scene-drafts/{draft_id}")
async def update_scene_draft(
    workflow_id: str,
    draft_id: str,
    req: UpdateDraftRequest,
) -> dict[str, Any]:
    """Update a scene draft's metadata (name, source) or replace the entire bundle."""
    from ..repositories import scene_drafts as repo

    try:
        record = repo.get_draft(draft_id)
    except repo.SceneDraftNotFoundError:
        raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")

    kwargs: dict[str, Any] = {"draft_id": draft_id, "expected_version": record["version"]}
    if req.name is not None:
        kwargs["name"] = req.name
    if req.source is not None:
        kwargs["source"] = req.source
    if req.bundle is not None:
        kwargs["bundle_dict"] = req.bundle

    try:
        updated = repo.update_draft(**kwargs)
    except repo.OptimisticLockError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"ok": True, "draft_id": draft_id, "version": updated["version"]}


@router.delete("/workflows/{workflow_id}/scene-drafts/{draft_id}")
async def delete_scene_draft(workflow_id: str, draft_id: str) -> dict[str, Any]:
    """Delete a scene draft."""
    success = _scene_service.delete_draft(draft_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
    return {"ok": True, "deleted": draft_id}


@router.put("/workflows/{workflow_id}/scene-drafts/{draft_id}/scenes/{scene_index}")
async def update_scene(
    workflow_id: str,
    draft_id: str,
    scene_index: int,
    req: UpdateSceneRequest,
) -> dict[str, Any]:
    """Update a specific scene's fields by index."""
    success = _scene_service.update_scene(draft_id, scene_index, req.updates)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Draft '{draft_id}' or scene index {scene_index} not found",
        )
    return {"ok": True, "draft_id": draft_id, "scene_index": scene_index}


@router.post("/workflows/{workflow_id}/scene-drafts/{draft_id}/scenes/{scene_index}/lock")
async def lock_scene(workflow_id: str, draft_id: str, scene_index: int) -> dict[str, Any]:
    """Lock a scene to prevent regeneration overwrites."""
    success = _scene_service.lock_scene(draft_id, scene_index)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Draft '{draft_id}' or scene index {scene_index} not found",
        )
    return {"ok": True, "locked": True}


@router.post("/workflows/{workflow_id}/scene-drafts/{draft_id}/scenes/{scene_index}/unlock")
async def unlock_scene(workflow_id: str, draft_id: str, scene_index: int) -> dict[str, Any]:
    """Unlock a scene to allow regeneration."""
    success = _scene_service.unlock_scene(draft_id, scene_index)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Draft '{draft_id}' or scene index {scene_index} not found",
        )
    return {"ok": True, "locked": False}


@router.post("/workflows/{workflow_id}/scene-drafts/import")
async def import_scene_bundle(workflow_id: str, req: ImportBundleRequest) -> dict[str, Any]:
    """Import an external bundle as a new draft."""
    try:
        bundle = ScenePromptBundle(**req.bundle)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid bundle: {e}")

    draft_id = _scene_service.import_bundle(bundle, workflow_id=workflow_id)
    return {"draft_id": draft_id, "workflow_id": workflow_id, "scene_count": len(bundle.scenes)}


@router.post("/workflows/{workflow_id}/scene-drafts/{draft_id}/merge")
async def merge_execution(
    workflow_id: str,
    draft_id: str,
    req: MergeExecutionRequest,
) -> dict[str, Any]:
    """Merge execution results with the draft, respecting locked scenes."""
    try:
        exec_bundle = ScenePromptBundle(**req.execution_bundle)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid execution bundle: {e}")

    merged = _scene_service.merge_execution(draft_id, exec_bundle)
    return merged.model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# Export / Validate
# ---------------------------------------------------------------------------

_EXPORT_FORMATS = {
    "json": export_to_json,
    "markdown": export_to_markdown,
    "csv": export_to_csv,
    "text": export_to_text,
    "qwen_jsonl": export_to_qwen_jsonl,
    "wan3_jsonl": export_to_wan3_jsonl,
}


@router.get("/scene-bundles/{bundle_id}/export")
async def export_scene_bundle(bundle_id: str, format: str = "json") -> dict[str, Any]:
    """Export scene bundle in specified format.

    Supported formats: json | markdown | csv | text | qwen_jsonl | wan3_jsonl
    """
    if format not in _EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{format}'. Supported: {', '.join(_EXPORT_FORMATS)}",
        )

    bundle = _scene_service.get_draft(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Bundle '{bundle_id}' not found")

    exporter = _EXPORT_FORMATS[format]
    content = exporter(bundle)

    content_type = "application/json" if format == "json" else "text/plain; charset=utf-8"

    return {"format": format, "content": content, "bundle_id": bundle_id}


@router.post("/scene-bundles/{bundle_id}/validate")
async def validate_scene_bundle(bundle_id: str) -> dict[str, Any]:
    """Run security validation on a scene bundle."""
    bundle = _scene_service.get_draft(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Bundle '{bundle_id}' not found")

    issues = scan_bundle_security(bundle)
    return {
        "bundle_id": bundle_id,
        "valid": len(issues) == 0,
        "issue_count": len(issues),
        "issues": [issue.model_dump() for issue in issues],
    }
