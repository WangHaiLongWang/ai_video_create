"""Tests for Agent API."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers


@pytest.fixture
def client():
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    with TestClient(app) as c:
        yield c
    clear_providers()


class TestAgentAPI:
    """Tests for Agent endpoints."""

    def test_generate_workflow(self, client):
        """Test generating workflow from prompt."""
        response = client.post("/api/agent/generate", json={"prompt": "自然风光视频"})
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_modify_workflow(self, client):
        """Test modifying workflow."""
        # First create a workflow
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        # Modify it
        response = client.post("/api/agent/modify", json={
            "workflow_id": workflow_id,
            "instruction": "添加一个输出节点",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "patch" in data

    def test_modify_nonexistent_workflow(self, client):
        """Test modifying nonexistent workflow."""
        response = client.post("/api/agent/modify", json={
            "workflow_id": "nonexistent",
            "instruction": "test",
        })
        assert response.status_code == 404

    def test_explain_workflow(self, client):
        """Test explaining workflow."""
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        response = client.post("/api/agent/explain", json={
            "workflow_id": workflow_id,
        })
        assert response.status_code == 200
        data = response.json()
        assert "explanation" in data

    def test_apply_patch(self, client):
        """Test applying patch to workflow."""
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        # Apply empty patch
        response = client.post("/api/agent/apply-patch", json={
            "workflow_id": workflow_id,
            "patch": {
                "description": "测试 patch",
                "add_nodes": [],
                "remove_nodes": [],
                "update_nodes": [],
                "add_edges": [],
                "remove_edges": [],
            },
        })
        assert response.status_code == 200
