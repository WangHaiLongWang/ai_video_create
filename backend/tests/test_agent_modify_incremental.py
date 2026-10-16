"""MOD-R3-004 backend — Agent modify is incremental (patch/diff/destructive/module diffs).

Covers:
- AgentPreviewResponse gains patch/diff/destructive/module_diffs on modify
- node-id preservation ("修改不重建") through spec -> intent -> compile
- apply-v2 applies incrementally (untouched node ids survive)
- module_diffs classification: added / removed / upgraded / reconfigured
- MockProvider returns an incremental (non-rebuild) response for modify prompts
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db
from backend.app.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test uses a temporary database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Force the deterministic MockProvider regardless of env settings."""
    from backend.app.providers.mock_provider import MockProvider

    monkeypatch.setattr(
        "backend.app.providers.get_provider",
        lambda _name: MockProvider(delay=0),
    )


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def managed_client():
    with client:
        yield


def _valid_intent_dict() -> dict:
    """A valid 6-node pipeline intent (aliases deliberately not kind names)."""
    return {
        "name": "Incremental Test Workflow",
        "nodes": [
            {"alias": "input", "kind": "textInput", "config": {"prompt": "test"}},
            {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 3}},
            {"alias": "img", "kind": "textToImage"},
            {"alias": "vid", "kind": "imageToVideo"},
            {"alias": "concat", "kind": "videoConcat"},
            {"alias": "output", "kind": "output"},
        ],
        "connections": [
            {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}},
            {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "img", "port": "scene"}, "mode": "map"},
            {"source": {"node": "img", "port": "image"}, "target": {"node": "vid", "port": "image"}, "mode": "map"},
            {"source": {"node": "vid", "port": "video"}, "target": {"node": "concat", "port": "video"}, "mode": "aggregate"},
            {"source": {"node": "concat", "port": "video"}, "target": {"node": "output", "port": "video"}},
        ],
    }


def _create_workflow() -> tuple[str, int, dict]:
    """Create a workflow via apply-v2. Returns (workflow_id, version, spec)."""
    resp = client.post("/api/agent/apply-v2", json={"intent": _valid_intent_dict()})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True, data
    workflow_id = data["workflow_id"]

    from backend.app.repositories.workflows import get_workflow

    wf = get_workflow(workflow_id)
    return workflow_id, data["version"], wf["spec"]


# ---------------------------------------------------------------------------
# Node identity passthrough (spec -> NodeIntent -> compile)
# ---------------------------------------------------------------------------


class TestNodeIdPreservation:
    def test_compile_prefers_original_node_id(self):
        from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
        from backend.app.services.agent_compiler import compile_intent

        intent = WorkflowIntent(
            name="ids",
            nodes=[
                NodeIntent(alias="input", kind="textInput", nodeId="original-id-1"),
                NodeIntent(alias="story", kind="storyboard"),
            ],
            connections=[],
        )
        compiled = compile_intent(intent)
        ids = [n["id"] for n in compiled["nodes"]]
        assert ids[0] == "original-id-1"
        # No original id -> deterministic alias-derived id
        assert ids[1].startswith("story-")

    def test_compile_without_node_id_unchanged(self):
        from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
        from backend.app.services.agent_compiler import compile_intent

        intent = WorkflowIntent(
            name="ids",
            nodes=[NodeIntent(alias="story", kind="storyboard")],
        )
        compiled = compile_intent(intent)
        node_id = compiled["nodes"][0]["id"]
        assert node_id.startswith("story-")
        assert len(node_id) == len("story-") + 8

    def test_spec_to_intent_carries_original_node_ids(self):
        from backend.app.api.agent_v2 import _spec_to_intent

        _, _, spec = _create_workflow()
        intent = _spec_to_intent(spec, "carry")
        original_ids = {n["id"] for n in spec["nodes"]}
        intent_ids = {n.node_id for n in intent.nodes}
        assert intent_ids == original_ids

    def test_restore_original_ids_by_alias_and_kind(self):
        from backend.app.api.agent_v2 import _restore_original_ids
        from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent

        existing = WorkflowIntent(
            name="e",
            nodes=[
                NodeIntent(alias="input", kind="textInput", nodeId="id-1"),
                NodeIntent(alias="story", kind="storyboard", nodeId="id-2"),
            ],
        )
        # "story" alias kept -> alias match; "in" is a rewritten alias -> kind match
        parsed = WorkflowIntent(
            name="p",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="story", kind="storyboard"),
                NodeIntent(alias="extra", kind="textToImage"),  # genuinely new
            ],
        )
        restored = _restore_original_ids(parsed, existing)
        assert restored.nodes[0].node_id == "id-1"
        assert restored.nodes[1].node_id == "id-2"
        assert restored.nodes[2].node_id is None


# ---------------------------------------------------------------------------
# compute_graph_patch / apply_graph_patch / generate_diff
# ---------------------------------------------------------------------------


class TestComputeGraphPatch:
    def test_config_only_change_is_small_and_non_destructive(self):
        from backend.app.services.agent_diff import (
            compute_graph_patch, generate_diff, is_destructive,
        )

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        for node in compiled["nodes"]:
            if node["data"]["kind"] == "storyboard":
                node["data"]["config"]["mockTweak"] = "modified"

        patch = compute_graph_patch(existing, compiled)
        assert patch.add_nodes == []
        assert patch.remove_nodes == []
        assert patch.remove_edges == []
        assert patch.add_edges == []
        assert len(patch.update_nodes) == 1
        assert patch.update_nodes[0].id in {n["id"] for n in existing["nodes"]}
        assert is_destructive(patch) is False
        assert "~ 更新 1 个节点" in generate_diff(existing, patch)

    def test_untouched_nodes_not_in_update_list(self):
        from backend.app.services.agent_diff import compute_graph_patch

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        changed_id = None
        for node in compiled["nodes"]:
            if node["data"]["kind"] == "textInput":
                node["data"]["config"]["prompt"] = "changed"
                changed_id = node["id"]
        patch = compute_graph_patch(existing, compiled)
        assert [u.id for u in patch.update_nodes] == [changed_id]

    def test_node_delete_is_destructive(self):
        from backend.app.services.agent_diff import (
            check_destructive, compute_graph_patch, is_destructive,
        )

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        removed_id = compiled["nodes"].pop()["id"]  # drop output node
        compiled["edges"] = [
            e for e in compiled["edges"] if e["target"] != removed_id
        ]

        patch = compute_graph_patch(existing, compiled)
        assert patch.remove_nodes == [removed_id]
        assert is_destructive(patch) is True
        warnings = check_destructive(patch)
        assert any("将删除" in w and "节点" in w for w in warnings)

    def test_unchanged_graph_has_empty_patch(self):
        from backend.app.services.agent_diff import (
            compute_graph_patch, generate_diff, is_destructive,
        )

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        patch = compute_graph_patch(existing, compiled)
        assert patch.add_nodes == [] and patch.remove_nodes == []
        assert patch.update_nodes == [] and patch.add_edges == [] and patch.remove_edges == []
        assert is_destructive(patch) is False
        assert generate_diff(existing, patch) == "(无变更)"

    def test_edge_regen_ids_do_not_churn(self):
        """Edges matched by topology — regenerated edge ids are not a diff."""
        from backend.app.services.agent_diff import compute_graph_patch

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        for edge in compiled["edges"]:
            edge["id"] = "regenerated-" + edge["id"]
        patch = compute_graph_patch(existing, compiled)
        assert patch.add_edges == [] and patch.remove_edges == []

    def test_apply_graph_patch_preserves_untouched(self):
        from backend.app.services.agent_diff import (
            apply_graph_patch, compute_graph_patch,
        )

        _, _, existing = _create_workflow()
        compiled = json.loads(json.dumps(existing))
        for node in compiled["nodes"]:
            if node["data"]["kind"] == "storyboard":
                node["data"]["config"]["mockTweak"] = "modified"
        patch = compute_graph_patch(existing, compiled)
        patched = apply_graph_patch(existing, patch, compiled=compiled)

        assert [n["id"] for n in patched["nodes"]] == [n["id"] for n in existing["nodes"]]
        assert [e["id"] for e in patched["edges"]] == [e["id"] for e in existing["edges"]]
        old_by_id = {n["id"]: n for n in existing["nodes"]}
        for node in patched["nodes"]:
            if node["data"]["kind"] == "storyboard":
                assert node["data"]["config"]["mockTweak"] == "modified"
            else:
                assert node == old_by_id[node["id"]]


# ---------------------------------------------------------------------------
# compute_module_diffs
# ---------------------------------------------------------------------------


def _module(version: str, extra_field: bool = False):
    from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy

    properties = {
        "model": {"type": "string", "title": "Model", "default": "gpt-4"},
        "variantCount": {"type": "integer", "title": "Variants", "default": 1},
    }
    if extra_field:
        properties["seed"] = {"type": "integer", "title": "Seed", "default": 0}
    return ModuleDefinition(
        id="test.module",
        version=version,
        status="published",
        baseKind="textToImage",
        category="image",
        label="Test Module",
        description="A test module",
        providerPolicy=ProviderPolicy(
            capability="image", allowed=["openai"], default="openai", locked=False,
        ),
        configSchema={"properties": properties, "required": ["model"]},
        ports={
            "inputs": [{"id": "scene", "type": "scene", "required": True, "cardinality": "one"}],
            "outputs": [{"id": "image", "type": "image", "required": False, "cardinality": "one"}],
        },
    )


def _module_node(node_id: str, module_version: str | None, overrides: dict | None = None) -> dict:
    data = {
        "label": "图片",
        "description": "",
        "kind": "textToImage",
        "config": {"model": "gpt-4"},
    }
    if module_version is not None:
        data.update({
            "moduleId": "test.module",
            "moduleVersion": module_version,
            "configOverrides": overrides or {},
        })
    return {"id": node_id, "type": "studio", "position": {"x": 0, "y": 0}, "data": data}


def _spec_with_nodes(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


class TestComputeModuleDiffs:
    def test_upgraded_uses_compute_module_diff(self, monkeypatch):
        import backend.app.services.module_registry as registry_module
        from backend.app.services.agent_diff import compute_module_diffs
        from backend.app.services.module_registry import ModuleRegistry

        registry = ModuleRegistry()
        registry._modules.setdefault("test.module", {})["1.0.0"] = _module("1.0.0")
        registry._modules.setdefault("test.module", {})["2.0.0"] = _module("2.0.0", extra_field=True)
        monkeypatch.setattr(registry_module, "_registry", registry)

        existing = _spec_with_nodes(_module_node("n1", "1.0.0"))
        compiled = _spec_with_nodes(_module_node("n1", "2.0.0"))
        entries = compute_module_diffs(existing, compiled)

        assert len(entries) == 1
        entry = entries[0]
        assert entry["type"] == "upgraded"
        assert entry["nodeId"] == "n1"
        assert entry["moduleId"] == "test.module"
        assert entry["from"] == "1.0.0"
        assert entry["to"] == "2.0.0"
        assert entry["details"]["versionFrom"] == "1.0.0"
        assert entry["details"]["versionTo"] == "2.0.0"
        assert any(f.get("key") == "seed" for f in entry["details"]["addedFields"])

    def test_reconfigured_reports_changed_keys(self):
        from backend.app.services.agent_diff import compute_module_diffs

        existing = _spec_with_nodes(
            _module_node("n1", "1.0.0", {"variantCount": 1, "model": "gpt-4"})
        )
        compiled = _spec_with_nodes(
            _module_node("n1", "1.0.0", {"variantCount": 3, "model": "gpt-4"})
        )
        entries = compute_module_diffs(existing, compiled)

        assert len(entries) == 1
        entry = entries[0]
        assert entry["type"] == "reconfigured"
        assert entry["details"]["changedKeys"] == ["variantCount"]
        assert entry["details"]["from"] == {"variantCount": 1}
        assert entry["details"]["to"] == {"variantCount": 3}

    def test_module_added_and_removed(self):
        from backend.app.services.agent_diff import compute_module_diffs

        existing = _spec_with_nodes(_module_node("n1", None), _module_node("n2", "1.0.0"))
        compiled = _spec_with_nodes(_module_node("n1", "1.0.0"), _module_node("n2", None))
        entries = compute_module_diffs(existing, compiled)

        by_type = {(e["nodeId"], e["type"]): e for e in entries}
        assert by_type[("n1", "added")]["from"] is None
        assert by_type[("n1", "added")]["to"] == "1.0.0"
        assert by_type[("n2", "removed")]["from"] == "1.0.0"
        assert by_type[("n2", "removed")]["to"] is None

    def test_node_removal_with_module_is_removed(self):
        from backend.app.services.agent_diff import compute_module_diffs

        existing = _spec_with_nodes(_module_node("n1", "1.0.0"))
        compiled = _spec_with_nodes()
        entries = compute_module_diffs(existing, compiled)
        assert entries[0]["type"] == "removed"

    def test_unchanged_module_yields_no_entries(self):
        from backend.app.services.agent_diff import compute_module_diffs

        node = _module_node("n1", "1.0.0", {"variantCount": 2})
        entries = compute_module_diffs(_spec_with_nodes(node), _spec_with_nodes(node))
        assert entries == []


# ---------------------------------------------------------------------------
# MockProvider determinism for modify
# ---------------------------------------------------------------------------


class TestMockProviderModify:
    @pytest.mark.asyncio
    async def test_modify_prompt_is_incremental_not_rebuild(self):
        from backend.app.providers.mock_provider import MockProvider

        context = {
            "name": "保持拓扑",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {"prompt": "p"},
                 "nodeId": "id-1"},
                {"alias": "story", "kind": "storyboard", "config": {"scenes": 3},
                 "nodeId": "id-2"},
                {"alias": "output", "kind": "output", "config": {}, "nodeId": "id-3"},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"},
                 "target": {"node": "story", "port": "prompt"}, "mode": "direct"},
                {"source": {"node": "story", "port": "scenes"},
                 "target": {"node": "output", "port": "video"}, "mode": "direct"},
            ],
            "scene_count": 3,
        }
        prompt = (
            "Modify this existing WorkflowIntent: "
            + json.dumps(context, ensure_ascii=False)
            + "\nInstruction: 微调配置"
        )
        provider = MockProvider(delay=0)
        text = await provider.generate_text(prompt)
        data = json.loads(text)

        assert [n["alias"] for n in data["nodes"]] == [n["alias"] for n in context["nodes"]]
        assert [n["kind"] for n in data["nodes"]] == [n["kind"] for n in context["nodes"]]
        assert data["connections"] == context["connections"]
        # Exactly one config value tweaked (storyboard preferred)
        tweaked = [n for n in data["nodes"] if (n.get("config") or {}).get("mockTweak")]
        assert len(tweaked) == 1
        assert tweaked[0]["kind"] == "storyboard"
        for node in data["nodes"]:
            if node is not tweaked[0]:
                assert node["config"] == next(
                    c["config"] for c in context["nodes"] if c["alias"] == node["alias"]
                )

    @pytest.mark.asyncio
    async def test_graphpatch_prompt_still_returns_empty_patch(self):
        from backend.app.providers.mock_provider import MockProvider

        prompt = "当前工作流：\n...\n请生成一个 GraphPatch JSON，包含以下字段：add_nodes ..."
        text = await MockProvider(delay=0).generate_text(prompt)
        data = json.loads(text)
        assert data["add_nodes"] == []
        assert data["remove_nodes"] == []
        assert data["update_nodes"] == []

    @pytest.mark.asyncio
    async def test_modify_prompt_without_context_falls_back(self):
        from backend.app.providers.mock_provider import MockProvider

        text = await MockProvider(delay=0).generate_text(
            "Modify this existing WorkflowIntent: not-json\nInstruction: x"
        )
        data = json.loads(text)
        # Falls back to the workflow shape — parse will template-fallback.
        assert "nodes" in data and "edges" in data


# ---------------------------------------------------------------------------
# modify-preview-v2 endpoint (patch/diff/destructive/module_diffs contract)
# ---------------------------------------------------------------------------


class TestModifyPreviewV2Incremental:
    def test_response_exposes_incremental_fields(self):
        workflow_id, _, _ = _create_workflow()
        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "调整分镜配置",
        })
        assert resp.status_code == 200
        data = resp.json()
        for key in ("patch", "diff", "destructive", "module_diffs"):
            assert key in data

    def test_config_only_modify_has_small_patch_and_preserves_ids(self):
        workflow_id, _, existing = _create_workflow()
        original_ids = [n["id"] for n in existing["nodes"]]

        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "调整分镜配置",
        })
        assert resp.status_code == 200
        data = resp.json()

        patch = data["patch"]
        assert patch["add_nodes"] == []
        assert patch["remove_nodes"] == []
        assert patch["add_edges"] == []
        assert patch["remove_edges"] == []
        assert len(patch["update_nodes"]) == 1
        assert data["destructive"] is False
        assert "~ 更新 1 个节点" in data["diff"]
        assert data["module_diffs"] == []

        # 修改不重建: every compiled node keeps its original id
        compiled_ids = [n["id"] for n in data["compiled_workflow"]["nodes"]]
        assert compiled_ids == original_ids
        # The update is a config change on one of those nodes
        assert patch["update_nodes"][0]["id"] in original_ids

    def test_generate_preview_leaves_patch_empty(self):
        resp = client.post("/api/agent/generate-preview-v2", json={"prompt": "生成视频"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["patch"] is None
        assert data["diff"] is None
        assert data["destructive"] is False
        assert data["module_diffs"] == []

    def test_missing_workflow_keeps_patch_none(self):
        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": "wf-missing",
            "instruction": "重命名",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["patch"] is None
        assert data["diff"] is None

    def test_delete_modify_is_destructive(self, monkeypatch):
        from backend.app.api.agent_v2 import _spec_to_intent

        workflow_id, _, existing = _create_workflow()

        async def fake_modify(wf_id: str, instruction: str):
            intent = _spec_to_intent(existing, "trimmed")
            dropped = next(n for n in intent.nodes if n.kind == "output")
            kept = [n for n in intent.nodes if n.node_id != dropped.node_id]
            connections = [
                c for c in intent.connections
                if c.source.node != dropped.alias and c.target.node != dropped.alias
            ]
            return intent.model_copy(update={"nodes": kept, "connections": connections})

        monkeypatch.setattr(
            "backend.app.api.agent_v2._modify_intent_from_prompt", fake_modify
        )
        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "删除输出节点",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["destructive"] is True
        assert len(data["patch"]["remove_nodes"]) == 1
        assert any("将删除" in w for w in data["warnings"])

    def test_module_diffs_populated_on_version_upgrade(self, monkeypatch):
        import backend.app.services.module_registry as registry_module
        from backend.app.api.agent_v2 import _spec_to_intent
        from backend.app.services.module_registry import ModuleRegistry

        registry = ModuleRegistry()
        registry._modules.setdefault("test.module", {})["1.0.0"] = _module("1.0.0")
        registry._modules.setdefault("test.module", {})["2.0.0"] = _module("2.0.0", extra_field=True)
        monkeypatch.setattr(registry_module, "_registry", registry)

        workflow_id, _, existing = _create_workflow()

        async def fake_modify(wf_id: str, instruction: str):
            intent = _spec_to_intent(existing, "upgrade")
            nodes = []
            for node in intent.nodes:
                if node.kind == "textToImage":
                    nodes.append(node.model_copy(update={
                        "node_id": node.node_id,
                        "module_id": "test.module",
                        "module_version": "1.0.0",
                        "config_overrides": {},
                    }))
                else:
                    nodes.append(node)
            return intent.model_copy(update={"nodes": nodes})

        monkeypatch.setattr(
            "backend.app.api.agent_v2._modify_intent_from_prompt", fake_modify
        )
        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "挂载模块",
        })
        assert resp.status_code == 200
        entries = resp.json()["module_diffs"]
        assert any(e["type"] == "added" and e["moduleId"] == "test.module" for e in entries)

        # Now bump the stored spec to 1.0.0 and modify to 2.0.0 -> upgraded
        from backend.app.repositories.workflows import get_workflow, update_workflow

        wf = get_workflow(workflow_id)
        spec = json.loads(json.dumps(wf["spec"]))
        for node in spec["nodes"]:
            if node["data"].get("kind") == "textToImage":
                node["data"].update({
                    "moduleId": "test.module",
                    "moduleVersion": "1.0.0",
                    "configOverrides": {},
                })
        update_workflow(workflow_id, spec, wf["version"])

        async def fake_upgrade(wf_id: str, instruction: str):
            intent = _spec_to_intent(get_workflow(wf_id)["spec"], "upgrade2")
            nodes = [
                n.model_copy(update={"module_version": "2.0.0"})
                if n.kind == "textToImage" else n
                for n in intent.nodes
            ]
            return intent.model_copy(update={"nodes": nodes})

        monkeypatch.setattr(
            "backend.app.api.agent_v2._modify_intent_from_prompt", fake_upgrade
        )
        resp = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "升级模块",
        })
        entries = resp.json()["module_diffs"]
        upgraded = next(e for e in entries if e["type"] == "upgraded")
        assert upgraded["from"] == "1.0.0"
        assert upgraded["to"] == "2.0.0"
        assert upgraded["details"]["versionFrom"] == "1.0.0"


# ---------------------------------------------------------------------------
# apply-v2 incremental (修改不重建 regression)
# ---------------------------------------------------------------------------


class TestApplyV2Incremental:
    def test_apply_preserves_untouched_node_ids(self):
        from backend.app.repositories.workflows import get_workflow

        workflow_id, version, existing = _create_workflow()
        original_ids = [n["id"] for n in existing["nodes"]]

        preview = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "调整分镜配置",
        }).json()
        assert preview["can_apply"] is True

        resp = client.post("/api/agent/apply-v2", json={
            "intent": preview["intent"],
            "workflow_id": workflow_id,
            "expected_version": version,
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        saved = get_workflow(workflow_id)["spec"]
        assert [n["id"] for n in saved["nodes"]] == original_ids
        assert [e["id"] for e in saved["edges"]] == [
            e["id"] for e in existing["edges"]
        ]

        old_by_id = {n["id"]: n for n in existing["nodes"]}
        changed = [
            n for n in saved["nodes"]
            if n["data"].get("config") != old_by_id[n["id"]]["data"].get("config")
        ]
        assert len(changed) == 1
        assert changed[0]["data"]["config"].get("mockTweak") == "modified"

    def test_apply_update_bumps_version_and_keeps_name_change(self):
        from backend.app.repositories.workflows import get_workflow

        workflow_id, version, _ = _create_workflow()
        preview = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "重命名为新版",
        }).json()
        intent = preview["intent"]
        intent["name"] = "Renamed Workflow"

        resp = client.post("/api/agent/apply-v2", json={
            "intent": intent,
            "workflow_id": workflow_id,
            "expected_version": version,
        })
        assert resp.status_code == 200
        assert resp.json()["version"] == version + 1
        assert get_workflow(workflow_id)["name"] == "Renamed Workflow"

    def test_apply_incremental_delete_removes_only_target_node(self, monkeypatch):
        from backend.app.api.agent_v2 import _spec_to_intent
        from backend.app.repositories.workflows import get_workflow

        workflow_id, version, existing = _create_workflow()
        output_id = next(
            n["id"] for n in existing["nodes"] if n["data"]["kind"] == "output"
        )

        async def fake_modify(wf_id: str, instruction: str):
            intent = _spec_to_intent(existing, "trimmed")
            dropped = next(n for n in intent.nodes if n.kind == "output")
            kept = [n for n in intent.nodes if n.node_id != dropped.node_id]
            connections = [
                c for c in intent.connections
                if c.source.node != dropped.alias and c.target.node != dropped.alias
            ]
            return intent.model_copy(update={"nodes": kept, "connections": connections})

        monkeypatch.setattr(
            "backend.app.api.agent_v2._modify_intent_from_prompt", fake_modify
        )
        preview = client.post("/api/agent/modify-preview-v2", json={
            "workflow_id": workflow_id,
            "instruction": "删除输出节点",
        }).json()
        assert preview["destructive"] is True

        resp = client.post("/api/agent/apply-v2", json={
            "intent": preview["intent"],
            "workflow_id": workflow_id,
            "expected_version": version,
        })
        assert resp.status_code == 200, resp.text
        saved = get_workflow(workflow_id)["spec"]
        saved_ids = [n["id"] for n in saved["nodes"]]
        assert output_id not in saved_ids
        assert set(saved_ids) == {
            n["id"] for n in existing["nodes"] if n["id"] != output_id
        }
