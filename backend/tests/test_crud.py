"""Workflow CRUD Repository 测试。"""

import pytest

from backend.app.db.connection import close_connection, init_db
from backend.app.repositories.workflows import (
    OptimisticLockError,
    WorkflowNotFoundError,
    create_workflow,
    delete_workflow,
    duplicate_workflow,
    get_workflow,
    list_workflows,
    update_workflow,
)

SAMPLE_SPEC = {
    "schemaVersion": "1.0",
    "id": "test-crud-1",
    "name": "CRUD 测试工作流",
    "nodes": [
        {
            "id": "n1",
            "type": "studio",
            "position": {"x": 0, "y": 0},
            "data": {"label": "输入", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {"prompt": "测试"}},
        }
    ],
    "edges": [],
}


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


class TestCreate:
    def test_create_workflow(self):
        result = create_workflow(SAMPLE_SPEC)
        assert result["id"] == "test-crud-1"
        assert result["name"] == "CRUD 测试工作流"
        assert result["version"] == 1

    def test_create_with_custom_name(self):
        result = create_workflow(SAMPLE_SPEC, name="自定义名称")
        assert result["name"] == "自定义名称"


class TestRead:
    def test_get_workflow_returns_full_spec(self):
        create_workflow(SAMPLE_SPEC)
        wf = get_workflow("test-crud-1")
        assert wf["id"] == "test-crud-1"
        assert "spec" in wf
        assert wf["spec"]["nodes"][0]["data"]["kind"] == "textInput"

    def test_get_nonexistent_raises(self):
        with pytest.raises(WorkflowNotFoundError):
            get_workflow("nonexistent")

    def test_list_workflows(self):
        create_workflow(SAMPLE_SPEC)
        create_workflow({**SAMPLE_SPEC, "id": "test-crud-2", "name": "第二个"})
        items = list_workflows()
        assert len(items) == 2


class TestUpdate:
    def test_update_increments_version(self):
        create_workflow(SAMPLE_SPEC)
        new_spec = {**SAMPLE_SPEC, "name": "已更新"}
        result = update_workflow("test-crud-1", new_spec, expected_version=1)
        assert result["version"] == 2

    def test_update_optimistic_lock_conflict(self):
        create_workflow(SAMPLE_SPEC)
        with pytest.raises(OptimisticLockError):
            update_workflow("test-crud-1", SAMPLE_SPEC, expected_version=99)

    def test_update_nonexistent_raises(self):
        with pytest.raises(WorkflowNotFoundError):
            update_workflow("nonexistent", SAMPLE_SPEC, expected_version=1)


class TestDelete:
    def test_delete_workflow(self):
        create_workflow(SAMPLE_SPEC)
        delete_workflow("test-crud-1")
        with pytest.raises(WorkflowNotFoundError):
            get_workflow("test-crud-1")

    def test_delete_nonexistent_raises(self):
        with pytest.raises(WorkflowNotFoundError):
            delete_workflow("nonexistent")


class TestDuplicate:
    def test_duplicate_creates_copy(self):
        create_workflow(SAMPLE_SPEC)
        result = duplicate_workflow("test-crud-1")
        assert result["id"] != "test-crud-1"
        assert result["name"] == "CRUD 测试工作流 (副本)"

    def test_duplicate_with_custom_name(self):
        create_workflow(SAMPLE_SPEC)
        result = duplicate_workflow("test-crud-1", new_name="我的副本")
        assert result["name"] == "我的副本"
