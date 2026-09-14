"""Tests for Template API."""

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


class TestTemplateAPI:
    """Tests for Template endpoints."""

    def test_list_templates(self, client):
        """Test listing templates."""
        response = client.get("/api/templates")
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) >= 3
        ids = [t["id"] for t in templates]
        assert "prompt-to-video" in ids

    def test_get_template(self, client):
        """Test getting template detail."""
        response = client.get("/api/templates/prompt-to-video")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "提示词生成视频"
        assert "spec" in data

    def test_get_nonexistent_template(self, client):
        """Test getting nonexistent template."""
        response = client.get("/api/templates/nonexistent")
        assert response.status_code == 404

    def test_create_from_template(self, client):
        """Test creating workflow from template."""
        response = client.post("/api/templates/prompt-to-video/create", json={
            "name": "我的视频",
            "prompt": "自然风光",
        })
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert data["name"] == "我的视频"

    def test_create_from_nonexistent_template(self, client):
        """Test creating from nonexistent template."""
        response = client.post("/api/templates/nonexistent/create", json={})
        assert response.status_code == 404

    def test_save_as_template(self, client):
        """Test saving workflow as template."""
        # First create a workflow
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        response = client.post("/api/templates/save", json={
            "workflow_id": workflow_id,
            "name": "自定义模板",
            "description": "测试模板",
            "tags": ["测试"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "template_id" in data

    def test_save_nonexistent_workflow(self, client):
        """Test saving nonexistent workflow as template."""
        response = client.post("/api/templates/save", json={
            "workflow_id": "nonexistent",
            "name": "test",
        })
        assert response.status_code == 404
