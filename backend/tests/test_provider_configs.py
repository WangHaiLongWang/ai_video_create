"""HARD-303/304 provider profile acceptance tests."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.db import connection as db
from backend.app.main import app
from backend.app.providers import clear_providers, get_provider, init_providers
from backend.app.repositories.workflows import create_workflow, get_workflow
from backend.app.schemas.module_definition import ModuleDefinition


@pytest.fixture
def client(tmp_path, monkeypatch):
    db.close_connection()
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "providers.db")
    db.init_db()
    clear_providers()
    init_providers(mock=True)
    with TestClient(app) as value:
        yield value
    clear_providers()
    db.close_connection()
    monkeypatch.setattr(db, "_DB_PATH", None)


def _profile(name="Mock A"):
    return {
        "name": name,
        "provider_type": "mock",
        "config": {"model": "mock-v1", "models": ["mock-v1", "mock-v2"]},
        "capabilities": {"text": True, "image": True, "video": True},
        "secrets": {"api_key": "must-never-be-returned"},
    }


def test_crud_is_multi_profile_and_secrets_are_write_only(client):
    first = client.post("/api/config/provider-configs", json=_profile("Mock A"))
    second = client.post("/api/config/provider-configs", json=_profile("Mock B"))
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["has_credentials"] is True
    assert "secrets" not in first.text and "must-never-be-returned" not in first.text

    items = client.get("/api/config/provider-configs").json()
    assert {item["name"] for item in items} >= {"Mock A", "Mock B"}
    config_id = first.json()["id"]
    updated = client.patch(f"/api/config/provider-configs/{config_id}", json={"name": "Mock Primary"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Mock Primary"

    row = db.get_connection().execute(
        "SELECT value, is_encrypted FROM configs WHERE key = ?", (f"provider_config.{config_id}.api_key",)
    ).fetchone()
    assert row["is_encrypted"] == 1
    assert "must-never-be-returned" not in row["value"]

    assert client.delete(f"/api/config/provider-configs/{config_id}").status_code == 204
    assert client.get(f"/api/config/provider-configs/{config_id}").status_code == 404


def test_default_model_discovery_connection_and_lazy_runtime_resolution(client):
    created = client.post("/api/config/provider-configs", json=_profile()).json()
    config_id = created["id"]
    selected = client.post(f"/api/config/provider-configs/{config_id}/default/image")
    assert selected.status_code == 200
    assert selected.json()["default_capabilities"] == ["image"]
    models = client.get(f"/api/config/provider-configs/{config_id}/models").json()
    assert models["models"] == ["mock-v1", "mock-v2"]
    tested = client.post(f"/api/config/provider-configs/{config_id}/test").json()
    assert tested == {"status": "ok", "config_id": config_id, "healthy": True}
    assert getattr(get_provider(config_id), "config_id") == config_id


def test_workflow_and_module_persistence_strip_credentials(client):
    spec = {
        "id": "provider-ref-wf", "name": "provider ref", "schemaVersion": "1.0",
        "nodes": [{"id": "input", "position": {"x": 0, "y": 0}, "data": {
            "label": "input", "kind": "textInput", "config": {
                "providerConfigId": "pc_mock", "api_key": "forbidden", "token": "also-forbidden",
                "api_url": "https://must-not-be-in-workflow.example"
            }}}], "edges": []
    }
    create_workflow(spec)
    stored = get_workflow("provider-ref-wf")["spec"]
    persisted = json.dumps(stored)
    assert stored["nodes"][0]["data"]["config"]["providerConfigId"] == "pc_mock"
    assert "forbidden" not in persisted and "api_key" not in persisted and "token" not in persisted
    assert "api_url" not in persisted and "must-not-be-in-workflow" not in persisted

    module = ModuleDefinition.model_validate({
        "id": "custom.safe", "version": "1.0.0", "baseKind": "textToImage",
        "category": "image", "label": "safe", "providerPolicy": {
            "capability": "image", "providerConfigId": "pc_mock"
        }, "defaultConfig": {"providerConfigId": "pc_mock", "api_key": "forbidden", "base_url": "https://forbidden"},
        "ports": {"inputs": [], "outputs": []}
    })
    assert module.provider_policy.provider_config_id == "pc_mock"
    assert "api_key" not in module.default_config
    assert "base_url" not in module.default_config
