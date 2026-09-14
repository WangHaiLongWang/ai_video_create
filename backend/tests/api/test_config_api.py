"""Tests for configuration API."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers


@pytest.fixture
def client():
    """Create test client."""
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    with TestClient(app) as c:
        yield c
    clear_providers()


class TestConfigAPI:
    """Tests for configuration endpoints."""

    def test_get_providers(self, client):
        """Test listing providers."""
        response = client.get("/api/config/providers")
        assert response.status_code == 200
        providers = response.json()
        assert isinstance(providers, list)
        assert len(providers) >= 1
        assert any(p["name"] == "mock" for p in providers)

    def test_get_settings(self, client):
        """Test getting settings."""
        response = client.get("/api/config/settings")
        assert response.status_code == 200
        settings = response.json()
        assert "default_llm_provider" in settings
        assert "default_image_provider" in settings
        assert "asset_dir" in settings
        # Should not expose API keys
        assert "openai_api_key" not in settings

    def test_update_settings(self, client):
        """Test updating settings."""
        response = client.put("/api/config/settings", json={
            "default_llm_provider": "mock",
            "ollama_model": "llama3.2",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_update_invalid_provider(self, client):
        """Test updating with invalid provider type."""
        response = client.put("/api/config/settings", json={
            "default_llm_provider": "invalid_provider",
        })
        assert response.status_code == 400

    def test_test_provider(self, client):
        """Test provider health check."""
        response = client.post("/api/config/test-provider", json={
            "provider_name": "mock",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "mock"
        assert data["healthy"] is True

    def test_test_nonexistent_provider(self, client):
        """Test health check for nonexistent provider."""
        response = client.post("/api/config/test-provider", json={
            "provider_name": "nonexistent",
        })
        assert response.status_code == 404

    def test_list_assets(self, client):
        """Test listing assets."""
        response = client.get("/api/config/assets")
        assert response.status_code == 200
        assets = response.json()
        assert isinstance(assets, list)

    def test_get_asset_stats(self, client):
        """Test getting asset stats."""
        response = client.get("/api/config/assets/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_size" in stats
        assert "counts" in stats
        assert "images" in stats["counts"]

    def test_cleanup_assets(self, client):
        """Test cleaning up old assets."""
        response = client.post("/api/config/assets/cleanup", params={"max_age_days": 7})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "deleted_count" in data


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "python" in data
        assert "version" in data
