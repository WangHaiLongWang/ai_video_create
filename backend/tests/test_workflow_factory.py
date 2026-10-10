"""Tests for workflow_factory — generated graphs must be port-valid."""

from backend.app.domain.graph_validation import (
    extract_nodes_edges_from_spec,
    raise_if_invalid,
)
from backend.app.workflow_factory import create_prompt_to_video


class TestCreatePromptToVideo:
    """Tests for create_prompt_to_video."""

    def test_generated_graph_is_port_valid(self):
        """Test generated edges carry handles that satisfy required ports."""
        spec = create_prompt_to_video("生成 3 个镜头的滑雪教学视频")
        nodes, edges = extract_nodes_edges_from_spec(spec.model_dump())
        assert raise_if_invalid(nodes, edges) == []
