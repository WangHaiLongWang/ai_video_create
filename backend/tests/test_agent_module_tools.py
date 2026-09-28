"""Tests for agent module tools — list_modules, get_module, format_for_system_prompt."""

import pytest

from backend.app.services.agent_module_tools import (
    format_modules_for_system_prompt,
    get_module_for_agent,
    list_modules_for_agent,
)
from backend.app.services.module_registry import get_module_registry


class TestListModulesForAgent:
    """Tests for list_modules_for_agent()."""

    def test_list_modules_returns_builtin_modules(self):
        """list_modules should return the builtin seedream module."""
        modules = list_modules_for_agent()
        assert len(modules) >= 1
        ids = [m["id"] for m in modules]
        assert "builtin.seedream.text-to-image" in ids

    def test_list_modules_filters_by_capability(self):
        """Filtering by capability should narrow results."""
        all_modules = list_modules_for_agent()
        image_modules = list_modules_for_agent(capability="image")
        assert len(image_modules) <= len(all_modules)
        for m in image_modules:
            assert m["capability"] == "image"

    def test_list_modules_filters_by_category(self):
        """Filtering by category should narrow results."""
        image_modules = list_modules_for_agent(category="image")
        for m in image_modules:
            assert m["category"] == "image"

    def test_list_modules_returns_expected_fields(self):
        """Each module dict should have the expected fields."""
        modules = list_modules_for_agent()
        for m in modules:
            assert "id" in m
            assert "version" in m
            assert "label" in m
            assert "description" in m
            assert "baseKind" in m
            assert "category" in m
            assert "capability" in m
            assert "inputPorts" in m
            assert "outputPorts" in m

    def test_list_modules_port_summary(self):
        """Port summary should list port IDs."""
        modules = list_modules_for_agent()
        seedream = next(m for m in modules if m["id"] == "builtin.seedream.text-to-image")
        assert "scene" in seedream["inputPorts"]
        assert "image" in seedream["outputPorts"]


class TestGetModuleForAgent:
    """Tests for get_module_for_agent()."""

    def test_get_module_returns_full_info(self):
        """get_module should return detailed module info."""
        info = get_module_for_agent("builtin.seedream.text-to-image")
        assert info is not None
        assert info["id"] == "builtin.seedream.text-to-image"
        assert info["version"] == "1.0.0"
        assert info["label"] == "Seedream 文生图"
        assert info["baseKind"] == "textToImage"
        assert info["category"] == "image"

    def test_get_module_returns_config_schema(self):
        """Module info should include configSchema."""
        info = get_module_for_agent("builtin.seedream.text-to-image")
        assert info is not None
        assert "configSchema" in info
        assert "properties" in info["configSchema"]

    def test_get_module_returns_provider_policy(self):
        """Module info should include providerPolicy."""
        info = get_module_for_agent("builtin.seedream.text-to-image")
        assert info is not None
        pp = info["providerPolicy"]
        assert pp["capability"] == "image"
        assert "doubao" in pp["allowed"]
        assert pp["default"] == "doubao"
        assert pp["locked"] is True

    def test_get_module_returns_default_config(self):
        """Module info should include defaultConfig."""
        info = get_module_for_agent("builtin.seedream.text-to-image")
        assert info is not None
        assert "defaultConfig" in info
        assert "provider" in info["defaultConfig"]

    def test_get_module_returns_ports(self):
        """Module info should include full ports definition."""
        info = get_module_for_agent("builtin.seedream.text-to-image")
        assert info is not None
        assert "ports" in info
        assert "inputs" in info["ports"]
        assert "outputs" in info["ports"]

    def test_get_module_with_specific_version(self):
        """Requesting a specific version should return that version."""
        info = get_module_for_agent("builtin.seedream.text-to-image", version="1.0.0")
        assert info is not None
        assert info["version"] == "1.0.0"

    def test_get_module_nonexistent_returns_none(self):
        """Requesting a nonexistent module should return None."""
        info = get_module_for_agent("nonexistent.module.id")
        assert info is None

    def test_get_module_nonexistent_version_returns_none(self):
        """Requesting a nonexistent version should return None."""
        info = get_module_for_agent("builtin.seedream.text-to-image", version="99.99.99")
        assert info is None


class TestFormatModulesForSystemPrompt:
    """Tests for format_modules_for_system_prompt()."""

    def test_format_groups_by_category(self):
        """Formatted output should group modules by category."""
        modules = list_modules_for_agent()
        text = format_modules_for_system_prompt(modules)
        assert "image" in text.lower() or "可用模块" in text

    def test_format_includes_port_summary(self):
        """Formatted output should include port information."""
        modules = list_modules_for_agent()
        text = format_modules_for_system_prompt(modules)
        assert "scene" in text  # Seedream input port
        assert "image" in text  # Seedream output port

    def test_format_includes_module_id(self):
        """Formatted output should include module IDs."""
        modules = list_modules_for_agent()
        text = format_modules_for_system_prompt(modules)
        assert "builtin.seedream.text-to-image" in text

    def test_format_empty_modules_returns_empty(self):
        """Empty module list should return empty string."""
        text = format_modules_for_system_prompt([])
        assert text == ""

    def test_format_includes_usage_instruction(self):
        """Formatted output should include usage instructions."""
        modules = list_modules_for_agent()
        text = format_modules_for_system_prompt(modules)
        assert "moduleId" in text


class TestSystemPromptIntegration:
    """Tests for integration with the workflow intent parser."""

    def test_system_prompt_includes_module_section(self):
        """The system prompt should include the modules section."""
        from backend.app.services.workflow_intent_parser import get_system_prompt
        prompt = get_system_prompt()
        assert "可用模块" in prompt
        assert "builtin.seedream.text-to-image" in prompt

    def test_node_intent_accepts_module_id(self):
        """NodeIntent should accept moduleId field."""
        from backend.app.schemas.workflow_intent import NodeIntent
        node = NodeIntent(
            alias="img",
            kind="textToImage",
            moduleId="builtin.seedream.text-to-image",
        )
        assert node.module_id == "builtin.seedream.text-to-image"

    def test_node_intent_module_id_optional(self):
        """NodeIntent moduleId should default to None."""
        from backend.app.schemas.workflow_intent import NodeIntent
        node = NodeIntent(alias="img", kind="textToImage")
        assert node.module_id is None

    def test_workflow_intent_json_roundtrip_with_module_id(self):
        """WorkflowIntent with moduleId should serialize/deserialize correctly."""
        from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
        intent = WorkflowIntent(
            name="test",
            nodes=[
                NodeIntent(
                    alias="img",
                    kind="textToImage",
                    moduleId="builtin.seedream.text-to-image",
                ),
            ],
        )
        # by_alias=True produces "moduleId" key; default produces "module_id"
        dumped = intent.model_dump(by_alias=True)
        assert dumped["nodes"][0]["moduleId"] == "builtin.seedream.text-to-image"

        dumped_field = intent.model_dump()
        assert dumped_field["nodes"][0]["module_id"] == "builtin.seedream.text-to-image"

        restored = WorkflowIntent(**dumped)
        assert restored.nodes[0].module_id == "builtin.seedream.text-to-image"

    def test_workflow_intent_roundtrip_preserves_module_instance(self):
        from backend.app.schemas.workflow_intent import NodeIntent, WorkflowIntent
        intent = WorkflowIntent(name="test", nodes=[NodeIntent(
            alias="img",
            kind="textToImage",
            moduleId="builtin.seedream.text-to-image",
            moduleVersion="1.0.0",
            configOverrides={"size": "1920x1080"},
        )])
        restored = WorkflowIntent.model_validate(intent.model_dump(by_alias=True))
        node = restored.nodes[0]
        assert node.module_version == "1.0.0"
        assert node.config_overrides == {"size": "1920x1080"}
