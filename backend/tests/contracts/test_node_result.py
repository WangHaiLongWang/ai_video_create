"""Tests for NodeResult, NodeError, and ArtifactRef schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.handlers.contracts import ArtifactRef, NodeError, NodeResult, Scene


# ---------------------------------------------------------------------------
# NodeError tests
# ---------------------------------------------------------------------------

class TestNodeError:
    def test_minimal(self):
        err = NodeError(code="E001", message="something broke")
        assert err.code == "E001"
        assert err.message == "something broke"
        assert err.retryable is False
        assert err.details == {}

    def test_retryable(self):
        err = NodeError(code="TIMEOUT", message="timed out", retryable=True)
        assert err.retryable is True

    def test_details(self):
        err = NodeError(code="E002", message="err", details={"key": "val"})
        assert err.details == {"key": "val"}


# ---------------------------------------------------------------------------
# ArtifactRef tests
# ---------------------------------------------------------------------------

class TestArtifactRef:
    def test_minimal_image(self):
        ref = ArtifactRef(type="image")
        assert ref.type == "image"
        assert ref.asset_id is None
        assert ref.scene_id is None
        assert ref.url is None
        assert ref.metadata == {}

    def test_full_video_ref(self):
        ref = ArtifactRef(
            type="video",
            asset_id="vid-abc",
            scene_id="scene-001",
            url="https://example.com/vid.mp4",
            metadata={"duration": 5.0},
        )
        assert ref.asset_id == "vid-abc"
        assert ref.url == "https://example.com/vid.mp4"

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ArtifactRef(type="invalid_type")  # type: ignore[arg-type]

    def test_all_literal_types(self):
        for t in ("image", "video", "text", "audio"):
            ref = ArtifactRef(type=t)
            assert ref.type == t


# ---------------------------------------------------------------------------
# NodeResult tests
# ---------------------------------------------------------------------------

class TestNodeResult:
    def test_ok_minimal(self):
        result = NodeResult.ok()
        assert result.status == "succeeded"
        assert result.output is None
        assert result.artifacts == []
        assert result.metrics == {}
        assert result.error is None

    def test_ok_with_output(self):
        ref = ArtifactRef(type="image", asset_id="img-123")
        result = NodeResult.ok(output=ref, artifacts=["img-123"])
        assert result.status == "succeeded"
        assert result.output.asset_id == "img-123"
        assert result.artifacts == ["img-123"]

    def test_fail_minimal(self):
        result = NodeResult.fail()
        assert result.status == "failed"
        assert result.output is None
        assert result.error is not None
        assert result.error.code == "UNKNOWN"
        assert result.error.message == ""
        assert result.error.retryable is False

    def test_fail_with_details(self):
        result = NodeResult.fail(
            code="NO_PROMPT",
            message="Missing prompt",
            retryable=True,
            details={"field": "prompt"},
        )
        assert result.error.code == "NO_PROMPT"
        assert result.error.message == "Missing prompt"
        assert result.error.retryable is True
        assert result.error.details == {"field": "prompt"}

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            NodeResult(status="ok")  # type: ignore[arg-type]

    def test_invalid_status_rejected_2(self):
        with pytest.raises(ValidationError):
            NodeResult(status="error")  # type: ignore[arg-type]

    def test_to_dict_excludes_none(self):
        result = NodeResult.ok()
        d = result.to_dict()
        assert d == {"status": "succeeded", "artifacts": [], "metrics": {}}
        assert "output" not in d
        assert "error" not in d

    def test_to_dict_with_output(self):
        ref = ArtifactRef(type="video", asset_id="vid-1")
        result = NodeResult.ok(output=ref, artifacts=["vid-1"], metrics={"duration_ms": 1200})
        d = result.to_dict()
        assert d["status"] == "succeeded"
        assert d["output"]["type"] == "video"
        assert d["output"]["asset_id"] == "vid-1"
        assert d["artifacts"] == ["vid-1"]
        assert d["metrics"]["duration_ms"] == 1200

    def test_to_dict_failed(self):
        result = NodeResult.fail(code="E1", message="err")
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["error"]["code"] == "E1"
        assert "output" not in d

    def test_roundtrip_via_model_validate(self):
        ref = ArtifactRef(type="image", asset_id="img-x", scene_id="s-1")
        original = NodeResult.ok(output=ref, artifacts=["img-x"])
        d = original.to_dict()
        restored = NodeResult.model_validate(d)
        assert restored.status == original.status
        assert restored.output.asset_id == "img-x"
        assert restored.artifacts == ["img-x"]

    def test_multiple_artifacts(self):
        result = NodeResult.ok(
            output=ArtifactRef(type="video"),
            artifacts=["img-1", "vid-1", "vid-2"],
        )
        assert len(result.artifacts) == 3


# ---------------------------------------------------------------------------
# Scene tests
# ---------------------------------------------------------------------------

class TestScene:
    def test_minimal(self):
        scene = Scene(scene_id="s-001", index=0)
        assert scene.scene_id == "s-001"
        assert scene.index == 0
        assert scene.narration == ""
        assert scene.image_prompt == ""
        assert scene.video_prompt == ""
        assert scene.duration == 5.0

    def test_full(self):
        scene = Scene(
            scene_id="s-002",
            index=1,
            narration="A quiet street.",
            image_prompt="rainy street, night",
            video_prompt="slow pan left",
            duration=4.0,
            metadata={"style": "noir"},
        )
        assert scene.duration == 4.0
        assert scene.metadata["style"] == "noir"

    def test_roundtrip(self):
        scene = Scene(scene_id="s-1", index=0, narration="test")
        d = scene.model_dump()
        restored = Scene.model_validate(d)
        assert restored.scene_id == scene.scene_id
        assert restored.narration == scene.narration


# ---------------------------------------------------------------------------
# Integration: NodeResult + ArtifactRef serialization
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_storyboard_result_pattern(self):
        """Simulate a storyboard handler returning scenes via NodeResult."""
        scenes = [
            {"scene_id": "scene-001", "index": 0, "narration": "n1"},
            {"scene_id": "scene-002", "index": 1, "narration": "n2"},
        ]
        result = NodeResult.ok(
            output=ArtifactRef(type="text", metadata={"scenes": scenes, "count": 2}),
        )
        d = result.to_dict()
        assert d["output"]["metadata"]["scenes"][0]["scene_id"] == "scene-001"

        # Worker reads scenes back from the dict
        output = d["output"]
        extracted_scenes = output["metadata"]["scenes"]
        assert len(extracted_scenes) == 2

    def test_image_generation_result_pattern(self):
        """Simulate an image handler returning an artifact."""
        result = NodeResult.ok(
            output=ArtifactRef(
                type="image",
                asset_id="img-abc",
                scene_id="scene-001",
                url="http://localhost/assets/img-abc.png",
                metadata={"path": "images/img-abc.png", "width": 1024},
            ),
            artifacts=["img-abc"],
        )
        d = result.to_dict()
        assert d["output"]["asset_id"] == "img-abc"
        assert d["artifacts"] == ["img-abc"]

    def test_worker_normalization_from_dict(self):
        """Worker can construct NodeResult from a plain dict (legacy path)."""
        legacy_dict = {
            "status": "succeeded",
            "output": {"type": "text"},
            "artifacts": [],
        }
        result = NodeResult(**legacy_dict)
        assert result.status == "succeeded"

    def test_worker_normalization_failed(self):
        """Worker constructs NodeResult for a failed handler."""
        failed_dict = {
            "status": "failed",
            "error": {"code": "E1", "message": "boom"},
        }
        result = NodeResult(**failed_dict)
        assert result.status == "failed"
        assert result.error.code == "E1"
