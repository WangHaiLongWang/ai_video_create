"""Tests for the Intent Compiler."""

import pytest

from backend.app.services.agent_compiler import compile_intent
from backend.app.schemas.workflow_intent import (
    WorkflowIntent,
    NodeIntent,
    ConnectionIntent,
    PortRef,
)


class TestCompileMinimal:
    def test_compile_minimal(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = compile_intent(intent)
        assert result["schemaVersion"] == "2.0"
        assert result["manifestVersion"] == "1.0"
        assert "id" in result
        assert result["name"] == "Test"
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["data"]["kind"] == "textInput"
        assert result["nodes"][0]["type"] == "studio"
        assert "position" in result["nodes"][0]

    def test_compile_minimal_has_metadata(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = compile_intent(intent)
        assert "viewport" in result
        assert result["viewport"] == {"x": 0, "y": 0, "zoom": 1}
        assert "metadata" in result
        assert "createdAt" in result["metadata"]

    def test_compile_minimal_has_edges_array(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = compile_intent(intent)
        assert isinstance(result["edges"], list)
        assert len(result["edges"]) == 0


class TestCompileLinearChain:
    def test_compile_linear_chain(self):
        intent = WorkflowIntent(
            name="Pipeline",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="story", kind="storyboard"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="story", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="story", port="scenes"),
                    target=PortRef(node="out", port="video"),
                ),
            ],
        )
        result = compile_intent(intent)
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2
        # Check edge handles
        edge1 = result["edges"][0]
        assert edge1["sourceHandle"] == "text"
        assert edge1["targetHandle"] == "prompt"
        edge2 = result["edges"][1]
        assert edge2["sourceHandle"] == "scenes"
        assert edge2["targetHandle"] == "video"

    def test_compile_edges_reference_node_ids(self):
        intent = WorkflowIntent(
            name="Ref Test",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="video"),
                ),
            ],
        )
        result = compile_intent(intent)
        node_ids = {n["id"] for n in result["nodes"]}
        edge = result["edges"][0]
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

    def test_compile_edge_has_mode(self):
        intent = WorkflowIntent(
            name="Mode Test",
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
        result = compile_intent(intent)
        assert result["edges"][0]["data"]["mode"] == "map"


class TestCompilePositionsAreSpaced:
    def test_compile_positions_are_spaced(self):
        intent = WorkflowIntent(
            name="Spaced",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
                NodeIntent(alias="c", kind="output"),
            ],
        )
        result = compile_intent(intent)
        positions = [n["position"]["x"] for n in result["nodes"]]
        assert positions[1] > positions[0]
        assert positions[2] > positions[1]

    def test_compile_spacing_is_288px(self):
        intent = WorkflowIntent(
            name="Spacing",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
            ],
        )
        result = compile_intent(intent)
        x0 = result["nodes"][0]["position"]["x"]
        x1 = result["nodes"][1]["position"]["x"]
        assert x1 - x0 == 288

    def test_compile_y_alternates(self):
        intent = WorkflowIntent(
            name="Alternating",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
                NodeIntent(alias="c", kind="output"),
            ],
        )
        result = compile_intent(intent)
        y0 = result["nodes"][0]["position"]["y"]
        y1 = result["nodes"][1]["position"]["y"]
        y2 = result["nodes"][2]["position"]["y"]
        assert y0 == 150.0  # even index
        assert y1 == 220.0  # odd index
        assert y2 == 150.0  # even index


class TestCompilePreservesConfig:
    def test_compile_preserves_config(self):
        intent = WorkflowIntent(
            name="Config",
            nodes=[
                NodeIntent(
                    alias="story",
                    kind="storyboard",
                    config={"scenes": 5, "style": "cinematic"},
                ),
            ],
        )
        result = compile_intent(intent)
        node = result["nodes"][0]
        assert node["data"]["config"]["scenes"] == 5
        assert node["data"]["config"]["style"] == "cinematic"

    def test_compile_merges_default_config(self):
        intent = WorkflowIntent(
            name="Defaults",
            nodes=[
                NodeIntent(
                    alias="story",
                    kind="storyboard",
                    config={"scenes": 3},  # override default
                ),
            ],
        )
        result = compile_intent(intent)
        config = result["nodes"][0]["data"]["config"]
        assert config["scenes"] == 3
        assert config["style"] == "cinematic"  # from default

    def test_compile_empty_config_gets_defaults(self):
        intent = WorkflowIntent(
            name="No Config",
            nodes=[
                NodeIntent(alias="story", kind="storyboard"),
            ],
        )
        result = compile_intent(intent)
        config = result["nodes"][0]["data"]["config"]
        assert "scenes" in config  # default from manifest
        assert "style" in config


class TestCompilePorts:
    def test_compile_ports_from_manifest(self):
        intent = WorkflowIntent(
            name="Ports",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
            ],
        )
        result = compile_intent(intent)
        node = result["nodes"][0]
        assert node["data"]["ports"] is not None
        assert len(node["data"]["ports"]["inputs"]) == 0
        assert len(node["data"]["ports"]["outputs"]) == 1
        assert node["data"]["ports"]["outputs"][0]["id"] == "text"
        assert node["data"]["ports"]["outputs"][0]["type"] == "text"

    def test_compile_backward_compat_types(self):
        intent = WorkflowIntent(
            name="Compat",
            nodes=[
                NodeIntent(alias="sb", kind="storyboard"),
            ],
        )
        result = compile_intent(intent)
        node = result["nodes"][0]
        assert node["data"]["inputType"] == "text"
        assert node["data"]["outputType"] == "scene"

    def test_compile_node_status_is_idle(self):
        intent = WorkflowIntent(
            name="Status",
            nodes=[NodeIntent(alias="a", kind="textInput")],
        )
        result = compile_intent(intent)
        assert result["nodes"][0]["data"]["status"] == "idle"


class TestCompileDeterministicId:
    def test_compile_node_ids_are_deterministic(self):
        """Same alias always produces the same ID."""
        intent = WorkflowIntent(
            name="Deterministic",
            nodes=[NodeIntent(alias="story", kind="storyboard")],
        )
        r1 = compile_intent(intent)
        r2 = compile_intent(intent)
        assert r1["nodes"][0]["id"] == r2["nodes"][0]["id"]

    def test_compile_different_aliases_different_ids(self):
        intent = WorkflowIntent(
            name="Different",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="textInput"),
            ],
        )
        result = compile_intent(intent)
        assert result["nodes"][0]["id"] != result["nodes"][1]["id"]

    def test_compile_node_id_format(self):
        intent = WorkflowIntent(
            name="Format",
            nodes=[NodeIntent(alias="test", kind="textInput")],
        )
        result = compile_intent(intent)
        node_id = result["nodes"][0]["id"]
        assert node_id.startswith("test-")
        assert len(node_id) == len("test-") + 8  # alias + "-" + 8 hex chars


class TestCompileFullPipeline:
    def test_compile_full_pipeline(self):
        """Test a full ski-lesson style pipeline."""
        intent = WorkflowIntent(
            name="Ski Lesson",
            description="Generate a ski lesson video",
            nodes=[
                NodeIntent(alias="in", kind="textInput", config={"prompt": "Learn to ski"}),
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3, "style": "cinematic"}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="story", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="story", port="scenes"),
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
        result = compile_intent(intent)
        assert result["schemaVersion"] == "2.0"
        assert result["name"] == "Ski Lesson"
        assert result["description"] == "Generate a ski lesson video"
        assert len(result["nodes"]) == 6
        assert len(result["edges"]) == 5

        # Verify first node has prompt
        assert result["nodes"][0]["data"]["config"]["prompt"] == "Learn to ski"

        # Verify storyboard config
        assert result["nodes"][1]["data"]["config"]["scenes"] == 3

    def test_compile_with_tags(self):
        intent = WorkflowIntent(
            name="Tagged",
            nodes=[NodeIntent(alias="in", kind="textInput")],
            tags=["ski", "lesson"],
        )
        result = compile_intent(intent)
        assert result["metadata"]["tags"] == ["ski", "lesson"]


class TestCompileEdgeData:
    def test_compile_edge_data_has_label(self):
        intent = WorkflowIntent(
            name="Label Test",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="video"),
                ),
            ],
        )
        result = compile_intent(intent)
        assert result["edges"][0]["data"]["label"] == ""

    def test_compile_edge_has_uuid(self):
        intent = WorkflowIntent(
            name="UUID Test",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="video"),
                ),
            ],
        )
        result = compile_intent(intent)
        edge_id = result["edges"][0]["id"]
        # UUID4 format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        parts = edge_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[4]) == 12
