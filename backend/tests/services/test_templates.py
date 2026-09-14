"""Tests for Template service."""

import pytest
from backend.app.services.templates import TemplateService
from backend.app.models import WorkflowSpec


class TestTemplateService:
    """Tests for TemplateService."""

    def setup_method(self):
        self.service = TemplateService()

    def test_list_templates(self):
        """Test listing built-in templates."""
        templates = self.service.list_templates()
        assert len(templates) >= 3
        ids = [t.id for t in templates]
        assert "prompt-to-video" in ids
        assert "image-storyboard" in ids
        assert "quick-video" in ids

    def test_get_template(self):
        """Test getting template detail."""
        detail = self.service.get_template("prompt-to-video")
        assert detail is not None
        assert detail.name == "提示词生成视频"
        assert len(detail.spec.nodes) == 6

    def test_get_nonexistent_template(self):
        """Test getting nonexistent template."""
        assert self.service.get_template("nonexistent") is None

    def test_create_from_template(self):
        """Test creating workflow from template."""
        spec = self.service.create_from_template("prompt-to-video")
        assert spec is not None
        assert isinstance(spec, WorkflowSpec)
        assert len(spec.nodes) == 6
        assert spec.id != "template-prompt-to-video"  # New ID

    def test_create_with_params(self):
        """Test creating with custom params."""
        spec = self.service.create_from_template("prompt-to-video", {
            "name": "我的视频",
            "prompt": "自然风光",
        })
        assert spec is not None
        assert spec.name == "我的视频"
        # Check prompt was applied to textInput node
        for node in spec.nodes:
            if node.data.kind == "textInput":
                assert node.data.config.get("prompt") == "自然风光"

    def test_save_as_template(self):
        """Test saving workflow as template."""
        spec = WorkflowSpec(
            id="test", name="Test",
            nodes=[], edges=[],
        )
        template_id = self.service.save_as_template(spec, "自定义模板", "测试模板")
        assert template_id.startswith("custom:")

        # Verify it appears in list
        templates = self.service.list_templates()
        assert any(t.id == template_id for t in templates)

    def test_delete_template(self):
        """Test deleting custom template."""
        spec = WorkflowSpec(id="test", name="Test", nodes=[], edges=[])
        template_id = self.service.save_as_template(spec, "ToDelete")

        result = self.service.delete_template(template_id)
        assert result is True
        assert self.service.get_template(template_id) is None

    def test_delete_builtin_template_fails(self):
        """Test deleting built-in template returns False."""
        result = self.service.delete_template("prompt-to-video")
        assert result is False

    def test_create_from_nonexistent_returns_none(self):
        """Test creating from nonexistent template returns None."""
        assert self.service.create_from_template("nonexistent") is None
