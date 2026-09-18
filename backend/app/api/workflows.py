"""Workflow CRUD REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from backend.app.domain.graph_validation import (
    extract_nodes_edges_from_spec,
    raise_if_invalid,
)
from backend.app.models import WorkflowSpec
from backend.app.repositories.workflows import (
    OptimisticLockError,
    WorkflowNotFoundError,
    create_workflow,
    delete_workflow,
    duplicate_workflow,
    get_workflow,
    list_workflows,
    update_workflow,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    version: int
    created_at: str
    updated_at: str


class WorkflowDetail(BaseModel):
    id: str
    name: str
    description: str = ""
    version: int
    spec: dict
    created_at: str
    updated_at: str


class UpdateRequest(BaseModel):
    spec: dict
    expected_version: int


class DuplicateRequest(BaseModel):
    name: str | None = None


# --- Routes ---


@router.get("", response_model=list[WorkflowSummary])
def api_list_workflows() -> list[dict]:
    return list_workflows()


@router.post("", response_model=WorkflowSummary, status_code=201)
def api_create_workflow(spec: WorkflowSpec) -> dict:
    nodes, edges = extract_nodes_edges_from_spec(spec.model_dump())
    raise_if_invalid(nodes, edges)
    return create_workflow(spec.model_dump())


@router.get("/{workflow_id}", response_model=WorkflowDetail)
def api_get_workflow(workflow_id: str) -> dict:
    try:
        return get_workflow(workflow_id)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{workflow_id}", response_model=WorkflowSummary)
def api_update_workflow(workflow_id: str, body: UpdateRequest) -> dict:
    nodes, edges = extract_nodes_edges_from_spec(body.spec)
    raise_if_invalid(nodes, edges)
    try:
        return update_workflow(workflow_id, body.spec, body.expected_version)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OptimisticLockError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{workflow_id}", status_code=204, response_class=Response)
def api_delete_workflow(workflow_id: str) -> Response:
    try:
        delete_workflow(workflow_id)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(status_code=204)


@router.post("/{workflow_id}/duplicate", response_model=WorkflowSummary, status_code=201)
def api_duplicate_workflow(workflow_id: str, body: DuplicateRequest | None = None) -> dict:
    name = body.name if body else None
    try:
        return duplicate_workflow(workflow_id, new_name=name)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{workflow_id}/export")
def api_export_workflow(workflow_id: str) -> dict:
    try:
        wf = get_workflow(workflow_id)
        return {"spec": wf["spec"]}
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/import", response_model=WorkflowSummary, status_code=201)
def api_import_workflow(spec: WorkflowSpec) -> dict:
    nodes, edges = extract_nodes_edges_from_spec(spec.model_dump())
    raise_if_invalid(nodes, edges)
    return create_workflow(spec.model_dump())
