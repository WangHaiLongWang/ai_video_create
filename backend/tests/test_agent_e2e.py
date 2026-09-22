"""Backend E2E tests for Agent v2 flow.

Uses FastAPI TestClient to verify the full Agent v2 pipeline:
  - POST /api/agent/generate-preview-v2  (preview)
  - POST /api/agent/apply-v2              (apply)
  - Validation error reporting
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Test: preview image-only workflow
# ---------------------------------------------------------------------------


class TestPreviewImageOnlyWorkflow:
    """POST /api/agent/generate-preview-v2 with prompt that yields image-only pipeline."""

    def test_status_code(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一张图片",
        })
        assert resp.status_code == 200

    def test_intent_present(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一张图片",
        })
        data = resp.json()
        assert "intent" in data
        assert "nodes" in data["intent"]

    def test_node_kinds(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一张图片",
        })
        data = resp.json()
        kinds = {n["kind"] for n in data["intent"]["nodes"]}
        assert "textInput" in kinds
        assert "textToImage" in kinds
        assert "output" in kinds
        # No video nodes for image-only
        assert "imageToVideo" not in kinds
        assert "videoConcat" not in kinds

    def test_edges_present(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一张图片",
        })
        data = resp.json()
        assert "connections" in data["intent"]
        assert len(data["intent"]["connections"]) >= 1

    def test_scene_count(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一个场景",
        })
        data = resp.json()
        assert data["intent"]["scene_count"] == 1

    def test_validation_errors_zero_for_full_pipeline(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一个场景",
        })
        data = resp.json()
        assert len(data["validation_errors"]) == 0

    def test_can_apply_for_full_pipeline(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "只生成一个场景",
        })
        data = resp.json()
        assert data["can_apply"] is True


# ---------------------------------------------------------------------------
# Test: preview full pipeline
# ---------------------------------------------------------------------------


class TestPreviewFullPipeline:
    """POST /api/agent/generate-preview-v2 with prompt that yields full 6-node pipeline."""

    def test_status_code(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        assert resp.status_code == 200

    def test_all_six_kinds_present(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        data = resp.json()
        kinds = {n["kind"] for n in data["intent"]["nodes"]}
        expected = {"textInput", "storyboard", "textToImage", "imageToVideo", "videoConcat", "output"}
        assert expected == kinds

    def test_scene_count(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        data = resp.json()
        assert data["intent"]["scene_count"] == 2

    def test_can_apply(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        data = resp.json()
        assert data["can_apply"] is True

    def test_connections_count(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        data = resp.json()
        assert len(data["intent"]["connections"]) == 5

    def test_cost_estimate_present(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        })
        data = resp.json()
        assert "cost_estimate" in data
        ce = data["cost_estimate"]
        assert ce["scene_count"] == 2
        assert ce["total_calls"] > 0


# ---------------------------------------------------------------------------
# Test: apply workflow
# ---------------------------------------------------------------------------


class TestApplyWorkflow:
    """POST /api/agent/apply-v2 with valid intent."""

    def test_apply_creates_workflow(self, client):
        # First generate a valid intent
        preview = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成一个测试视频",
        }).json()

        intent = preview["intent"]

        # Apply it
        resp = client.post("/api/agent/apply-v2", json={
            "intent": intent,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["workflow_id"] is not None
        assert data["version"] is not None

    def test_apply_returns_workflow_id(self, client):
        preview = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        }).json()

        resp = client.post("/api/agent/apply-v2", json={
            "intent": preview["intent"],
        })
        data = resp.json()
        assert data["success"] is True
        assert data["workflow_id"] is not None
        assert len(data["workflow_id"]) > 0


# ---------------------------------------------------------------------------
# Test: invalid intent
# ---------------------------------------------------------------------------


class TestPreviewInvalidIntent:
    """POST /api/agent/generate-preview-v2 / apply-v2 with invalid data."""

    def test_apply_invalid_intent_fails(self, client):
        resp = client.post("/api/agent/apply-v2", json={
            "intent": {
                "name": "Bad",
                "nodes": [{"alias": "a", "kind": "nonexistent_kind", "config": {}}],
                "connections": [],
            },
        })
        # Should succeed at HTTP level but with validation error
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_apply_duplicate_alias_fails(self, client):
        resp = client.post("/api/agent/apply-v2", json={
            "intent": {
                "name": "Duplicate",
                "nodes": [
                    {"alias": "dup", "kind": "textInput", "config": {}},
                    {"alias": "dup", "kind": "textToImage", "config": {}},
                ],
                "connections": [],
            },
        })
        data = resp.json()
        assert data["success"] is False

    def test_generate_preview_missing_prompt(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={})
        assert resp.status_code == 422  # Pydantic validation error

    def test_generate_preview_empty_prompt(self, client):
        resp = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "",
        })
        assert resp.status_code == 422  # min_length=1


# ---------------------------------------------------------------------------
# Test: preview consistency (generate twice with same prompt -> same structure)
# ---------------------------------------------------------------------------


class TestPreviewConsistency:
    """Two previews with the same prompt should have identical structure."""

    def test_same_structure(self, client):
        r1 = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        }).json()
        r2 = client.post("/api/agent/generate-preview-v2", json={
            "prompt": "生成两个场景的视频",
        }).json()

        assert len(r1["intent"]["nodes"]) == len(r2["intent"]["nodes"])
        assert len(r1["intent"]["connections"]) == len(r2["intent"]["connections"])

        kinds1 = sorted(n["kind"] for n in r1["intent"]["nodes"])
        kinds2 = sorted(n["kind"] for n in r2["intent"]["nodes"])
        assert kinds1 == kinds2

        assert r1["intent"]["scene_count"] == r2["intent"]["scene_count"]
        assert r1["intent"]["variant_count"] == r2["intent"]["variant_count"]
