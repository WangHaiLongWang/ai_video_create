"""Tests for WorkflowIntent schema."""

import pytest

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)


class TestMinimalIntent:
    def test_minimal_intent(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        assert len(intent.nodes) == 1
        assert intent.connections == []
        assert intent.tags == []
        assert intent.warnings == []

    def test_minimal_intent_no_optional_fields(self):
        intent = WorkflowIntent(
            name="Minimal",
            nodes=[NodeIntent(alias="a", kind="output")],
        )
        assert intent.name == "Minimal"
        assert intent.description is None
        assert intent.template_id is None
        assert intent.scene_count is None
        assert intent.variant_count is None
        assert intent.duration is None
        assert intent.resolution is None


class TestFullIntent:
    def test_full_intent(self):
        intent = WorkflowIntent(
            name="滑雪教学",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3}),
                NodeIntent(alias="img", kind="textToImage"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="story", port="scenes"),
                    target=PortRef(node="img", port="scene"),
                    mode="map",
                )
            ],
            scene_count=3,
            variant_count=1,
            warnings=["不确定是否需要音频"],
        )
        assert intent.scene_count == 3
        assert len(intent.connections) == 1
        assert intent.connections[0].mode == "map"
        assert intent.connections[0].source.node == "story"
        assert intent.connections[0].target.port == "scene"
        assert len(intent.warnings) == 1

    def test_intent_with_multiple_connections(self):
        intent = WorkflowIntent(
            name="Multi-conn",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
                NodeIntent(alias="c", kind="textToImage"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                    mode="direct",
                ),
                ConnectionIntent(
                    source=PortRef(node="b", port="scenes"),
                    target=PortRef(node="c", port="scene"),
                    mode="map",
                ),
            ],
        )
        assert len(intent.connections) == 2

    def test_intent_with_tags(self):
        intent = WorkflowIntent(
            name="Tagged",
            nodes=[NodeIntent(alias="in", kind="textInput")],
            tags=["ski", "lesson"],
        )
        assert intent.tags == ["ski", "lesson"]

    def test_node_with_label_and_description(self):
        intent = WorkflowIntent(
            name="Labeled",
            nodes=[
                NodeIntent(
                    alias="story",
                    kind="storyboard",
                    label="分镜生成",
                    description="将文本拆分为多个场景",
                    config={"scenes": 5, "style": "cinematic"},
                ),
            ],
        )
        assert intent.nodes[0].label == "分镜生成"
        assert intent.nodes[0].description == "将文本拆分为多个场景"
        assert intent.nodes[0].config["scenes"] == 5


class TestJSONRoundtrip:
    def test_intent_json_roundtrip(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="a", kind="textInput")],
        )
        json_str = intent.model_dump_json()
        restored = WorkflowIntent.model_validate_json(json_str)
        assert restored.name == "Test"
        assert len(restored.nodes) == 1
        assert restored.nodes[0].alias == "a"

    def test_full_intent_json_roundtrip(self):
        intent = WorkflowIntent(
            name="滑雪教学",
            nodes=[
                NodeIntent(alias="story", kind="storyboard", config={"scenes": 3}),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
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
                    mode="direct",
                ),
            ],
            scene_count=3,
            variant_count=1,
            duration=12,
            resolution="1080P",
            tags=["ski", "教学"],
            warnings=["test warning"],
        )
        json_str = intent.model_dump_json()
        restored = WorkflowIntent.model_validate_json(json_str)
        assert restored.name == "滑雪教学"
        assert len(restored.nodes) == 5
        assert len(restored.connections) == 4
        assert restored.scene_count == 3
        assert restored.resolution == "1080P"
        assert restored.tags == ["ski", "教学"]

    def test_model_dump_dict(self):
        intent = WorkflowIntent(
            name="Dict Test",
            nodes=[NodeIntent(alias="x", kind="output")],
        )
        d = intent.model_dump()
        assert d["name"] == "Dict Test"
        assert d["nodes"][0]["alias"] == "x"


class TestValidation:
    def test_empty_nodes_rejected(self):
        with pytest.raises(Exception):
            WorkflowIntent(
                name="Empty",
                nodes=[],
            )

    def test_connection_mode_default(self):
        conn = ConnectionIntent(
            source=PortRef(node="a", port="out"),
            target=PortRef(node="b", port="in"),
        )
        assert conn.mode == "direct"

    def test_port_ref_fields(self):
        ref = PortRef(node="story", port="scenes")
        assert ref.node == "story"
        assert ref.port == "scenes"
