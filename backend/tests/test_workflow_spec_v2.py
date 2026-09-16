"""WorkflowSpec V2 tests — migration, validation, and roundtrip."""

import pytest

from backend.app.models import WorkflowSpec


def _make_v1_spec(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "schemaVersion": "1.0",
        "id": "test-v1",
        "name": "V1 Test",
        "nodes": nodes,
        "edges": edges,
    }


def _make_v2_spec(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "schemaVersion": "2.0",
        "manifestVersion": "1.0",
        "id": "test-v2",
        "name": "V2 Test",
        "nodes": nodes,
        "edges": edges,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "metadata": {"tags": ["test"]},
    }


NODE_A = {
    "id": "a",
    "type": "studio",
    "position": {"x": 0, "y": 0},
    "data": {"label": "A", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {}},
}
NODE_B = {
    "id": "b",
    "type": "studio",
    "position": {"x": 100, "y": 0},
    "data": {"label": "B", "description": "", "kind": "storyboard", "inputType": "text", "outputType": "list<scene>", "status": "idle", "config": {}},
}
NODE_C = {
    "id": "c",
    "type": "studio",
    "position": {"x": 200, "y": 0},
    "data": {"label": "C", "description": "", "kind": "textToImage", "inputType": "list<scene>", "outputType": "list<image>", "status": "idle", "config": {}},
}


class TestV1SpecBackwardCompat:
    """V1 specs without handles should still parse."""

    def test_v1_spec_without_handles(self):
        spec = _make_v1_spec(
            [NODE_A, NODE_B],
            [{"id": "e1", "source": "a", "target": "b", "type": "smoothstep"}],
        )
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "1.0"
        assert len(wf.nodes) == 2
        assert len(wf.edges) == 1

    def test_v1_edge_without_handle_fields(self):
        spec = _make_v1_spec(
            [NODE_A, NODE_B],
            [{"id": "e1", "source": "a", "target": "b", "type": "smoothstep"}],
        )
        wf = WorkflowSpec(**spec)
        assert wf.edges[0].sourceHandle is None
        assert wf.edges[0].targetHandle is None

    def test_v1_full_pipeline_valid(self):
        spec = _make_v1_spec(
            [NODE_A, NODE_B, NODE_C],
            [
                {"id": "e1", "source": "a", "target": "b", "type": "smoothstep"},
                {"id": "e2", "source": "b", "target": "c", "type": "smoothstep"},
            ],
        )
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "1.0"
        assert len(wf.edges) == 2


class TestV2SpecValidation:
    """V2 specs with handles should pass validation."""

    def test_v2_spec_with_handles(self):
        spec = _make_v2_spec(
            [NODE_A, NODE_B],
            [{
                "id": "e1",
                "source": "a",
                "sourceHandle": "text",
                "target": "b",
                "targetHandle": "prompt",
                "type": "smoothstep",
                "data": {"mode": "direct"},
            }],
        )
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "2.0"
        assert wf.edges[0].sourceHandle == "text"
        assert wf.edges[0].targetHandle == "prompt"

    def test_v2_spec_with_viewport_and_metadata(self):
        spec = _make_v2_spec(
            [NODE_A],
            [],
        )
        wf = WorkflowSpec(**spec)
        assert wf.viewport is not None
        assert wf.viewport["zoom"] == 1
        assert wf.metadata is not None
        assert wf.metadata["tags"] == ["test"]

    def test_v2_edge_data_preserved(self):
        spec = _make_v2_spec(
            [NODE_A, NODE_B],
            [{
                "id": "e1",
                "source": "a",
                "sourceHandle": "text",
                "target": "b",
                "targetHandle": "prompt",
                "type": "smoothstep",
                "data": {"mode": "direct", "label": "custom"},
            }],
        )
        wf = WorkflowSpec(**spec)
        assert wf.edges[0].data["mode"] == "direct"
        assert wf.edges[0].data["label"] == "custom"

    def test_v2_spec_with_description(self):
        spec = _make_v2_spec([NODE_A], [])
        spec["description"] = "A test workflow"
        wf = WorkflowSpec(**spec)
        assert wf.description == "A test workflow"

    def test_v2_skips_handle_based_type_validation(self):
        """V2 edges with handles skip outputType/inputType check."""
        # NODE_A has outputType=text, NODE_C has inputType=list<scene>
        # These are incompatible via v1 validation, but v2 skips this check
        spec = _make_v2_spec(
            [NODE_A, NODE_C],
            [{
                "id": "e1",
                "source": "a",
                "sourceHandle": "text",
                "target": "c",
                "targetHandle": "scene",
                "type": "smoothstep",
            }],
        )
        # Should not raise — v2 skips outputType/inputType check for handled edges
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "2.0"


class TestV2Migration:
    """Test migration from v1 to v2 concepts."""

    def test_v1_to_v2_roundtrip_via_model(self):
        """Parse as v1, export, re-parse as v2."""
        v1_spec = _make_v1_spec(
            [NODE_A, NODE_B],
            [{"id": "e1", "source": "a", "target": "b", "type": "smoothstep"}],
        )
        wf_v1 = WorkflowSpec(**v1_spec)
        exported = wf_v1.model_dump(by_alias=True, exclude_none=True)

        # Add v2 fields
        exported["schemaVersion"] = "2.0"
        exported["manifestVersion"] = "1.0"
        exported["edges"][0]["sourceHandle"] = "text"
        exported["edges"][0]["targetHandle"] = "prompt"
        exported["viewport"] = {"x": 0, "y": 0, "zoom": 1}
        exported["metadata"] = {"tags": []}

        wf_v2 = WorkflowSpec(**exported)
        assert wf_v2.schemaVersion == "2.0"
        assert wf_v2.edges[0].sourceHandle == "text"

    def test_v2_spec_populates_by_name(self):
        """V2 fields can be passed using camelCase aliases."""
        spec = {
            "schemaVersion": "2.0",
            "manifestVersion": "1.0",
            "id": "alias-test",
            "name": "Alias Test",
            "nodes": [NODE_A],
            "edges": [],
        }
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "2.0"
        assert wf.manifestVersion == "1.0"


class TestV2GraphValidation:
    """Test graph validation with v2 spec using backend graph_validator."""

    def test_valid_v2_graph_no_errors(self):
        from backend.app.schemas.graph_validator import validate_graph
        from backend.app.schemas.node_manifest import NodeManifest, PortGroup, PortDefinition

        catalog = {
            "textInput": NodeManifest(
                kind="textInput",
                version="1.0",
                category="input",
                label="Input",
                ports=PortGroup(
                    inputs=[],
                    outputs=[PortDefinition(id="text", type="text")],
                ),
            ),
            "storyboard": NodeManifest(
                kind="storyboard",
                version="1.0",
                category="transform",
                label="Storyboard",
                ports=PortGroup(
                    inputs=[PortDefinition(id="prompt", type="text", required=True)],
                    outputs=[PortDefinition(id="scenes", type="scene", cardinality="many")],
                ),
            ),
        }

        spec = {
            "nodes": [
                {"id": "n1", "kind": "textInput"},
                {"id": "n2", "kind": "storyboard"},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "n1",
                    "sourceHandle": "text",
                    "target": "n2",
                    "targetHandle": "prompt",
                },
            ],
        }

        errors = validate_graph(spec, catalog)
        real_errors = [e for e in errors if e.code != "REQUIRED_PORT"]
        assert len(real_errors) == 0

    def test_cycle_detected_in_v2(self):
        from backend.app.schemas.graph_validator import validate_graph
        from backend.app.schemas.node_manifest import NodeManifest, PortGroup, PortDefinition

        catalog = {
            "textInput": NodeManifest(
                kind="textInput",
                version="1.0",
                category="input",
                label="Input",
                ports=PortGroup(
                    inputs=[PortDefinition(id="in", type="text", required=True)],
                    outputs=[PortDefinition(id="text", type="text")],
                ),
            ),
            "storyboard": NodeManifest(
                kind="storyboard",
                version="1.0",
                category="transform",
                label="Storyboard",
                ports=PortGroup(
                    inputs=[PortDefinition(id="prompt", type="text", required=True)],
                    outputs=[PortDefinition(id="scenes", type="scene")],
                ),
            ),
        }

        spec = {
            "nodes": [
                {"id": "n1", "kind": "textInput"},
                {"id": "n2", "kind": "storyboard"},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "sourceHandle": "text", "target": "n2", "targetHandle": "prompt"},
                {"id": "e2", "source": "n2", "sourceHandle": "scenes", "target": "n1", "targetHandle": "in"},
            ],
        }

        errors = validate_graph(spec, catalog)
        assert any(e.code == "CYCLE" for e in errors)


class TestV2ExistingTestsCompatibility:
    """Ensure existing v1 test patterns still work with updated model."""

    def test_duplicate_node_ids_rejected(self):
        dup_node = {**NODE_A, "id": "dup"}
        dup_node2 = {**NODE_B, "id": "dup"}
        spec = _make_v1_spec([dup_node, dup_node2], [])
        with pytest.raises(Exception, match="节点 ID 必须唯一"):
            WorkflowSpec(**spec)

    def test_dangling_edge_rejected(self):
        spec = _make_v1_spec(
            [NODE_A],
            [{"id": "e1", "source": "a", "target": "nonexistent", "type": "smoothstep"}],
        )
        with pytest.raises(Exception, match="引用了不存在的节点"):
            WorkflowSpec(**spec)

    def test_empty_edges_valid(self):
        spec = _make_v1_spec([NODE_A], [])
        wf = WorkflowSpec(**spec)
        assert len(wf.nodes) == 1
        assert len(wf.edges) == 0
