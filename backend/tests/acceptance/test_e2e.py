"""Acceptance tests — end-to-end workflow validation."""

import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers
from backend.app.db.connection import close_connection, init_db
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
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    with TestClient(app) as c:
        yield c
    clear_providers()


class TestEndToEndPipeline:
    """端到端流水线测试。"""

    def test_full_pipeline_mock_mode(self, client):
        """完整流水线（Mock 模式）：提示词 → 工作流 → 执行。"""
        # 1. 生成工作流
        gen_resp = client.post("/api/agent/generate", json={
            "prompt": "创建一个关于自然风光的短视频",
        })
        assert gen_resp.status_code == 200
        workflow = gen_resp.json()
        workflow_id = workflow["id"]

        # 2. 验证工作流结构
        assert len(workflow["nodes"]) >= 4
        assert len(workflow["edges"]) >= 3

        # 3. 执行工作流
        exec_resp = client.post("/api/executions/start", json={
            "workflow_id": workflow_id,
        })
        # 执行可能返回 200 或 201
        assert exec_resp.status_code in (200, 201)
        execution = exec_resp.json()
        execution_id = execution.get("execution_id") or execution.get("id")

        # 4. 查询执行状态
        if execution_id:
            status_resp = client.get(f"/api/executions/{execution_id}")
            assert status_resp.status_code == 200

    def test_template_workflow(self, client):
        """模板工作流：从模板创建 → 验证结构。"""
        # 1. 获取模板列表
        templates_resp = client.get("/api/templates")
        assert templates_resp.status_code == 200
        templates = templates_resp.json()
        assert len(templates) >= 3

        # 2. 从模板创建工作流
        create_resp = client.post("/api/templates/prompt-to-video/create", json={
            "name": "模板测试视频",
            "prompt": "城市风光",
        })
        assert create_resp.status_code == 200
        workflow = create_resp.json()

        # 3. 验证工作流
        assert len(workflow["nodes"]) == 6
        assert workflow["name"] == "模板测试视频"

    def test_import_export_roundtrip(self, client):
        """导入导出往返测试。"""
        # 1. 创建工作流
        create_resp = client.post("/api/workflows", json={
            "id": "roundtrip-test",
            "name": "往返测试",
            "nodes": [
                {"id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
                 "data": {"label": "Input", "description": "", "kind": "textInput",
                          "outputType": "text", "config": {"prompt": "test"}}},
            ],
            "edges": [],
        })
        assert create_resp.status_code in (200, 201)

        # 2. 导出 (返回 {"spec": {...}})
        export_resp = client.post("/api/workflows/roundtrip-test/export")
        assert export_resp.status_code == 200
        exported = export_resp.json()

        # 3. 导入 (需要修改 ID 以避免冲突)
        spec_data = exported.get("spec", exported)
        spec_data["id"] = "roundtrip-imported"  # 新 ID
        import_resp = client.post("/api/workflows/import", json=spec_data)
        assert import_resp.status_code in (200, 201)
        imported = import_resp.json()

        # 4. 验证导入成功
        assert imported["id"] == "roundtrip-imported"


class TestAgentCapabilities:
    """Agent 能力测试。"""

    def test_agent_generate_and_modify(self, client):
        """Agent 生成 + 修改工作流。"""
        # 1. 生成
        gen_resp = client.post("/api/agent/generate", json={
            "prompt": "测试视频",
        })
        workflow = gen_resp.json()
        workflow_id = workflow["id"]

        # 2. 修改
        modify_resp = client.post("/api/agent/modify", json={
            "workflow_id": workflow_id,
            "instruction": "添加更多场景",
        })
        assert modify_resp.status_code == 200
        patch = modify_resp.json()["patch"]

        # 3. 应用 patch
        apply_resp = client.post("/api/agent/apply-patch", json={
            "workflow_id": workflow_id,
            "patch": patch,
        })
        assert apply_resp.status_code == 200

    def test_agent_explain_workflow(self, client):
        """Agent 解释工作流。"""
        gen_resp = client.post("/api/agent/generate", json={
            "prompt": "测试",
        })
        workflow_id = gen_resp.json()["id"]

        explain_resp = client.post("/api/agent/explain", json={
            "workflow_id": workflow_id,
        })
        assert explain_resp.status_code == 200
        assert "explanation" in explain_resp.json()


class TestConfigurationManagement:
    """配置管理测试。"""

    def test_get_and_update_settings(self, client):
        """获取并更新设置。"""
        # 1. 获取当前设置
        get_resp = client.get("/api/config/settings")
        assert get_resp.status_code == 200
        settings = get_resp.json()

        # 2. 更新设置
        update_resp = client.put("/api/config/settings", json={
            "default_llm_provider": "mock",
            "ollama_model": "llama3.2",
        })
        assert update_resp.status_code == 200

        # 3. 验证更新
        get_resp2 = client.get("/api/config/settings")
        assert get_resp2.json()["ollama_model"] == "llama3.2"

    def test_provider_listing(self, client):
        """Provider 列表。"""
        resp = client.get("/api/config/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert any(p["name"] == "mock" for p in providers)


class TestWorkflowManagement:
    """工作流管理测试。"""

    def test_crud_operations(self, client):
        """CRUD 操作完整流程。"""
        # Create
        create_resp = client.post("/api/workflows", json={
            "id": "crud-test",
            "name": "CRUD 测试",
            "nodes": [],
            "edges": [],
        })
        assert create_resp.status_code in (200, 201)

        # Read
        get_resp = client.get("/api/workflows/crud-test")
        assert get_resp.status_code == 200

        # Update (API 格式: {spec: {...}, expected_version: N})
        get_data = get_resp.json()
        version = get_data.get("version", 1)
        update_resp = client.put("/api/workflows/crud-test", json={
            "spec": {
                "id": "crud-test",
                "name": "更新名称",
                "nodes": [],
                "edges": [],
            },
            "expected_version": version,
        })
        assert update_resp.status_code == 200

        # Delete
        delete_resp = client.delete("/api/workflows/crud-test")
        assert delete_resp.status_code == 204

        # Verify deleted
        get_resp2 = client.get("/api/workflows/crud-test")
        assert get_resp2.status_code == 404

    def test_duplicate_workflow(self, client):
        """复制工作流。"""
        # 创建
        client.post("/api/workflows", json={
            "id": "dup-source",
            "name": "源工作流",
            "nodes": [],
            "edges": [],
        })

        # 复制
        dup_resp = client.post("/api/workflows/dup-source/duplicate")
        assert dup_resp.status_code in (200, 201)
        dup = dup_resp.json()

        # 验证是不同 ID
        assert dup["id"] != "dup-source"
