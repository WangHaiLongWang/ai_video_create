"""Agent Preview -- response models for the Agent preview API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .workflow_intent import WorkflowIntent


class CostEstimate(BaseModel):
    """Estimated API cost breakdown for a workflow intent."""

    scene_count: int = 0
    variant_count: int = 1
    image_calls: int = 0
    video_calls: int = 0
    storyboard_calls: int = 0
    concat_calls: int = 0
    total_calls: int = 0
    estimated_duration_seconds: int = 0
    warnings: list[str] = Field(default_factory=list)


class RepairStep(BaseModel):
    """One repair attempt recorded during validation repair."""

    attempt: int
    errors_before: list[dict] = Field(default_factory=list)
    repairs_applied: list[str] = Field(default_factory=list)
    errors_after: list[dict] = Field(default_factory=list)


class AgentPreviewResponse(BaseModel):
    """Response from Agent generate/modify preview."""

    intent: WorkflowIntent
    compiled_workflow: Optional[dict] = None  # WorkflowSpecV2 if compilation succeeded
    validation_errors: list[dict] = Field(default_factory=list)
    repair_steps: list[RepairStep] = Field(default_factory=list)
    cost_estimate: Optional[CostEstimate] = None
    warnings: list[str] = Field(default_factory=list)
    can_apply: bool = False  # True only if validation passed with 0 errors


class AgentApplyRequest(BaseModel):
    """Request to apply an Agent preview."""

    intent: WorkflowIntent
    expected_version: Optional[int] = None  # For optimistic concurrency
    workflow_id: Optional[str] = None  # None = create new, existing = update


class AgentApplyResponse(BaseModel):
    """Response from applying an Agent preview."""

    success: bool
    workflow_id: Optional[str] = None
    version: Optional[int] = None
    error: Optional[str] = None
