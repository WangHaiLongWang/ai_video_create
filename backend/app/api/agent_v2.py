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

from backend.app.domain.graph_validation import (
    extract_nodes_edges_from_spec,
    raise_if_invalid,
    validate_graph,
    build_422_response,
    get_node_catalog,
)
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
            result = repair_intent(current_intent, max_repairs=1)
        except Exception as exc:
            logger.warning(f"repair_intent failed on attempt {attempt}: {exc}")
            steps.append(RepairStep(
                attempt=attempt,
                errors_before=errors_before,
                repairs_applied=[],
                errors_after=errors_before,
            ))
            break

        repaired = result.repaired_intent
        new_errors = result.errors

        repairs_applied = list(result.repairs)

        steps.append(RepairStep(
            attempt=attempt,
            errors_before=errors_before,
            repairs_applied=repairs_applied,
            errors_after=new_errors,
        ))

        current_intent = repaired
        current_errors = new_errors

    return current_intent, steps, current_errors


def _compiled_gate_errors(compiled: dict | None, compile_error: str | None) -> list[dict]:
    """Validate graph and module resolution before a preview can be applied."""
    if compiled is None:
        return [{"code": "COMPILE_FAILED", "message": compile_error or "Compilation failed"}]

    errors: list[dict] = []
    nodes, edges = extract_nodes_edges_from_spec(compiled)
    for error in validate_graph(nodes, edges):
        errors.append({
            "code": error.code,
            "message": error.message,
            **({"nodeId": error.node_id} if error.node_id else {}),
            **({"edgeId": error.edge_id} if error.edge_id else {}),
            **({"portId": error.port_id} if error.port_id else {}),
        })

    try:
        from backend.app.services.execution_resolver import resolve_execution_config

        resolution = resolve_execution_config(compiled)
        for error in resolution.errors:
            errors.append({
                "code": f"MODULE_{error.error_type.upper()}",
                "message": error.message,
                "nodeId": error.node_id,
                "details": error.details,
            })
    except Exception as exc:
        errors.append({"code": "MODULE_RESOLUTION_FAILED", "message": str(exc)})
    return errors


async def _generate_intent_from_prompt(prompt: str) -> WorkflowIntent:
    """Generate a WorkflowIntent from a natural-language prompt.

    Uses the structured WorkflowIntent parser (MiMo-backed) to generate
    a WorkflowIntent. Falls back to the template-based intent if the
    parser or provider is unavailable.
    """
    try:
        from backend.app.services.workflow_intent_parser import parse_workflow_intent

        # Enrich prompt with module context so the parser knows about modules
        enriched_prompt = prompt
        try:
            from backend.app.services.agent_module_tools import (
                list_modules_for_agent,
                format_modules_for_system_prompt,
            )
            modules = list_modules_for_agent()
            if modules:
                module_ctx = format_modules_for_system_prompt(modules)
                enriched_prompt = f"{prompt}\n\n[可用模块信息]\n{module_ctx}"
        except Exception:
            pass  # Module tools not available — proceed without enrichment

        # Try to get a text-capable provider for the parser
        provider = None
        try:
            from backend.app.providers import get_provider
            from backend.app.config import get_settings
            configured = get_provider(get_settings().DEFAULT_LLM_PROVIDER.value)
            if configured and configured.capabilities.text:
                provider = configured
        except Exception:
            pass

        return await parse_workflow_intent(enriched_prompt, provider=provider)
    except Exception as exc:
        logger.warning(f"Intent parser failed, falling back to template: {exc}")
        try:
            from backend.app.services.agent import get_agent_service
            service = get_agent_service()
            spec = service._template_fallback(prompt, {})
            return _spec_to_intent(spec, prompt)
        except Exception as exc2:
            logger.warning(f"Agent service also unavailable, using default intent: {exc2}")
            return _default_intent(prompt)


async def _modify_intent_from_prompt(
    workflow_id: str, instruction: str
) -> WorkflowIntent:
    """Modify an existing workflow via Agent and return a WorkflowIntent."""
    existing_intent: WorkflowIntent | None = None
    try:
        from backend.app.repositories.workflows import get_workflow

        existing = get_workflow(workflow_id)
        existing_intent = _spec_to_intent(existing["spec"], existing.get("name", workflow_id))
    except Exception:
        pass

    try:
        from backend.app.services.workflow_intent_parser import parse_workflow_intent

        provider = None
        try:
            from backend.app.providers import get_provider
            from backend.app.config import get_settings
            configured = get_provider(get_settings().DEFAULT_LLM_PROVIDER.value)
            if configured and configured.capabilities.text:
                provider = configured
        except Exception:
            pass

        if existing_intent is None:
            return await parse_workflow_intent(instruction, provider=provider)
        if provider is None:
            # Preserve the existing topology when structured modification is
            # unavailable. Returning a fresh template is destructive.
            return existing_intent.model_copy(update={
                "description": instruction,
                "warnings": [*existing_intent.warnings, "Modification parser unavailable; topology preserved"],
            })
        context = existing_intent.model_dump(by_alias=True)
        return await parse_workflow_intent(
            f"Modify this existing WorkflowIntent: {context}\nInstruction: {instruction}",
            provider=provider,
        )
    except Exception as exc:
        logger.warning(f"Modify failed, generating new intent: {exc}")
        return existing_intent or _default_intent(instruction)


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

    spec_nodes = spec.get("nodes", []) if isinstance(spec, dict) else spec.nodes
    spec_edges = spec.get("edges", []) if isinstance(spec, dict) else spec.edges
    for wf_node in spec_nodes:
        data = wf_node.get("data", {}) if isinstance(wf_node, dict) else wf_node.data
        kind = data.get("kind") if isinstance(data, dict) else data.kind
        count = alias_counter.get(kind, 0)
        alias_counter[kind] = count + 1
        alias = f"{kind}{count}" if count > 0 else kind

        nodes.append(NodeIntent(
            alias=alias,
            kind=kind,
            config=data.get("config", {}) if isinstance(data, dict) else data.config,
            label=data.get("label") if isinstance(data, dict) else data.label,
            moduleId=data.get("moduleId") if isinstance(data, dict) else getattr(data, "module_id", None),
            moduleVersion=data.get("moduleVersion") if isinstance(data, dict) else getattr(data, "module_version", None),
            configOverrides=data.get("configOverrides", {}) if isinstance(data, dict) else getattr(data, "config_overrides", {}),
        ))
        node_id = wf_node.get("id") if isinstance(wf_node, dict) else wf_node.id
        kind_to_alias[node_id] = alias

    # Build connections from edges
    connections: list[ConnectionIntent] = []
    for edge in spec_edges:
        source = edge.get("source") if isinstance(edge, dict) else edge.source
        target = edge.get("target") if isinstance(edge, dict) else edge.target
        src_alias = kind_to_alias.get(source, source)
        tgt_alias = kind_to_alias.get(target, target)

        # Determine port names based on source/target kinds
        src_port = "text"  # default
        tgt_port = "prompt"  # default

        # Try to find the node kinds for better port inference
        for n in spec_nodes:
            n_id = n.get("id") if isinstance(n, dict) else n.id
            n_data = n.get("data", {}) if isinstance(n, dict) else n.data
            n_kind = n_data.get("kind") if isinstance(n_data, dict) else n_data.kind
            if n_id == source:
                src_port = edge.get("sourceHandle") if isinstance(edge, dict) else getattr(edge, "source_handle", None)
                src_port = src_port or _output_port_for_kind(n_kind)
            if n_id == target:
                tgt_port = edge.get("targetHandle") if isinstance(edge, dict) else getattr(edge, "target_handle", None)
                tgt_port = tgt_port or _input_port_for_kind(n_kind)

        connections.append(ConnectionIntent(
            source=PortRef(node=src_alias, port=src_port),
            target=PortRef(node=tgt_alias, port=tgt_port),
        ))

    # Infer scene count from storyboard config
    scene_count = None
    for node in spec_nodes:
        data = node.get("data", {}) if isinstance(node, dict) else node.data
        kind = data.get("kind") if isinstance(data, dict) else data.kind
        if kind == "storyboard":
            config = data.get("config", {}) if isinstance(data, dict) else data.config
            scenes = config.get("scenes")
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
        "textToImage": "image",
        "imageToVideo": "video",
        "videoConcat": "video",
    }
    return port_map.get(kind, "output")


def _input_port_for_kind(kind: str) -> str:
    port_map = {
        "textInput": "prompt",
        "storyboard": "prompt",
        "textToImage": "scene",
        "imageToVideo": "image",
        "videoConcat": "video",
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
                source=PortRef(node="textToImage", port="image"),
                target=PortRef(node="imageToVideo", port="image"),
                mode="map",
            ),
            ConnectionIntent(
                source=PortRef(node="imageToVideo", port="video"),
                target=PortRef(node="videoConcat", port="video"),
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
    intent = await _generate_intent_from_prompt(request.prompt)

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

    # Always compile the final intent.  The previous code only recompiled
    # while errors remained, returning the stale pre-repair graph on success.
    compiled, compile_error = _compile_intent(intent)
    errors.extend(_compiled_gate_errors(compiled, compile_error))

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
    intent = await _modify_intent_from_prompt(request.workflow_id, request.instruction)

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

    compiled, compile_error = _compile_intent(intent)
    errors.extend(_compiled_gate_errors(compiled, compile_error))

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

    # Graph/module/resolver validation on the compiled workflow
    gate_errors = _compiled_gate_errors(compiled, compile_error)
    if gate_errors:
        return AgentApplyResponse(
            success=False,
            error=f"Validation failed with {len(gate_errors)} error(s): {gate_errors[0].get('message', '')}",
        )

    # Keep the HTTP 422 graph contract for callers that depend on it.
    nodes, edges = extract_nodes_edges_from_spec(compiled)
    graph_errors = validate_graph(nodes, edges)
    if graph_errors:
        detail = build_422_response(graph_errors)
        raise HTTPException(status_code=422, detail=detail)

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
