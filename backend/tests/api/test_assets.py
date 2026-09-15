"""Assets API tests — 资产管理和血缘追踪。"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.connection import close_connection, init_db, get_connection
import backend.app.db.connection as conn_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()
    yield
    close_connection()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_workflow(client):
    """创建一个示例工作流。"""
    resp = client.post("/api/workflows", json={
        "id": "test-wf",
        "name": "测试工作流",
        "nodes": [
            {"id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
             "data": {"label": "Input", "description": "", "kind": "textInput",
                      "outputType": "text", "config": {"prompt": "test"}}},
        ],
        "edges": [],
    })
    return resp.json()


@pytest.fixture
def sample_execution(client, sample_workflow):
    """创建一个示例执行。"""
    resp = client.post(f"/api/executions/{sample_workflow['id']}/start")
    return resp.json()


class TestAssetsCRUD:
    """Assets CRUD 测试。"""

    def test_list_assets_empty(self, client):
        """空列表。"""
        resp = client.get("/api/assets")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_asset_not_found(self, client):
        """获取不存在的资产。"""
        resp = client.get("/api/assets/nonexistent")
        assert resp.status_code == 404

    def test_delete_asset_not_found(self, client):
        """删除不存在的资产。"""
        resp = client.delete("/api/assets/nonexistent")
        assert resp.status_code == 404

    def test_asset_stats_empty(self, client):
        """空统计。"""
        resp = client.get("/api/assets/stats")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestAssetLineage:
    """资产血缘追踪测试。"""

    def test_lineage_not_found(self, client):
        """血缘查询不存在的资产。"""
        resp = client.get("/api/assets/nonexistent/lineage")
        assert resp.status_code == 404

    def test_list_assets_by_execution(self, client, sample_execution):
        """按执行 ID 列出资产。"""
        resp = client.get(f"/api/assets?execution_id={sample_execution['id']}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_assets_by_type(self, client):
        """按类型过滤资产。"""
        resp = client.get("/api/assets?asset_type=image")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
