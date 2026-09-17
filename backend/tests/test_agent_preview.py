"""Tests for agent preview models and enhanced estimate_calls."""

import pytest

from backend.app.schemas.agent_preview import (
    AgentApplyRequest,
    AgentApplyResponse,
    AgentPreviewResponse,
    CostEstimate,
    RepairStep,
)
from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)
from backend.app.services.agent_tools import estimate_calls


# ---------------------------------------------------------------------------
# CostEstimate model tests
# ---------------------------------------------------------------------------


class TestCostEstimate:
    def test_default_values(self):
        ce = CostEstimate()
        assert ce.scene_count == 0
        assert ce.variant_count == 1
        assert ce.image_calls == 0
        assert ce.video_calls == 0
        assert ce.storyboard_calls == 0
        assert ce.concat_calls == 0
        assert ce.total_calls == 0
        assert ce.estimated_duration_seconds == 0
        assert ce.warnings == []

    def test_from_dict(self):
        data = {
            "scene_count": 5,
            "variant_count": 2,
            "image_calls": 10,
            "video_calls": 10,
            "total_calls": 12,
            "estimated_duration_seconds": 400,
            "warnings": ["High call count"],
        }
        ce = CostEstimate(**data)
        assert ce.scene_count == 5
        assert ce.variant_count == 2
        assert ce.image_calls == 10
        assert ce.video_calls == 10
        assert ce.storyboard_calls == 0
        assert ce.concat_calls == 0
        assert ce.total_calls == 12
        assert ce.estimated_duration_seconds == 400
        assert len(ce.warnings) == 1


# ---------------------------------------------------------------------------
# RepairStep model tests
# ---------------------------------------------------------------------------


class TestRepairStep:
    def test_basic(self):
        step = RepairStep(
            attempt=1,
            errors_before=[{"code": "UNKNOWN_KIND", "message": "bad kind"}],
            repairs_applied=["UNKNOWN_KIND"],
            errors_after=[],
        )
        assert step.attempt == 1
        assert len(step.errors_before) == 1
        assert len(step.repairs_applied) == 1
        assert len(step.errors_after) == 0

    def test_empty_defaults(self):
        step = RepairStep(attempt=1)
        assert step.errors_before == []
        assert step.repairs_applied == []
        assert step.errors_after == []


# ---------------------------------------------------------------------------
# AgentPreviewResponse model tests
# ---------------------------------------------------------------------------


class TestAgentPreviewResponse:
    def test_minimal(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        resp = AgentPreviewResponse(intent=intent)
        assert resp.compiled_workflow is None
        assert resp.validation_errors == []
        assert resp.repair_steps == []
        assert resp.cost_estimate is None
        assert resp.warnings == []
        assert resp.can_apply is False

    def test_with_cost_estimate(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        cost = CostEstimate(scene_count=5, total_calls=10)
        resp = AgentPreviewResponse(
            intent=intent,
            cost_estimate=cost,
            can_apply=True,
        )
        assert resp.can_apply is True
        assert resp.cost_estimate.scene_count == 5


# ---------------------------------------------------------------------------
# AgentApplyRequest / Response model tests
# ---------------------------------------------------------------------------


class TestAgentApplyRequest:
    def test_minimal(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        req = AgentApplyRequest(intent=intent)
        assert req.expected_version is None
        assert req.workflow_id is None

    def test_with_fields(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        req = AgentApplyRequest(
            intent=intent,
            expected_version=3,
            workflow_id="wf-123",
        )
        assert req.expected_version == 3
        assert req.workflow_id == "wf-123"


class TestAgentApplyResponse:
    def test_success(self):
        resp = AgentApplyResponse(success=True, workflow_id="wf-1", version=2)
        assert resp.success is True
        assert resp.workflow_id == "wf-1"
        assert resp.version == 2
        assert resp.error is None

    def test_failure(self):
        resp = AgentApplyResponse(success=False, error="Validation failed")
        assert resp.success is False
        assert resp.error == "Validation failed"


# ---------------------------------------------------------------------------
# Enhanced estimate_calls tests
# ---------------------------------------------------------------------------


class TestEnhancedEstimateCalls:
    def test_basic_estimate_fields(self):
        """Test that estimate_calls returns all the new fields."""
        intent = WorkflowIntent(
            name="Basic",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=3,
            variant_count=1,
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] == 3
        assert result.data["variant_count"] == 1
        assert result.data["image_calls"] == 3
        assert result.data["video_calls"] == 3
        assert result.data["storyboard_calls"] == 1
        assert result.data["total_calls"] == 7  # 3 + 3 + 1
        assert result.data["estimated_duration_seconds"] > 0
        assert "warnings" in result.data

    def test_duration_estimation(self):
        """Test that duration is estimated correctly."""
        intent = WorkflowIntent(
            name="Duration",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 5}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
            ],
            scene_count=5,
            variant_count=1,
        )
        result = estimate_calls(intent)
        assert result.success
        # storyboard: 1 call * 5 scenes * 10s = 50s
        # textToImage: 5 images * 5s = 25s
        # imageToVideo: 5 videos * 30s = 150s (default 30s)
        # videoConcat: 1 call * 10s = 10s
        # total = 50 + 25 + 150 + 10 = 235s
        assert result.data["estimated_duration_seconds"] == 235

    def test_duration_with_custom_video_duration(self):
        """Test that custom video duration affects estimation."""
        intent = WorkflowIntent(
            name="Custom Duration",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=2,
            variant_count=1,
            duration=10,  # 10 seconds per video
        )
        result = estimate_calls(intent)
        assert result.success
        # textToImage: 2 * 5s = 10s
        # imageToVideo: 2 * 10s = 20s
        # total = 30s
        assert result.data["estimated_duration_seconds"] == 30

    def test_high_call_count_warning(self):
        """Test that high call counts generate warnings."""
        intent = WorkflowIntent(
            name="Many Calls",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=20,
            variant_count=3,
        )
        result = estimate_calls(intent)
        assert result.success
        # 20 * 3 = 60 image calls + 60 video calls = 120 total (no storyboard node)
        assert result.data["total_calls"] == 120
        warnings = result.data["warnings"]
        assert any("High call count" in w for w in warnings)

    def test_high_variant_warning(self):
        """Test that high variant counts generate warnings."""
        intent = WorkflowIntent(
            name="Many Variants",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=5,
            variant_count=5,
        )
        result = estimate_calls(intent)
        assert result.success
        warnings = result.data["warnings"]
        assert any("Variant count" in w for w in warnings)

    def test_long_duration_warning(self):
        """Test that long estimated duration generates warnings."""
        intent = WorkflowIntent(
            name="Long Duration",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=10,
            variant_count=1,
            duration=60,  # 60s per video
        )
        result = estimate_calls(intent)
        assert result.success
        # imageToVideo: 10 * 60 = 600s total
        assert result.data["estimated_duration_seconds"] >= 600
        warnings = result.data["warnings"]
        assert any("Estimated execution time" in w for w in warnings)

    def test_concat_calls_counted(self):
        """Test that videoConcat is counted in total."""
        intent = WorkflowIntent(
            name="With Concat",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
            ],
            scene_count=3,
            variant_count=1,
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["concat_calls"] == 1
        assert result.data["total_calls"] == 8  # 3 + 3 + 1 + 1

    def test_zero_scenes(self):
        """Test estimate with no scenes (defaults to 1)."""
        intent = WorkflowIntent(
            name="No Scenes",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
            ],
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] == 1
        assert result.data["image_calls"] == 1
