"""Tests for workflow_intent_parser module.

Tests cover:
- Valid WorkflowIntent generation from simple prompts
- Scene count extraction from various Chinese patterns
- Variant count extraction
- Image-only prompts (no video nodes)
- Minimal workflow for single-image prompts
- Fallback when MiMo provider is unavailable
- Fallback when MiMo returns invalid JSON
- MiMo response validation against schema
- System prompt completeness (node kinds, port definitions)
- Multiple requirements parsed correctly
- Chinese/English mixed prompts
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.schemas.workflow_intent import WorkflowIntent
from backend.app.services.workflow_intent_parser import (
    _build_system_prompt,
    _dict_to_intent,
    _extract_scene_count,
    _extract_variant_count,
    _parse_json_response,
    _template_fallback,
    _wants_no_video,
    get_system_prompt,
    parse_workflow_intent,
    NODE_KINDS,
    PORT_DEFINITIONS,
)


# ---------------------------------------------------------------------------
# Helper: fake provider that returns controlled JSON
# ---------------------------------------------------------------------------

class FakeProvider:
    """A fake text provider for testing."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str | None = None

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        self.last_prompt = prompt
        return self._response


class FailingProvider:
    """A provider that always raises."""

    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        raise RuntimeError("Provider unavailable")


# ---------------------------------------------------------------------------
# Tests: Scene count extraction
# ---------------------------------------------------------------------------

class TestExtractSceneCount:
    def test_extract_from_ge_shu_chang_jing(self):
        assert _extract_scene_count("生成两个场景") == 2

    def test_extract_from_san_ge_jing_tou(self):
        assert _extract_scene_count("请生成三个镜头") == 3

    def test_extract_from_five_scenes(self):
        assert _extract_scene_count("generate 5 scenes") == 5

    def test_extract_from_shi_ge_pian_duan(self):
        assert _extract_scene_count("用十个片段展示") == 10

    def test_returns_none_when_no_match(self):
        assert _extract_scene_count("生成一个好看的故事") is None

    def test_extracts_first_match(self):
        assert _extract_scene_count("两个场景，五个镜头") == 2


# ---------------------------------------------------------------------------
# Tests: Variant count extraction
# ---------------------------------------------------------------------------

class TestExtractVariantCount:
    def test_extract_mei_zhang_tu_liang_zhang(self):
        assert _extract_variant_count("每个场景两张图") == 2

    def test_extract_mei_zhang_liang_zhang(self):
        assert _extract_variant_count("每张图两张") == 2

    def test_extract_bian_ti(self):
        assert _extract_variant_count("每个场景3个变体") == 3

    def test_returns_none_when_no_match(self):
        assert _extract_variant_count("生成一个故事") is None


# ---------------------------------------------------------------------------
# Tests: No-video detection
# ---------------------------------------------------------------------------

class TestWantsNoVideo:
    def test_no_video_explicit(self):
        assert _wants_no_video("不要视频，只生成图片") is True

    def test_no_he_cheng(self):
        assert _wants_no_video("不要合成") is True

    def test_zhi_sheng_cheng_tu_pian(self):
        assert _wants_no_video("只生成一张图片") is True

    def test_no_video_in_english(self):
        assert _wants_no_video("generate image, no video") is True

    def test_wants_video_by_default(self):
        assert _wants_no_video("生成两个场景，每个场景两张图") is False


# ---------------------------------------------------------------------------
# Tests: JSON parsing
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_parse_plain_json(self):
        data = {"name": "test", "nodes": []}
        result = _parse_json_response(json.dumps(data))
        assert result == data

    def test_parse_markdown_code_block(self):
        data = {"name": "test"}
        text = f"```json\n{json.dumps(data)}\n```"
        result = _parse_json_response(text)
        assert result == data

    def test_parse_generic_code_block(self):
        data = {"name": "test"}
        text = f"```\n{json.dumps(data)}\n```"
        result = _parse_json_response(text)
        assert result == data

    def test_parse_embedded_json(self):
        data = {"name": "test"}
        text = f"Here is the result:\n{json.dumps(data)}\nDone."
        result = _parse_json_response(text)
        assert result == data

    def test_returns_none_for_invalid(self):
        result = _parse_json_response("not json at all")
        assert result is None

    def test_returns_none_for_empty(self):
        result = _parse_json_response("")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: _dict_to_intent validation
# ---------------------------------------------------------------------------

class TestDictToIntent:
    def test_valid_simple_intent(self):
        data = {
            "name": "Test",
            "nodes": [{"alias": "input", "kind": "textInput", "config": {}}],
            "connections": [],
        }
        intent = _dict_to_intent(data, "test prompt")
        assert intent is not None
        assert intent.name == "Test"
        assert len(intent.nodes) == 1
        assert intent.nodes[0].alias == "input"

    def test_returns_none_for_empty_nodes(self):
        data = {"name": "Test", "nodes": []}
        assert _dict_to_intent(data, "test") is None

    def test_returns_none_for_unknown_kind(self):
        data = {
            "name": "Test",
            "nodes": [{"alias": "a", "kind": "nonexistent"}],
        }
        assert _dict_to_intent(data, "test") is None

    def test_returns_none_for_missing_alias(self):
        data = {
            "name": "Test",
            "nodes": [{"kind": "textInput"}],
        }
        assert _dict_to_intent(data, "test") is None

    def test_returns_none_for_invalid_connection_ref(self):
        data = {
            "name": "Test",
            "nodes": [{"alias": "a", "kind": "textInput"}],
            "connections": [
                {
                    "source": {"node": "a", "port": "text"},
                    "target": {"node": "nonexistent", "port": "prompt"},
                }
            ],
        }
        assert _dict_to_intent(data, "test") is None

    def test_preserves_scene_and_variant_count(self):
        data = {
            "name": "Test",
            "nodes": [{"alias": "input", "kind": "textInput", "config": {}}],
            "scene_count": 3,
            "variant_count": 2,
        }
        intent = _dict_to_intent(data, "test")
        assert intent is not None
        assert intent.scene_count == 3
        assert intent.variant_count == 2


# ---------------------------------------------------------------------------
# Tests: Template fallback
# ---------------------------------------------------------------------------

class TestTemplateFallback:
    def test_default_has_six_nodes(self):
        intent = _template_fallback("生成一个视频")
        assert len(intent.nodes) == 6
        kinds = [n.kind for n in intent.nodes]
        assert "textInput" in kinds
        assert "storyboard" in kinds
        assert "textToImage" in kinds
        assert "imageToVideo" in kinds
        assert "videoConcat" in kinds
        assert "output" in kinds

    def test_no_video_has_four_nodes(self):
        intent = _template_fallback("只生成一张图片，不要视频")
        assert len(intent.nodes) == 4
        kinds = [n.kind for n in intent.nodes]
        assert "imageToVideo" not in kinds
        assert "videoConcat" not in kinds

    def test_scene_count_from_prompt(self):
        intent = _template_fallback("生成三个场景")
        assert intent.scene_count == 3
        storyboard = [n for n in intent.nodes if n.kind == "storyboard"][0]
        assert storyboard.config["scenes"] == 3

    def test_variant_count_from_prompt(self):
        intent = _template_fallback("每个场景两张图")
        assert intent.variant_count == 2

    def test_default_scene_count_is_five(self):
        intent = _template_fallback("随便生成")
        assert intent.scene_count == 5

    def test_connections_are_valid(self):
        intent = _template_fallback("生成视频")
        node_aliases = {n.alias for n in intent.nodes}
        for conn in intent.connections:
            assert conn.source.node in node_aliases
            assert conn.target.node in node_aliases


# ---------------------------------------------------------------------------
# Tests: parse_workflow_intent (integration)
# ---------------------------------------------------------------------------

class TestParseWorkflowIntent:
    @pytest.mark.asyncio
    async def test_simple_prompt_with_provider(self):
        mimo_response = {
            "name": "简单图片",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {"prompt": "画一只猫"}},
                {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 1}},
                {"alias": "textToImage", "kind": "textToImage", "config": {}},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
                {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
            ],
            "scene_count": 1,
            "variant_count": None,
            "reasoning": "用户只想画一张图",
        }
        provider = FakeProvider(json.dumps(mimo_response, ensure_ascii=False))
        intent = await parse_workflow_intent("画一只猫", provider=provider)
        assert isinstance(intent, WorkflowIntent)
        assert intent.name == "简单图片"
        assert len(intent.nodes) == 3
        assert intent.scene_count == 1

    @pytest.mark.asyncio
    async def test_fallback_when_no_provider(self):
        intent = await parse_workflow_intent("生成视频", provider=None)
        assert isinstance(intent, WorkflowIntent)
        assert len(intent.nodes) == 6

    @pytest.mark.asyncio
    async def test_fallback_when_provider_fails(self):
        provider = FailingProvider()
        intent = await parse_workflow_intent("生成视频", provider=provider)
        assert isinstance(intent, WorkflowIntent)
        assert len(intent.nodes) == 6

    @pytest.mark.asyncio
    async def test_fallback_when_invalid_json(self):
        provider = FakeProvider("this is not json at all")
        intent = await parse_workflow_intent("生成视频", provider=provider)
        assert isinstance(intent, WorkflowIntent)
        assert len(intent.nodes) == 6

    @pytest.mark.asyncio
    async def test_fallback_when_empty_nodes(self):
        mimo_response = {"name": "empty", "nodes": []}
        provider = FakeProvider(json.dumps(mimo_response))
        intent = await parse_workflow_intent("生成视频", provider=provider)
        assert isinstance(intent, WorkflowIntent)
        assert len(intent.nodes) == 6  # fallback

    @pytest.mark.asyncio
    async def test_reasoning_added_as_warning(self):
        mimo_response = {
            "name": "Test",
            "nodes": [{"alias": "input", "kind": "textInput", "config": {}}],
            "reasoning": "I think the user wants a simple workflow",
        }
        provider = FakeProvider(json.dumps(mimo_response, ensure_ascii=False))
        intent = await parse_workflow_intent("简单工作流", provider=provider)
        assert any("reasoning" in w.lower() for w in intent.warnings)

    @pytest.mark.asyncio
    async def test_prompt_sent_to_provider_contains_system_prompt(self):
        mimo_response = {
            "name": "Test",
            "nodes": [{"alias": "input", "kind": "textInput", "config": {}}],
        }
        provider = FakeProvider(json.dumps(mimo_response))
        await parse_workflow_intent("测试提示", provider=provider)
        assert provider.last_prompt is not None
        assert "textInput" in provider.last_prompt
        assert "测试提示" in provider.last_prompt

    @pytest.mark.asyncio
    async def test_mixed_chinese_english_prompt(self):
        mimo_response = {
            "name": "Mixed workflow",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {}},
                {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 2}},
                {"alias": "textToImage", "kind": "textToImage", "config": {}},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
                {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
            ],
            "scene_count": 2,
        }
        provider = FakeProvider(json.dumps(mimo_response, ensure_ascii=False))
        intent = await parse_workflow_intent("生成2个场景 generate 2 scenes", provider=provider)
        assert isinstance(intent, WorkflowIntent)
        assert intent.scene_count == 2

    @pytest.mark.asyncio
    async def test_no_video_prompt_with_provider(self):
        mimo_response = {
            "name": "Image only",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {}},
                {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 1}},
                {"alias": "textToImage", "kind": "textToImage", "config": {}},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
                {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
            ],
            "scene_count": 1,
        }
        provider = FakeProvider(json.dumps(mimo_response, ensure_ascii=False))
        intent = await parse_workflow_intent("只生成一张图片，不要视频", provider=provider)
        kinds = [n.kind for n in intent.nodes]
        assert "imageToVideo" not in kinds
        assert "videoConcat" not in kinds

    @pytest.mark.asyncio
    async def test_multiple_requirements_parsed(self):
        mimo_response = {
            "name": "Multi-requirement",
            "nodes": [
                {"alias": "input", "kind": "textInput", "config": {}},
                {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 3}},
                {"alias": "textToImage", "kind": "textToImage", "config": {}},
                {"alias": "imageToVideo", "kind": "imageToVideo", "config": {"duration": 10}},
                {"alias": "videoConcat", "kind": "videoConcat", "config": {}},
                {"alias": "output", "kind": "output", "config": {}},
            ],
            "connections": [
                {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
                {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
                {"source": {"node": "textToImage", "port": "image"}, "target": {"node": "imageToVideo", "port": "image"}, "mode": "map"},
                {"source": {"node": "imageToVideo", "port": "video"}, "target": {"node": "videoConcat", "port": "video"}, "mode": "aggregate"},
                {"source": {"node": "videoConcat", "port": "video"}, "target": {"node": "output", "port": "video"}, "mode": "direct"},
            ],
            "scene_count": 3,
            "variant_count": 2,
            "reasoning": "三场景，每场景两变体，10秒视频",
        }
        provider = FakeProvider(json.dumps(mimo_response, ensure_ascii=False))
        intent = await parse_workflow_intent(
            "三个场景，每个场景两张图，每张图10秒视频", provider=provider
        )
        assert intent.scene_count == 3
        assert intent.variant_count == 2
        assert len(intent.nodes) == 6
        # Check imageToVideo has duration config
        i2v = [n for n in intent.nodes if n.kind == "imageToVideo"][0]
        assert i2v.config["duration"] == 10


# ---------------------------------------------------------------------------
# Tests: System prompt completeness
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_includes_all_node_kinds(self):
        prompt = get_system_prompt()
        for kind in NODE_KINDS:
            assert kind in prompt

    def test_includes_port_definitions(self):
        prompt = get_system_prompt()
        for kind, ports in PORT_DEFINITIONS.items():
            assert kind in prompt
            for port in ports.get("input", []):
                assert port in prompt
            for port in ports.get("output", []):
                assert port in prompt

    def test_includes_connection_rules(self):
        prompt = get_system_prompt()
        assert "textInput" in prompt
        assert "storyboard" in prompt
        assert "textToImage" in prompt
        assert "imageToVideo" in prompt
        assert "videoConcat" in prompt
        assert "output" in prompt

    def test_includes_examples(self):
        prompt = get_system_prompt()
        assert "示例" in prompt
        assert "只生成一张图片" in prompt
        assert "每个场景两张图" in prompt
