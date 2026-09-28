"""Round-two vertical acceptance for structured Agent workflow generation."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.workflow_intent_parser import parse_workflow_intent


class StructuredTextProvider:
    """Deterministic text provider exercising the real structured parser."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    async def generate_text(self, prompt: str, config: dict | None = None) -> str:
        self.calls += 1
        assert "WorkflowIntent" in prompt
        return json.dumps(self.payload, ensure_ascii=False)


def _connection(source: str, source_port: str, target: str, target_port: str, mode="direct"):
    return {
        "source": {"node": source, "port": source_port},
        "target": {"node": target, "port": target_port},
        "mode": mode,
    }


def _video_payload() -> dict:
    return {
        "name": "双场景视频",
        "nodes": [
            {"alias": "input", "kind": "textInput", "config": {}},
            {"alias": "story", "kind": "storyboard", "config": {}},
            {"alias": "image", "kind": "textToImage", "config": {}},
            {"alias": "video", "kind": "imageToVideo", "config": {}},
            {"alias": "concat", "kind": "videoConcat", "config": {}},
            {"alias": "output", "kind": "output", "config": {}},
        ],
        "connections": [
            _connection("input", "text", "story", "prompt"),
            _connection("story", "scenes", "image", "scene", "map"),
            _connection("image", "image", "video", "image", "map"),
            _connection("video", "video", "concat", "video", "aggregate"),
            _connection("concat", "video", "output", "video"),
        ],
        "scene_count": 2,
        "variant_count": 2,
        "duration": 5,
    }


@pytest.mark.asyncio
async def test_real_parser_normalizes_image_only_output_semantics():
    payload = {
        "name": "单图",
        "nodes": [
            {"alias": "input", "kind": "textInput", "config": {}},
            {"alias": "story", "kind": "storyboard", "config": {}},
            {"alias": "image", "kind": "textToImage", "config": {}},
            # Simulate a model following the obsolete image -> output.video shape.
            {"alias": "output", "kind": "output", "config": {}},
        ],
        "connections": [
            _connection("input", "text", "story", "prompt"),
            _connection("story", "scenes", "image", "scene", "map"),
            _connection("image", "image", "output", "video"),
        ],
        "scene_count": 1,
    }
    provider = StructuredTextProvider(payload)
    intent = await parse_workflow_intent("只生成一张图片，不要视频", provider)

    assert provider.calls == 1
    assert [node.kind for node in intent.nodes] == ["textInput", "storyboard", "textToImage"]
    assert all(c.target.node != "output" for c in intent.connections)
    assert next(n for n in intent.nodes if n.kind == "storyboard").config["scenes"] == 1


@pytest.mark.asyncio
async def test_real_parser_materializes_two_scenes_variants_and_duration():
    provider = StructuredTextProvider(_video_payload())
    intent = await parse_workflow_intent(
        "生成两个场景，每个场景两张图，每张图生成5秒视频并合成", provider
    )

    assert (intent.scene_count, intent.variant_count, intent.duration) == (2, 2, 5)
    assert next(n for n in intent.nodes if n.kind == "storyboard").config["scenes"] == 2
    assert next(n for n in intent.nodes if n.kind == "textToImage").config["variantCount"] == 2
    assert next(n for n in intent.nodes if n.kind == "imageToVideo").config["duration"] == 5


@pytest.mark.asyncio
async def test_seedream_module_reference_survives_parser_and_compiler():
    from backend.app.services.agent_compiler import compile_intent

    payload = _video_payload()
    image = next(n for n in payload["nodes"] if n["kind"] == "textToImage")
    image.update({
        "moduleId": "builtin.seedream.text-to-image",
        "moduleVersion": "1.0.0",
        "configOverrides": {"variantCount": 2},
    })
    intent = await parse_workflow_intent("使用 Seedream 生成两张图并生成视频", StructuredTextProvider(payload))
    compiled = compile_intent(intent)
    node = next(n for n in compiled["nodes"] if n["data"]["kind"] == "textToImage")

    assert node["data"]["moduleId"] == "builtin.seedream.text-to-image"
    assert node["data"]["moduleVersion"] == "1.0.0"
    assert node["data"]["configOverrides"]["variantCount"] == 2


def test_unknown_module_is_rejected_by_preview_gate(monkeypatch):
    payload = _video_payload()
    image = next(n for n in payload["nodes"] if n["kind"] == "textToImage")
    image.update({"moduleId": "unknown.image.module", "moduleVersion": "1.0.0"})
    provider = StructuredTextProvider(payload)

    async def generate(prompt: str):
        return await parse_workflow_intent(prompt, provider)

    monkeypatch.setattr("backend.app.api.agent_v2._generate_intent_from_prompt", generate)
    with TestClient(app, raise_server_exceptions=False) as client:
        data = client.post("/api/agent/generate-preview-v2", json={"prompt": "unknown"}).json()
    assert data["can_apply"] is False
    assert any(error["code"] == "COMPILE_FAILED" for error in data["validation_errors"])


def test_draft_module_is_rejected_by_preview_gate(monkeypatch):
    import backend.app.services.module_registry as registry_module
    from backend.app.services.module_registry import BUILTIN_MODULES, ModuleRegistry

    draft = BUILTIN_MODULES["builtin.seedream.text-to-image"].model_copy(
        update={"id": "custom.seedream.draft", "status": "draft"}, deep=True
    )
    registry = ModuleRegistry()
    registry._modules.setdefault(draft.id, {})[draft.version] = draft
    monkeypatch.setattr(registry_module, "_registry", registry)

    payload = _video_payload()
    image = next(n for n in payload["nodes"] if n["kind"] == "textToImage")
    image.update({"moduleId": draft.id, "moduleVersion": draft.version})
    provider = StructuredTextProvider(payload)

    async def generate(prompt: str):
        return await parse_workflow_intent(prompt, provider)

    monkeypatch.setattr("backend.app.api.agent_v2._generate_intent_from_prompt", generate)
    with TestClient(app, raise_server_exceptions=False) as client:
        data = client.post("/api/agent/generate-preview-v2", json={"prompt": "draft"}).json()
    assert data["can_apply"] is False
    assert any(
        error["code"] == "MODULE_MODULE_NOT_PUBLISHED"
        for error in data["validation_errors"]
    )
