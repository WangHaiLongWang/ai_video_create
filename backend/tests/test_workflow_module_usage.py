"""Vertical tests for workflow-to-module usage synchronization."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, get_connection, init_db
from backend.app.main import app
from backend.app.repositories.workflows import (
    create_workflow,
    delete_workflow,
    duplicate_workflow,
    update_workflow,
)


def _spec(workflow_id: str, module_id: str | None = "module.image") -> dict:
    data = {
        "label": "Image module",
        "description": "",
        "kind": "textInput",
        "status": "idle",
        "config": {},
    }
    if module_id:
        data.update({"moduleId": module_id, "moduleVersion": "1.2.3"})
    return {
        "schemaVersion": "2.0",
        "id": workflow_id,
        "name": "Module usage workflow",
        "nodes": [
            {
                "id": "image-1",
                "type": "studio",
                "position": {"x": 0, "y": 0},
                "data": data,
            }
        ],
        "edges": [],
    }


def _usage(workflow_id: str) -> list[dict]:
    rows = get_connection().execute(
        "SELECT * FROM module_usage WHERE workflow_id = ? ORDER BY node_id",
        (workflow_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "usage.db")
    close_connection()
    init_db()
    yield
    close_connection()


class TestRepositoryUsageSynchronization:
    def test_create_records_exact_module_reference(self):
        create_workflow(_spec("wf-create"))
        assert _usage("wf-create") == [
            {
                "workflow_id": "wf-create",
                "node_id": "image-1",
                "module_id": "module.image",
                "module_version": "1.2.3",
            }
        ]

    def test_update_replaces_then_removes_stale_usage(self):
        create_workflow(_spec("wf-update", "module.old"))
        update_workflow("wf-update", _spec("wf-update", "module.new"), 1)
        assert [row["module_id"] for row in _usage("wf-update")] == ["module.new"]

        update_workflow("wf-update", _spec("wf-update", None), 2)
        assert _usage("wf-update") == []

    def test_duplicate_uses_new_workflow_id(self):
        create_workflow(_spec("wf-source"))
        duplicate = duplicate_workflow("wf-source")
        usage = _usage(duplicate["id"])
        assert usage[0]["workflow_id"] == duplicate["id"]
        assert usage[0]["module_id"] == "module.image"

    def test_delete_removes_usage(self):
        create_workflow(_spec("wf-delete"))
        delete_workflow("wf-delete")
        assert _usage("wf-delete") == []


class TestApiUsageSynchronization:
    def test_create_update_duplicate_and_import_keep_usage_in_sync(self):
        with TestClient(app) as client:
            assert client.post("/api/workflows", json=_spec("api-create")).status_code == 201
            assert _usage("api-create")[0]["module_id"] == "module.image"

            update = client.put(
                "/api/workflows/api-create",
                json={"spec": _spec("api-create", "module.updated"), "expected_version": 1},
            )
            assert update.status_code == 200
            assert [row["module_id"] for row in _usage("api-create")] == ["module.updated"]

            duplicate = client.post("/api/workflows/api-create/duplicate")
            assert duplicate.status_code == 201
            duplicate_id = duplicate.json()["id"]
            assert [row["module_id"] for row in _usage(duplicate_id)] == ["module.updated"]

            imported = client.post("/api/workflows/import", json=_spec("api-import"))
            assert imported.status_code == 201
            assert [row["module_id"] for row in _usage("api-import")] == ["module.image"]
