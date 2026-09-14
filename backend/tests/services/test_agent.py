"""Tests for Agent service."""

import pytest
from backend.app.services.agent import AgentService
from backend.app.models import WorkflowSpec, GraphPatch
from backend.app.providers import init_providers, clear_providers


class TestAgentService:
    """Tests for AgentService."""

    def setup_method(self):
        clear_providers()
        init_providers(mock=True)
        self.service = AgentService()

    def teardown_method(self):
        clear_providers()

    @pytest.mark.asyncio
    async def test_generate_from_prompt(self):
        """Test generating workflow from prompt."""
        spec = await self.service.generate_from_prompt("生成一个关于自然风光的视频")
        assert isinstance(spec, WorkflowSpec)
        assert len(spec.nodes) > 0
        assert spec.name != ""

    @pytest.mark.asyncio
    async def test_generate_with_config(self):
        """Test generating with custom config."""
        spec = await self.service.generate_from_prompt(
            "城市宣传片",
            config={"scenes": 3, "style": "modern"},
        )
        assert isinstance(spec, WorkflowSpec)

    @pytest.mark.asyncio
    async def test_modify_workflow(self):
        """Test modifying workflow returns GraphPatch."""
        spec = await self.service.generate_from_prompt("测试视频")
        patch = await self.service.modify_workflow(spec, "添加一个新场景")
        assert isinstance(patch, GraphPatch)
        # Mock provider may return empty patch, that's OK
        assert patch is not None

    @pytest.mark.asyncio
    async def test_explain_workflow(self):
        """Test explaining workflow."""
        spec = await self.service.generate_from_prompt("测试")
        explanation = await self.service.explain_workflow(spec)
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    @pytest.mark.asyncio
    async def test_template_fallback(self):
        """Test fallback when no provider available."""
        clear_providers()
        service = AgentService()
        spec = await service.generate_from_prompt("fallback test")
        assert isinstance(spec, WorkflowSpec)

    def test_serialize_workflow_for_llm(self):
        """Test workflow serialization."""
        spec = WorkflowSpec(
            id="test", name="Test",
            nodes=[], edges=[],
        )
        text = self.service._serialize_workflow_for_llm(spec)
        assert "Test" in text
        assert "节点数: 0" in text
