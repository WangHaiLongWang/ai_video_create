"""Tests for agent tool functions."""

import pytest

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)
from backend.app.services.agent_tools import (
    AgentToolResult,
    estimate_calls,
    get_node_manifest,
    intent_to_compact_prompt,
    list_node_manifests,
    list_templates,
    validate_intent,
)


class TestListNodeManifests:
    def test_list_node_manifests(self):
        result = list_node_manifests()
        assert result.success
        assert "textInput" in result.data
        assert "storyboard" in result.data
        assert "textToImage" in result.data
        assert "imageToVideo" in result.data
        assert "videoConcat" in result.data
        assert "output" in result.data

    def test_manifest_structure(self):
        result = list_node_manifests()
        assert result.success
        text_input = result.data["textInput"]
        assert text_input["kind"] == "textInput"
        assert text_input["label"] == "TextInput"
        assert len(text_input["outputs"]) == 1
        assert text_input["outputs"][0]["id"] == "text"
        assert text_input["outputs"][0]["type"] == "text"
        assert len(text_input["inputs"]) == 0

    def test_storyboard_ports(self):
        result = list_node_manifests()
        assert result.success
        sb = result.data["storyboard"]
        assert len(sb["inputs"]) == 1
        assert sb["inputs"][0]["id"] == "prompt"
        assert len(sb["outputs"]) == 1
        assert sb["outputs"][0]["id"] == "scenes"
        assert sb["outputs"][0]["cardinality"] == "many"

    def test_text_to_image_execution_hints(self):
        result = list_node_manifests()
        assert result.success
        tti = result.data["textToImage"]
        assert "configSchema" in tti


class TestGetNodeManifest:
    def test_get_valid_manifest(self):
        result = get_node_manifest("textInput")
        assert result.success
        assert result.data["kind"] == "textInput"
        assert result.data["category"] == "input"

    def test_get_invalid_manifest(self):
        result = get_node_manifest("nonexistent")
        assert not result.success
        assert "nonexistent" in result.error
        assert "textInput" in result.error  # available kinds listed

    def test_get_all_manifests(self):
        for kind in ["textInput", "storyboard", "textToImage", "imageToVideo", "videoConcat", "output"]:
            result = get_node_manifest(kind)
            assert result.success, f"Failed for kind: {kind}"
            assert result.data["kind"] == kind

    def test_manifest_execution_hints(self):
        result = get_node_manifest("textToImage")
        assert result.success
        assert result.data["execution"] is not None
        assert result.data["execution"]["mapOver"] == "scene"


class TestListTemplates:
    def test_list_templates(self):
        result = list_templates()
        assert result.success
        assert "templates" in result.data
        assert len(result.data["templates"]) > 0

    def test_template_structure(self):
        result = list_templates()
        assert result.success
        first = result.data["templates"][0]
        assert "id" in first
        assert "name" in first
        assert "description" in first
        assert "tags" in first


class TestValidateIntent:
    def test_validate_valid_intent(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="sb", kind="storyboard"),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="sb", port="scenes"),
                    target=PortRef(node="img", port="scene"),
                    mode="map",
                ),
                ConnectionIntent(
                    source=PortRef(node="img", port="images"),
                    target=PortRef(node="vid", port="image"),
                    mode="map",
                ),
                ConnectionIntent(
                    source=PortRef(node="vid", port="videos"),
                    target=PortRef(node="concat", port="videos"),
                    mode="aggregate",
                ),
                ConnectionIntent(
                    source=PortRef(node="concat", port="video"),
                    target=PortRef(node="out", port="video"),
                ),
            ],
        )
        result = validate_intent(intent)
        assert result.success
        assert result.data["errors"] == []

    def test_validate_unknown_kind(self):
        intent = WorkflowIntent(
            name="Bad Kind",
            nodes=[NodeIntent(alias="x", kind="nonexistent")],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "UNKNOWN_KIND" in codes

    def test_validate_type_mismatch(self):
        intent = WorkflowIntent(
            name="Type Mismatch",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="out", port="video"),
                )
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "TYPE_MISMATCH" in codes

    def test_validate_self_loop(self):
        intent = WorkflowIntent(
            name="Self Loop",
            nodes=[NodeIntent(alias="sb", kind="storyboard")],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="sb", port="scenes"),
                    target=PortRef(node="sb", port="prompt"),
                )
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "SELF_LOOP" in codes

    def test_validate_duplicate_alias(self):
        intent = WorkflowIntent(
            name="Dup Alias",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="a", kind="output"),
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "DUPLICATE_ALIAS" in codes

    def test_validate_unknown_port(self):
        intent = WorkflowIntent(
            name="Bad Port",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="nonexistent"),
                    target=PortRef(node="out", port="video"),
                )
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "UNKNOWN_PORT" in codes

    def test_validate_duplicate_connection(self):
        intent = WorkflowIntent(
            name="Dup Conn",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="sb", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "DUPLICATE_CONNECTION" in codes

    def test_validate_empty_intent(self):
        intent = WorkflowIntent(
            name="No Connections",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = validate_intent(intent)
        assert result.success  # no connections is fine

    def test_validate_unknown_source_node(self):
        intent = WorkflowIntent(
            name="Bad Source",
            nodes=[NodeIntent(alias="a", kind="textInput")],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="ghost", port="text"),
                    target=PortRef(node="a", port="prompt"),
                )
            ],
        )
        result = validate_intent(intent)
        assert not result.success
        codes = [e["code"] for e in result.data["errors"]]
        assert "UNKNOWN_NODE" in codes


class TestEstimateCalls:
    def test_estimate_basic(self):
        intent = WorkflowIntent(
            name="Basic",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=3,
            variant_count=1,
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] == 3
        assert result.data["variant_count"] == 1
        assert result.data["image_calls"] == 3
        assert result.data["video_calls"] == 3
        assert result.data["total_estimated_calls"] >= 6

    def test_estimate_with_variants(self):
        intent = WorkflowIntent(
            name="Variant",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
            ],
            scene_count=5,
            variant_count=3,
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["image_calls"] == 15  # 5 * 3
        assert result.data["video_calls"] == 15  # 5 * 3

    def test_estimate_infers_scene_count(self):
        intent = WorkflowIntent(
            name="Inferred",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 7}),
                NodeIntent(alias="img", kind="textToImage"),
            ],
            # no scene_count provided
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] == 7  # inferred from config

    def test_estimate_default_scene_count(self):
        intent = WorkflowIntent(
            name="Default",
            nodes=[
                NodeIntent(alias="img", kind="textToImage"),
            ],
        )
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] == 1  # default


class TestIntentToCompactPrompt:
    def test_basic_conversion(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="out", kind="output"),
            ],
        )
        text = intent_to_compact_prompt(intent)
        assert "Workflow: Test" in text
        assert "in(textInput)" in text
        assert "out(output)" in text

    def test_with_connections(self):
        intent = WorkflowIntent(
            name="Pipeline",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                ),
            ],
        )
        text = intent_to_compact_prompt(intent)
        assert "a.text -> b.prompt" in text

    def test_with_map_mode(self):
        intent = WorkflowIntent(
            name="Map",
            nodes=[
                NodeIntent(alias="sb", kind="storyboard"),
                NodeIntent(alias="img", kind="textToImage"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="sb", port="scenes"),
                    target=PortRef(node="img", port="scene"),
                    mode="map",
                ),
            ],
        )
        text = intent_to_compact_prompt(intent)
        assert "[map]" in text

    def test_with_constraints(self):
        intent = WorkflowIntent(
            name="Constrained",
            nodes=[NodeIntent(alias="x", kind="textInput")],
            scene_count=5,
            variant_count=2,
            duration=30,
            resolution="4K",
        )
        text = intent_to_compact_prompt(intent)
        assert "scenes=5" in text
        assert "variants=2" in text
        assert "duration=30s" in text
        assert "resolution=4K" in text

    def test_with_warnings(self):
        intent = WorkflowIntent(
            name="Warning",
            nodes=[NodeIntent(alias="x", kind="textInput")],
            warnings=["uncertain about audio"],
        )
        text = intent_to_compact_prompt(intent)
        assert "uncertain about audio" in text

    def test_with_description(self):
        intent = WorkflowIntent(
            name="Desc",
            nodes=[NodeIntent(alias="x", kind="textInput")],
            description="A test workflow",
        )
        text = intent_to_compact_prompt(intent)
        assert "A test workflow" in text


class TestAgentToolResult:
    def test_repr_success(self):
        r = AgentToolResult(success=True, data={"key": "val"})
        assert "OK" in repr(r)

    def test_repr_failure(self):
        r = AgentToolResult(success=False, error="bad")
        assert "FAIL" in repr(r)
        assert "bad" in repr(r)

    def test_default_empty_data(self):
        r = AgentToolResult(success=True)
        assert r.data == {}
        assert r.error is None
