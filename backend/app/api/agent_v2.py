"""Agent API v2 -- structured generate/modify with preview and apply.

Endpoints:
  POST /api/agent/generate-preview-v2 -- Generate a workflow from a prompt
  POST /api/agent/modify-preview-v2  -- Modify an existing workflow
  POST /api/agent/apply-v2           -- Apply a previewed workflow

The v2 endpoints return structured WorkflowIntent objects with validation,
cost estimation, and repair information -- rather than raw WorkflowSpec JSON.
"""

from __future__ import annotations

import json
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
from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
from backend.app.services import agent_trace
from backend.app.services.agent_tools import (
    enforce_resource_limits,
    estimate_calls,
    validate_intent,
)

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

def _load_existing_spec(workflow_id: str) -> dict | None:
    """Load an existing workflow's spec dict, or None when it does not exist."""
    try:
        from backend.app.repositories.workflows import get_workflow

        return get_workflow(workflow_id)["spec"]
    except Exception:
        return None


def _build_cost_estimate(intent: WorkflowIntent) -> CostEstimate:
    """Run estimate_calls and convert to a CostEstimate model."""
    result = estimate_calls(intent)
    if not result.success:
        return CostEstimate()
    return CostEstimate(**result.data)


def _resource_limit_errors(intent: WorkflowIntent) -> list[dict]:
    """Return stable validation errors for the preview/apply safety gate."""
    return list(enforce_resource_limits(intent).data.get("errors", []))


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
        # Embed as JSON (not Python repr) so providers can parse the topology.
        context_text = json.dumps(context, ensure_ascii=False, default=str)
        modified = await parse_workflow_intent(
            f"Modify this existing WorkflowIntent: {context_text}\nInstruction: {instruction}",
            provider=provider,
        )
        # The parser builds fresh NodeIntents without original ids — re-attach
        # them so compilation keeps the node identity of untouched nodes.
        return _restore_original_ids(modified, existing_intent)
    except Exception as exc:
        logger.warning(f"Modify failed, generating new intent: {exc}")
        return existing_intent or _default_intent(instruction)


def _restore_original_ids(
    new_intent: WorkflowIntent, existing_intent: WorkflowIntent
) -> WorkflowIntent:
    """Re-attach original node ids from the existing intent to a parsed intent.

    Matching is by alias first (the modify prompt echoes the aliases), then by
    kind order for nodes whose alias was rewritten by the model.  Nodes that
    match nothing (genuinely new) keep ``nodeId=None`` and receive a
    deterministic id at compile time.
    """
    alias_to_id: dict[str, str] = {
        node.alias: node.node_id for node in existing_intent.nodes if node.node_id
    }
    kind_remaining: dict[str, list[str]] = {}
    for node in existing_intent.nodes:
        if node.node_id:
            kind_remaining.setdefault(node.kind, []).append(node.node_id)

    restored: list[NodeIntent] = []
    for node in new_intent.nodes:
        if node.node_id:
            restored.append(node)
            continue
        original_id = alias_to_id.get(node.alias)
        if original_id is None:
            candidates = kind_remaining.get(node.kind) or []
            original_id = candidates.pop(0) if candidates else None
        else:
            candidates = kind_remaining.get(node.kind) or []
            if original_id in candidates:
                candidates.remove(original_id)
        restored.append(
            node if original_id is None else node.model_copy(update={"node_id": original_id})
        )
    return new_intent.model_copy(update={"nodes": restored})


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

        node_id = wf_node.get("id") if isinstance(wf_node, dict) else wf_node.id
        nodes.append(NodeIntent(
            alias=alias,
            kind=kind,
            # Carry the original id through compilation so modify keeps
            # node identity ("修改不重建") instead of regenerating ids.
            nodeId=node_id,
            config=data.get("config", {}) if isinstance(data, dict) else data.config,
            label=data.get("label") if isinstance(data, dict) else data.label,
            moduleId=(data.get("moduleId", data.get("module_id")) if isinstance(data, dict) else getattr(data, "module_id", None)),
            moduleVersion=(data.get("moduleVersion", data.get("module_version")) if isinstance(data, dict) else getattr(data, "module_version", None)),
            configOverrides=(data.get("configOverrides", data.get("config_overrides", {})) if isinstance(data, dict) else getattr(data, "config_overrides", {})),
        ))
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

        edge_data = edge.get("data", {}) if isinstance(edge, dict) else getattr(edge, "data", {}) or {}
        mode = (edge_data.get("mode") if isinstance(edge_data, dict) else None) or "direct"
        connections.append(ConnectionIntent(
            source=PortRef(node=src_alias, port=src_port),
            target=PortRef(node=tgt_alias, port=tgt_port),
            mode=mode,
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
    from backend.app.schemas.node_catalog import load_node_catalog

    manifest = load_node_catalog().get(kind)
    if manifest and manifest.ports.outputs:
        return manifest.ports.outputs[0].id
    return "output"


def _input_port_for_kind(kind: str) -> str:
    from backend.app.schemas.node_catalog import load_node_catalog

    manifest = load_node_catalog().get(kind)
    if manifest and manifest.ports.inputs:
        return next(
            (port.id for port in manifest.ports.inputs if port.required),
            manifest.ports.inputs[0].id,
        )
    return "input"


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
    with agent_trace.trace_operation(
        agent_trace.TRACE_KIND_GENERATE,
        workflow_id=request.workflow_id,
        prompt=request.prompt,
    ) as tr:
        # 1. Generate intent
        intent = await _generate_intent_from_prompt(request.prompt)
        agent_trace.safe_add_step(
            None, "intent", "build_intent", "ok", 0,
            {"node_count": len(intent.nodes)},
        )

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
        agent_trace.safe_add_step(
            None, "validate", "compiled_gate",
            "ok" if not errors else "error", 0,
            {"error_count": len(errors)},
        )

        # 5. Cost estimate
        cost = _build_cost_estimate(intent)
        warnings.extend(cost.warnings)
        errors.extend(_resource_limit_errors(intent))

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

    Returns a full AgentPreviewResponse, same as generate-preview-v2, plus the
    incremental change vs the existing workflow: ``patch`` / ``diff`` /
    ``destructive`` / ``module_diffs``.
    """
    with agent_trace.trace_operation(
        agent_trace.TRACE_KIND_MODIFY,
        workflow_id=request.workflow_id,
        prompt=request.instruction,
    ) as tr:
        # 1. Modify intent
        intent = await _modify_intent_from_prompt(request.workflow_id, request.instruction)
        agent_trace.safe_add_step(
            None, "intent", "build_intent", "ok", 0,
            {"node_count": len(intent.nodes)},
        )

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
        agent_trace.safe_add_step(
            None, "validate", "compiled_gate",
            "ok" if not errors else "error", 0,
            {"error_count": len(errors)},
        )

        # 5. Cost estimate
        cost = _build_cost_estimate(intent)
        warnings.extend(cost.warnings)
        errors.extend(_resource_limit_errors(intent))

        # 6. Incremental diff vs the existing workflow (MOD-R3-004)
        from backend.app.services.agent_diff import (
            check_destructive,
            compute_graph_patch,
            compute_module_diffs,
            generate_diff,
            is_destructive,
        )

        patch = None
        diff_text = None
        destructive = False
        module_diffs: list[dict] = []
        existing_spec = _load_existing_spec(request.workflow_id)
        if existing_spec is not None and compiled is not None:
            patch = compute_graph_patch(existing_spec, compiled)
            diff_text = generate_diff(existing_spec, patch)
            destructive = is_destructive(patch)
            module_diffs = compute_module_diffs(existing_spec, compiled)
            warnings.extend(check_destructive(patch))

        can_apply = len(errors) == 0

        diff_summary = agent_trace.summarize_module_diffs(module_diffs)
        agent_trace.safe_finish(tr, module_diff_summary=diff_summary)
        agent_trace.emit_agent_audit(
            agent_trace.AUDIT_MODIFY,
            prompt_hash=tr.prompt_hash,
            module_diff_summary=diff_summary,
            repair_count=tr.repair_count,
            trace_id=tr.trace_id or None,
        )

        return AgentPreviewResponse(
            intent=intent,
            compiled_workflow=compiled,
            validation_errors=errors,
            repair_steps=repair_steps,
            cost_estimate=cost,
            warnings=warnings,
            can_apply=can_apply,
            patch=patch,
            diff=diff_text,
            destructive=destructive,
            module_diffs=module_diffs,
        )


@router.post("/apply-v2", response_model=AgentApplyResponse)
async def apply_v2(request: AgentApplyRequest) -> AgentApplyResponse:
    """Apply a previewed workflow.

    - If workflow_id is None, creates a new workflow.
    - If workflow_id is provided, updates the existing workflow.
    - Uses expected_version for optimistic concurrency (409 on conflict).
    """
    intent = request.intent

    prompt_for_hash = intent.description or intent.name or ""

    with agent_trace.trace_operation(
        agent_trace.TRACE_KIND_APPLY,
        workflow_id=request.workflow_id,
        prompt=prompt_for_hash,
    ) as tr:
        try:
            response, diff_summary = _apply_v2_impl(request)
        except HTTPException as exc:
            tr.set_status("error", error_code=f"HTTP_{exc.status_code}")
            raise

        if diff_summary is not None:
            agent_trace.safe_finish(tr, module_diff_summary=diff_summary)
        if response.success:
            agent_trace.emit_agent_audit(
                agent_trace.AUDIT_APPLY,
                prompt_hash=tr.prompt_hash,
                module_diff_summary=diff_summary,
                repair_count=tr.repair_count,
                trace_id=tr.trace_id or None,
            )
        else:
            tr.set_status("error", error_code="APPLY_FAILED")
        return response


def _apply_v2_impl(
    request: AgentApplyRequest,
) -> tuple[AgentApplyResponse, dict | None]:
    """Run the apply-v2 pipeline.  Returns (response, module_diff_summary)."""
    intent = request.intent

    # Preview output is client-controlled and may be stale or edited, so apply
    # must independently repeat the resource gate before compilation/storage.
    limit_errors = _resource_limit_errors(intent)
    if limit_errors:
        agent_trace.safe_add_step(
            None, "validate", "resource_limits", "error", 0,
            {"error_count": len(limit_errors)},
        )
        return (
            AgentApplyResponse(
                success=False,
                error=(
                    f"Resource limits exceeded with {len(limit_errors)} error(s): "
                    f"{limit_errors[0].get('message', '')}"
                ),
            ),
            None,
        )

    # Validate before applying
    val = validate_intent(intent)
    errors = val.data.get("errors", []) if not val.success else val.data.get("errors", [])
    if errors:
        agent_trace.safe_add_step(
            None, "validate", "intent_validation", "error", 0,
            {"error_count": len(errors)},
        )
        return (
            AgentApplyResponse(
                success=False,
                error=f"Validation failed with {len(errors)} error(s): {errors[0].get('message', '')}",
            ),
            None,
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
            return (
                AgentApplyResponse(
                    success=False,
                    error=f"Failed to compile intent: {compile_error or exc}",
                ),
                None,
            )

    # Graph/module/resolver validation on the compiled workflow
    gate_errors = _compiled_gate_errors(compiled, compile_error)
    if gate_errors:
        agent_trace.safe_add_step(
            None, "validate", "compiled_gate", "error", 0,
            {"error_count": len(gate_errors)},
        )
        return (
            AgentApplyResponse(
                success=False,
                error=f"Validation failed with {len(gate_errors)} error(s): {gate_errors[0].get('message', '')}",
            ),
            None,
        )
    agent_trace.safe_add_step(
        None, "validate", "compiled_gate", "ok", 0, {"error_count": 0},
    )

    # Keep the HTTP 422 graph contract for callers that depend on it.
    nodes, edges = extract_nodes_edges_from_spec(compiled)
    graph_errors = validate_graph(nodes, edges)
    if graph_errors:
        detail = build_422_response(graph_errors)
        raise HTTPException(status_code=422, detail=detail)

    diff_summary: dict | None = None
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

            # Incremental apply (修改不重建): patch the existing spec instead
            # of replacing it wholesale, so untouched nodes/edges keep their
            # ids and canvas metadata.
            from backend.app.services.agent_diff import (
                apply_graph_patch,
                compute_graph_patch,
                compute_module_diffs,
            )

            existing_spec = wf["spec"]
            try:
                patch = compute_graph_patch(existing_spec, compiled)
                patched = apply_graph_patch(existing_spec, patch, compiled=compiled)
            except ValueError as exc:
                raise HTTPException(400, str(exc))

            patched["name"] = compiled.get("name") or patched.get("name")
            if compiled.get("description") is not None:
                patched["description"] = compiled["description"]

            # Validate the patched graph before saving
            patched_nodes, patched_edges = extract_nodes_edges_from_spec(patched)
            raise_if_invalid(patched_nodes, patched_edges)

            diff_summary = agent_trace.summarize_module_diffs(
                compute_module_diffs(existing_spec, compiled)
            )

            try:
                result = update_workflow(request.workflow_id, patched, expected_version)
            except OptimisticLockError as exc:
                raise HTTPException(409, str(exc))

            return (
                AgentApplyResponse(
                    success=True,
                    workflow_id=result["id"],
                    version=result["version"],
                ),
                diff_summary,
            )
        else:
            # Create new workflow
            from backend.app.repositories.workflows import create_workflow

            # Generate a new ID if not present
            if not compiled.get("id"):
                import uuid
                compiled["id"] = f"wf-{uuid.uuid4().hex[:12]}"

            result = create_workflow(compiled, name=intent.name)

            diff_summary = agent_trace.build_diff_summary(
                added=len(compiled.get("nodes", []) or []),
                removed=0,
                updated=0,
                modules=[],
            )

            return (
                AgentApplyResponse(
                    success=True,
                    workflow_id=result["id"],
                    version=result["version"],
                ),
                diff_summary,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Apply failed: {exc}")
        return (
            AgentApplyResponse(
                success=False,
                error=f"Apply failed: {exc}",
            ),
            diff_summary,
        )
