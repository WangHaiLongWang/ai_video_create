"""Tests for Agent API v2 endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db
from backend.app.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test uses a temporary database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/agent/generate-preview-v2
# ---------------------------------------------------------------------------


class TestGeneratePreviewV2:
    def test_generate_preview_returns_valid_response(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": "create a ski lesson video with 5 scenes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "cost_estimate" in data
        assert "can_apply" in data
        assert "validation_errors" in data
        assert "repair_steps" in data
        assert "warnings" in data

    def test_generate_preview_intent_structure(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": "test workflow"},
        )
        assert response.status_code == 200
        intent = response.json()["intent"]
        assert "name" in intent
        assert "nodes" in intent
        assert isinstance(intent["nodes"], list)
        assert len(intent["nodes"]) > 0

    def test_generate_preview_has_cost_estimate(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": "test"},
        )
        assert response.status_code == 200
        cost = response.json()["cost_estimate"]
        assert cost is not None
        assert "scene_count" in cost
        assert "total_calls" in cost
        assert "estimated_duration_seconds" in cost
        assert "warnings" in cost

    def test_generate_preview_can_apply(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": "test"},
        )
        assert response.status_code == 200
        # The default intent should be valid, so can_apply should be True
        assert response.json()["can_apply"] is True

    def test_generate_preview_empty_prompt_rejected(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={"prompt": ""},
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_generate_preview_missing_prompt(self):
        response = client.post(
            "/api/agent/generate-preview-v2",
            json={},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/agent/modify-preview-v2
# ---------------------------------------------------------------------------


class TestModifyPreviewV2:
    def test_modify_preview_requires_workflow_id(self):
        response = client.post(
            "/api/agent/modify-preview-v2",
            json={"instruction": "add more scenes"},
        )
        assert response.status_code == 422

    def test_modify_preview_requires_instruction(self):
        response = client.post(
            "/api/agent/modify-preview-v2",
            json={"workflow_id": "wf-123"},
        )
        assert response.status_code == 422

    def test_modify_preview_returns_valid_response(self):
        response = client.post(
            "/api/agent/modify-preview-v2",
            json={"workflow_id": "wf-123", "instruction": "add more scenes"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert "cost_estimate" in data
        assert "can_apply" in data


# ---------------------------------------------------------------------------
# POST /api/agent/apply-v2
# ---------------------------------------------------------------------------


class TestApplyV2:
    def _make_valid_intent(self):
        """Helper to create a valid intent for apply tests."""
        return {
            "name": "Test Apply Workflow",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {"prompt": "test"}},
                {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 3}},
                {"alias": "img", "kind": "textToImage"},
                {"alias": "vid", "kind": "imageToVideo"},
                {"alias": "concat", "kind": "videoConcat"},
                {"alias": "output", "kind": "output"},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}},
                {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "img", "port": "scene"}, "mode": "map"},
                {"source": {"node": "img", "port": "images"}, "target": {"node": "vid", "port": "image"}, "mode": "map"},
                {"source": {"node": "vid", "port": "videos"}, "target": {"node": "concat", "port": "videos"}, "mode": "aggregate"},
                {"source": {"node": "concat", "port": "video"}, "target": {"node": "output", "port": "video"}},
            ],
        }

    def test_apply_requires_intent(self):
        response = client.post("/api/agent/apply-v2", json={})
        assert response.status_code == 422

    def test_apply_creates_new_workflow(self):
        intent = self._make_valid_intent()
        response = client.post(
            "/api/agent/apply-v2",
            json={"intent": intent},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workflow_id"] is not None
        assert data["version"] == 1

    def test_apply_with_invalid_intent_fails(self):
        intent = {
            "name": "Invalid",
            "nodes": [
                {"alias": "x", "kind": "nonexistent_kind"},
            ],
        }
        response = client.post(
            "/api/agent/apply-v2",
            json={"intent": intent},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_apply_update_existing_workflow(self):
        # First create a workflow
        intent = self._make_valid_intent()
        create_resp = client.post(
            "/api/agent/apply-v2",
            json={"intent": intent},
        )
        assert create_resp.status_code == 200
        wf_id = create_resp.json()["workflow_id"]
        version = create_resp.json()["version"]

        # Now update it
        intent["name"] = "Updated Workflow"
        update_resp = client.post(
            "/api/agent/apply-v2",
            json={
                "intent": intent,
                "workflow_id": wf_id,
                "expected_version": version,
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["success"] is True
        assert data["workflow_id"] == wf_id
        assert data["version"] == version + 1

    def test_apply_version_conflict(self):
        # First create a workflow
        intent = self._make_valid_intent()
        create_resp = client.post(
            "/api/agent/apply-v2",
            json={"intent": intent},
        )
        wf_id = create_resp.json()["workflow_id"]

        # Try to update with wrong version
        intent["name"] = "Conflicted"
        update_resp = client.post(
            "/api/agent/apply-v2",
            json={
                "intent": intent,
                "workflow_id": wf_id,
                "expected_version": 99,  # wrong version
            },
        )
        assert update_resp.status_code == 409

    def test_apply_nonexistent_workflow(self):
        intent = self._make_valid_intent()
        response = client.post(
            "/api/agent/apply-v2",
            json={
                "intent": intent,
                "workflow_id": "nonexistent-id",
                "expected_version": 1,
            },
        )
        assert response.status_code == 404
