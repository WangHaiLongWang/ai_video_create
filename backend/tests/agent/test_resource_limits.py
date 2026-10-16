"""HARD-404: Agent resource limits are enforced before persistence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
from backend.app.services.agent_tools import enforce_resource_limits


def _intent(*, scenes: int = 1, variants: int = 1, nodes: int = 1) -> WorkflowIntent:
    items = [NodeIntent(alias=f"input-{i}", kind="textInput") for i in range(nodes)]
    # Keep the intent valid only for the direct tool assertions; apply tests use
    # the API and a valid generated workflow below.
    items[0] = NodeIntent(
        alias="story",
        kind="storyboard",
        config={"scenes": scenes},
    )
    return WorkflowIntent(
        name="limit-test",
        nodes=items,
        scene_count=scenes,
        variant_count=variants,
    )


def test_resource_limit_reports_scene_and_variant_overages(monkeypatch):
    monkeypatch.setenv("AI_VIDEO_AGENT_MAX_SCENES", "2")
    monkeypatch.setenv("AI_VIDEO_AGENT_MAX_VARIANTS", "2")
    from backend.app.config import reset_settings
    reset_settings()
    try:
        result = enforce_resource_limits(_intent(scenes=3, variants=3))
        codes = {item["code"] for item in result.data["errors"]}
        assert {"SCENE_LIMIT_EXCEEDED", "VARIANT_LIMIT_EXCEEDED"} <= codes
    finally:
        monkeypatch.delenv("AI_VIDEO_AGENT_MAX_SCENES", raising=False)
        monkeypatch.delenv("AI_VIDEO_AGENT_MAX_VARIANTS", raising=False)
        reset_settings()

def test_apply_v2_rejects_over_limit_before_create(monkeypatch):
    # Make the limit deliberately smaller than the default generated workflow.
    monkeypatch.setenv("AI_VIDEO_AGENT_MAX_NODES", "2")
    from backend.app.config import reset_settings
    reset_settings()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        preview = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": "生成一个场景的视频"},
        ).json()
        assert any(e["code"] == "NODE_LIMIT_EXCEEDED" for e in preview["validation_errors"])
        applied = client.post("/api/agent/apply-v2", json={"intent": preview["intent"]})
        assert applied.status_code == 200
        assert applied.json()["success"] is False
        assert "limit" in applied.json()["error"].lower()
    finally:
        monkeypatch.delenv("AI_VIDEO_AGENT_MAX_NODES", raising=False)
        reset_settings()
