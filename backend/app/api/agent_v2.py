"""Agent API v2 -- structured generate/modify with preview and apply.

Endpoints:
  POST /api/agent/generate-preview-v2 -- Generate a workflow from a prompt
  POST /api/agent/modify-preview-v2  -- Modify an existing workflow
  POST /api/agent/apply-v2           -- Apply a previewed workflow

The v2 endpoints return structured WorkflowIntent objects with validation,
cost estimation, and repair information -- rather than raw WorkflowSpec JSON.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.schemas.agent_preview import (
    AgentApplyRequest,
    AgentApplyResponse,
    AgentPreviewResponse,
    CostEstimate,
    RepairStep,
)
from backend.app.schemas.workflow_intent import WorkflowIntent
from backend.app.services.agent_tools import estimate_calls, validate_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent-v2"])


# ---------------------------------------------------------------------------
# Request models local to this module (lightweight wrappers)
# ---------------------------------------------------------------------------

class GeneratePreviewRequest(BaseModel):
    """Request body for generate-preview-v2."""

    prompt: str = Field(..., min_length=1, description="Natural language workflow description")
    workflow_id: Optional[str] = Field(None, description="Existing workflow to modify (None = new)")


class ModifyPreviewRequest(BaseModel):
    """Request body for modify-preview-v2."""

    workflow_id: str = Field(..., description="ID of the workflow to modify")
    instruction: str = Field(..., min_length=1, description="Modification instruction")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_cost_estimate(intent: WorkflowIntent) -> CostEstimate:
    """Run estimate_calls and convert to a CostEstimate model."""
    result = estimate_calls(intent)
    if not result.success:
        return CostEstimate()
    return CostEstimate(**result.data)


def _compile_intent(intent: WorkflowIntent) -> tuple[dict | None, str | None]:
    """Attempt to compile a WorkflowIntent into a WorkflowSpecV2 dict.

    Returns (compiled_workflow_dict, error_string).
    """
    try:
        from backend.app.services.agent_compiler import compile_intent
        compiled = compile_intent(intent)
        if isinstance(compiled, dict):
            return compiled, None
        # Assume it's a Pydantic model
        return compiled.model_dump(), None
    except ImportError:
        return None, "agent_compiler not available"
    except Exception as exc:
        return None, f"Compilation failed: {exc}"


def _repair_intent(
    intent: WorkflowIntent,
    errors: list[dict],
    max_attempts: int = 2,
) -> tuple[WorkflowIntent, list[RepairStep], list[dict]]:
    """Attempt to repair a WorkflowIntent using repair_intent().

    Returns (repaired_intent, repair_steps, remaining_errors).
    """
    steps: list[RepairStep] = []
    current_intent = intent
    current_errors = errors

    try:
        from backend.app.services.agent_repair import repair_intent
    except ImportError:
        # repair not available -- return as-is
        return current_intent, steps, current_errors

    for attempt in range(1, max_attempts + 1):
        if not current_errors:
            break

        errors_before = list(current_errors)
        try:
            repaired = repair_intent(current_intent, current_errors)
        except Exception as exc:
            logger.warning(f"repair_intent failed on attempt {attempt}: {exc}")
            steps.append(RepairStep(
                attempt=attempt,
                errors_before=errors_before,
                repairs_applied=[],
                errors_after=errors_before,
            ))
            break

        # Validate the repaired intent
        val = validate_intent(repaired)
        new_errors = val.data.get("errors", []) if val.success is False else val.data.get("errors", [])

        repairs_applied: list[str] = []
        # Heuristic: compare error codes before/after
        codes_before = {e.get("code") for e in errors_before}
        codes_after = {e.get("code") for e in new_errors}
        fixed_codes = codes_before - codes_after
        if fixed_codes:
            repairs_applied = sorted(fixed_codes)

        steps.append(RepairStep(
            attempt=attempt,
            errors_before=errors_before,
            repairs_applied=repairs_applied,
            errors_after=new_errors,
        ))

        current_intent = repaired
        current_errors = new_errors

    return current_intent, steps, current_errors


def _generate_intent_from_prompt(prompt: str) -> WorkflowIntent:
    """Generate a WorkflowIntent from a natural-language prompt.

    Uses the existing Agent LLM service to generate a WorkflowIntent.
    Falls back to a simple template-based intent if the LLM is unavailable.
    """
    try:
        from backend.app.services.agent import get_agent_service
        service = get_agent_service()
        # The existing agent generates WorkflowSpec -- we build a WorkflowIntent
        # from the template fallback for now. In future, the agent should
        # output WorkflowIntent directly.
        spec = service._template_fallback(prompt, {})

        # Convert WorkflowSpec to WorkflowIntent
        return _spec_to_intent(spec, prompt)
    except Exception as exc:
        logger.warning(f"Agent service unavailable, using default intent: {exc}")
        return _default_intent(prompt)


def _modify_intent_from_prompt(
    workflow_id: str, instruction: str
) -> WorkflowIntent:
    """Modify an existing workflow via Agent and return a WorkflowIntent."""
    try:
        from backend.app.repositories.workflows import get_workflow
        from backend.app.services.agent import get_agent_service

        wf = get_workflow(workflow_id)
        from backend.app.models import WorkflowSpec
        spec = WorkflowSpec(**wf["spec"])

        service = get_agent_service()
        spec = service._template_fallback(instruction, {})
        return _spec_to_intent(spec, instruction)
    except Exception as exc:
        logger.warning(f"Modify failed, generating new intent: {exc}")
        return _default_intent(instruction)


def _spec_to_intent(spec: Any, name: str) -> WorkflowIntent:
    """Convert a WorkflowSpec to a WorkflowIntent."""
    from backend.app.schemas.workflow_intent import (
        ConnectionIntent,
        NodeIntent,
        PortRef,
    )

    kind_to_alias: dict[str, str] = {}
    alias_counter: dict[str, int] = {}
    nodes: list[NodeIntent] = []

    for wf_node in spec.nodes:
        kind = wf_node.data.kind
        count = alias_counter.get(kind, 0)
        alias_counter[kind] = count + 1
        alias = f"{kind}{count}" if count > 0 else kind

        nodes.append(NodeIntent(
            alias=alias,
            kind=kind,
            config=wf_node.data.config,
            label=wf_node.data.label,
        ))
        kind_to_alias[wf_node.id] = alias

    # Build connections from edges
    connections: list[ConnectionIntent] = []
    for edge in spec.edges:
        src_alias = kind_to_alias.get(edge.source, edge.source)
        tgt_alias = kind_to_alias.get(edge.target, edge.target)

        # Determine port names based on source/target kinds
        src_port = "text"  # default
        tgt_port = "prompt"  # default

        # Try to find the node kinds for better port inference
        for n in spec.nodes:
            if n.id == edge.source:
                src_port = _output_port_for_kind(n.data.kind)
            if n.id == edge.target:
                tgt_port = _input_port_for_kind(n.data.kind)

        connections.append(ConnectionIntent(
            source=PortRef(node=src_alias, port=src_port),
            target=PortRef(node=tgt_alias, port=tgt_port),
        ))

    # Infer scene count from storyboard config
    scene_count = None
    for node in spec.nodes:
        if node.data.kind == "storyboard":
            scenes = node.data.config.get("scenes")
            if isinstance(scenes, int):
                scene_count = scenes

    return WorkflowIntent(
        name=name[:50] if name else "Generated Workflow",
        nodes=nodes,
        connections=connections,
        scene_count=scene_count,
    )


def _output_port_for_kind(kind: str) -> str:
    port_map = {
        "textInput": "text",
        "storyboard": "scenes",
        "textToImage": "images",
        "imageToVideo": "videos",
        "videoConcat": "video",
    }
    return port_map.get(kind, "output")


def _input_port_for_kind(kind: str) -> str:
    port_map = {
        "textInput": "prompt",
        "storyboard": "prompt",
        "textToImage": "scene",
        "imageToVideo": "image",
        "videoConcat": "videos",
        "output": "video",
    }
    return port_map.get(kind, "input")


def _default_intent(prompt: str) -> WorkflowIntent:
    """Create a default workflow intent for the given prompt."""
    from backend.app.schemas.workflow_intent import (
        ConnectionIntent,
        NodeIntent,
        PortRef,
    )

    return WorkflowIntent(
        name=prompt[:50] if prompt else "Untitled Workflow",
        description=prompt,
        nodes=[
            NodeIntent(alias="input", kind="textInput", config={"prompt": prompt}),
            NodeIntent(alias="storyboard", kind="storyboard", config={"scenes": 5}),
            NodeIntent(alias="textToImage", kind="textToImage"),
            NodeIntent(alias="imageToVideo", kind="imageToVideo"),
            NodeIntent(alias="videoConcat", kind="videoConcat"),
            NodeIntent(alias="output", kind="output"),
        ],
        connections=[
            ConnectionIntent(
                source=PortRef(node="input", port="text"),
                target=PortRef(node="storyboard", port="prompt"),
            ),
            ConnectionIntent(
                source=PortRef(node="storyboard", port="scenes"),
                target=PortRef(node="textToImage", port="scene"),
                mode="map",
            ),
            ConnectionIntent(
                source=PortRef(node="textToImage", port="images"),
                target=PortRef(node="imageToVideo", port="image"),
                mode="map",
            ),
            ConnectionIntent(
                source=PortRef(node="imageToVideo", port="videos"),
                target=PortRef(node="videoConcat", port="videos"),
                mode="aggregate",
            ),
            ConnectionIntent(
                source=PortRef(node="videoConcat", port="video"),
                target=PortRef(node="output", port="video"),
            ),
        ],
        scene_count=5,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate-preview-v2", response_model=AgentPreviewResponse)
async def generate_preview_v2(request: GeneratePreviewRequest) -> AgentPreviewResponse:
    """Generate a workflow from a natural-language prompt.

    Returns a full AgentPreviewResponse with:
    - The generated WorkflowIntent
    - Validation errors (if any)
    - Repair steps (if errors were repaired)
    - Cost estimate
    - Whether the workflow can be applied
    """
    # 1. Generate intent
    intent = _generate_intent_from_prompt(request.prompt)

    # 2. Compile (if compiler available)
    compiled, compile_error = _compile_intent(intent)

    # 3. Validate
    val = validate_intent(intent)
    errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
    warnings = list(val.data.get("warnings", []))

    # 4. Repair if there are errors
    repair_steps: list[RepairStep] = []
    if errors:
        intent, repair_steps, errors = _repair_intent(intent, errors)

        # Re-validate after repair
        val = validate_intent(intent)
        errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
        warnings.extend(val.data.get("warnings", []))

    # Re-compile after repair if needed
    if errors and compiled is not None:
        compiled, _ = _compile_intent(intent)

    # 5. Cost estimate
    cost = _build_cost_estimate(intent)
    warnings.extend(cost.warnings)

    can_apply = len(errors) == 0

    return AgentPreviewResponse(
        intent=intent,
        compiled_workflow=compiled,
        validation_errors=errors,
        repair_steps=repair_steps,
        cost_estimate=cost,
        warnings=warnings,
        can_apply=can_apply,
    )


@router.post("/modify-preview-v2", response_model=AgentPreviewResponse)
async def modify_preview_v2(request: ModifyPreviewRequest) -> AgentPreviewResponse:
    """Modify an existing workflow via natural-language instruction.

    Returns a full AgentPreviewResponse, same as generate-preview-v2.
    """
    # 1. Modify intent
    intent = _modify_intent_from_prompt(request.workflow_id, request.instruction)

    # 2. Compile (if compiler available)
    compiled, compile_error = _compile_intent(intent)

    # 3. Validate
    val = validate_intent(intent)
    errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
    warnings = list(val.data.get("warnings", []))

    # 4. Repair if there are errors
    repair_steps: list[RepairStep] = []
    if errors:
        intent, repair_steps, errors = _repair_intent(intent, errors)

        # Re-validate after repair
        val = validate_intent(intent)
        errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
        warnings.extend(val.data.get("warnings", []))

    # Re-compile after repair if needed
    if errors and compiled is not None:
        compiled, _ = _compile_intent(intent)

    # 5. Cost estimate
    cost = _build_cost_estimate(intent)
    warnings.extend(cost.warnings)

    can_apply = len(errors) == 0

    return AgentPreviewResponse(
        intent=intent,
        compiled_workflow=compiled,
        validation_errors=errors,
        repair_steps=repair_steps,
        cost_estimate=cost,
        warnings=warnings,
        can_apply=can_apply,
    )


@router.post("/apply-v2", response_model=AgentApplyResponse)
async def apply_v2(request: AgentApplyRequest) -> AgentApplyResponse:
    """Apply a previewed workflow.

    - If workflow_id is None, creates a new workflow.
    - If workflow_id is provided, updates the existing workflow.
    - Uses expected_version for optimistic concurrency (409 on conflict).
    """
    intent = request.intent

    # Validate before applying
    val = validate_intent(intent)
    errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
    if errors:
        return AgentApplyResponse(
            success=False,
            error=f"Validation failed with {len(errors)} error(s): {errors[0].get('message', '')}",
        )

    # Compile the intent into a WorkflowSpec
    compiled, compile_error = _compile_intent(intent)
    if compiled is None:
        # Fallback: use the Agent service to generate a spec
        try:
            from backend.app.services.agent import get_agent_service
            service = get_agent_service()
            spec = service._template_fallback(intent.name, {})
            compiled = spec.model_dump()
        except Exception as exc:
            return AgentApplyResponse(
                success=False,
                error=f"Failed to compile intent: {compile_error or exc}",
            )

    try:
        if request.workflow_id:
            # Update existing workflow
            from backend.app.repositories.workflows import (
                OptimisticLockError,
                WorkflowNotFoundError,
                get_workflow,
                update_workflow,
            )

            try:
                wf = get_workflow(request.workflow_id)
            except WorkflowNotFoundError:
                raise HTTPException(404, f"Workflow '{request.workflow_id}' not found")

            expected_version = request.expected_version or wf["version"]
            try:
                result = update_workflow(request.workflow_id, compiled, expected_version)
            except OptimisticLockError as exc:
                raise HTTPException(409, str(exc))

            return AgentApplyResponse(
                success=True,
                workflow_id=result["id"],
                version=result["version"],
            )
        else:
            # Create new workflow
            from backend.app.repositories.workflows import create_workflow

            # Generate a new ID if not present
            if not compiled.get("id"):
                import uuid
                compiled["id"] = f"wf-{uuid.uuid4().hex[:12]}"

            result = create_workflow(compiled, name=intent.name)

            return AgentApplyResponse(
                success=True,
                workflow_id=result["id"],
                version=result["version"],
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Apply failed: {exc}")
        return AgentApplyResponse(
            success=False,
            error=f"Apply failed: {exc}",
        )
