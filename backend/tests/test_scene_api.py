"""Tests for Scene API endpoints."""

import sys
from pathlib import Path

import pytest

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)
from backend.app.services.scene_service import SceneService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_BUNDLE_DICT = {
    "schemaVersion": "1.0",
    "storyboardId": "sb-001",
    "workflowId": "wf-001",
    "executionId": "ex-001",
    "title": "Test Bundle",
    "globalStyle": "cinematic",
    "negativePrompt": "blurry",
    "scenes": [
        {
            "sceneId": "s1",
            "index": 0,
            "title": "Opening",
            "narration": "The sun rises.",
            "durationSeconds": 5.0,
            "locked": False,
            "image": {"prompt": "Sunrise image"},
            "video": {"prompt": "Sunrise video"},
        },
        {
            "sceneId": "s2",
            "index": 1,
            "title": "Journey",
            "narration": "Walking forward.",
            "durationSeconds": 8.0,
            "locked": False,
            "image": {"prompt": "Journey image"},
            "video": {"prompt": "Journey video"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Use FastAPI TestClient (same pattern as test_api.py)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture(autouse=True)
def fresh_scene_service():
    """Reset the scene service singleton before each test and ensure DB tables exist."""
    from backend.app.api import scenes as scenes_module
    from backend.app.db.connection import init_db, get_connection

    init_db()
    original = scenes_module._scene_service
    scenes_module._scene_service = SceneService()
    # Clean up any leftover scene_drafts from previous tests
    conn = get_connection()
    conn.execute("DELETE FROM scene_drafts")
    conn.commit()
    yield
    scenes_module._scene_service = original


client = TestClient(app)

WORKFLOW_ID = "wf-test"


class TestCreateDraft:
    def test_create_draft(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "draft_id" in body
        assert body["scene_count"] == 2

    def test_create_draft_invalid_bundle(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": {"invalid": True}},
        )
        assert resp.status_code == 422


class TestListDrafts:
    def test_list_drafts_empty(self):
        resp = client.get(f"/api/workflows/{WORKFLOW_ID}/scene-drafts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_drafts_with_entries(self):
        client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        resp = client.get(f"/api/workflows/{WORKFLOW_ID}/scene-drafts")
        assert resp.status_code == 200
        drafts = resp.json()
        assert len(drafts) == 1
        assert drafts[0]["name"] == "Test Bundle"


class TestGetDraft:
    def test_get_draft(self):
        create_resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        draft_id = create_resp.json()["draft_id"]

        resp = client.get(f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Test Bundle"
        assert len(body["scenes"]) == 2

    def test_get_draft_not_found(self):
        resp = client.get(f"/api/workflows/{WORKFLOW_ID}/scene-drafts/nonexistent")
        assert resp.status_code == 404


class TestUpdateScene:
    def test_update_scene(self):
        create_resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        draft_id = create_resp.json()["draft_id"]

        resp = client.put(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}/scenes/0",
            json={"updates": {"narration": "Updated narration"}},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify update persisted
        get_resp = client.get(f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}")
        assert get_resp.json()["scenes"][0]["narration"] == "Updated narration"

    def test_update_scene_not_found(self):
        resp = client.put(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/nonexistent/scenes/0",
            json={"updates": {"narration": "x"}},
        )
        assert resp.status_code == 404


class TestLockUnlockScene:
    def test_lock_scene(self):
        create_resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        draft_id = create_resp.json()["draft_id"]

        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}/scenes/0/lock",
        )
        assert resp.status_code == 200
        assert resp.json()["locked"] is True

    def test_unlock_scene(self):
        create_resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        draft_id = create_resp.json()["draft_id"]

        # Lock first
        client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}/scenes/0/lock",
        )

        # Then unlock
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/{draft_id}/scenes/0/unlock",
        )
        assert resp.status_code == 200
        assert resp.json()["locked"] is False

    def test_lock_scene_not_found(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/nonexistent/scenes/0/lock",
        )
        assert resp.status_code == 404

    def test_unlock_scene_not_found(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/nonexistent/scenes/0/unlock",
        )
        assert resp.status_code == 404


class TestImportBundle:
    def test_import_bundle(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/import",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "draft_id" in body
        assert body["scene_count"] == 2

    def test_import_invalid_bundle(self):
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts/import",
            json={"bundle": {"bad": True}},
        )
        assert resp.status_code == 422


class TestExportBundle:
    def _create_bundle(self) -> str:
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        return resp.json()["draft_id"]

    def test_export_json(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "json"
        import json
        parsed = json.loads(body["content"])
        assert parsed["title"] == "Test Bundle"

    def test_export_markdown(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "markdown"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "markdown"
        assert "Test Bundle" in body["content"]

    def test_export_csv(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "csv"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "csv"
        assert "sceneId" in body["content"]

    def test_export_text(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "text"})
        assert resp.status_code == 200
        body = resp.json()
        assert "[Scene 0]" in body["content"]

    def test_export_qwen_jsonl(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "qwen_jsonl"})
        assert resp.status_code == 200
        assert body["format"] == "qwen_jsonl" if (body := resp.json()) and False else True
        assert resp.json()["format"] == "qwen_jsonl"

    def test_export_wan3_jsonl(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "wan3_jsonl"})
        assert resp.status_code == 200
        assert resp.json()["format"] == "wan3_jsonl"

    def test_export_unsupported_format(self):
        draft_id = self._create_bundle()
        resp = client.get(f"/api/scene-bundles/{draft_id}/export", params={"format": "xml"})
        assert resp.status_code == 400

    def test_export_not_found(self):
        resp = client.get("/api/scene-bundles/nonexistent/export")
        assert resp.status_code == 404


class TestValidateBundle:
    def _create_bundle(self) -> str:
        resp = client.post(
            f"/api/workflows/{WORKFLOW_ID}/scene-drafts",
            json={"bundle": SAMPLE_BUNDLE_DICT},
        )
        return resp.json()["draft_id"]

    def test_validate_clean_bundle(self):
        draft_id = self._create_bundle()
        resp = client.post(f"/api/scene-bundles/{draft_id}/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["issue_count"] == 0

    def test_validate_bundle_with_issues(self):
        # Modify bundle to have a security issue
        from backend.app.api import scenes as scenes_module
        bundle = scenes_module._scene_service.get_draft(
            scenes_module._scene_service.create_draft(
                ScenePromptBundle(**{
                    **SAMPLE_BUNDLE_DICT,
                    "scenes": [
                        {
                            **SAMPLE_BUNDLE_DICT["scenes"][0],
                            "image": {"prompt": "Use key sk-abcdefghijklmnopqrstuvwxyz123456"},
                        },
                        SAMPLE_BUNDLE_DICT["scenes"][1],
                    ],
                })
            )
        )
        # Use the draft we just created
        draft_id = scenes_module._scene_service.create_draft(
            ScenePromptBundle(**{
                **SAMPLE_BUNDLE_DICT,
                "scenes": [
                    {
                        **SAMPLE_BUNDLE_DICT["scenes"][0],
                        "image": {"prompt": "Use key sk-abcdefghijklmnopqrstuvwxyz123456"},
                    },
                    SAMPLE_BUNDLE_DICT["scenes"][1],
                ],
            })
        )
        resp = client.post(f"/api/scene-bundles/{draft_id}/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert body["issue_count"] > 0

    def test_validate_not_found(self):
        resp = client.post("/api/scene-bundles/nonexistent/validate")
        assert resp.status_code == 404
