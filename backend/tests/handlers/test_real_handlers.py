"""Tests for real handlers."""

import pytest
from backend.app.handlers import init_mock_handlers, init_real_handlers, get_handler
from backend.app.providers import init_providers, clear_providers


class TestHandlerRegistry:
    """Tests for handler registry."""

    def setup_method(self):
        """Initialize mock handlers."""
        clear_providers()
        init_providers(mock=True)
        init_mock_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    def test_register_handlers(self):
        """Test that all handlers are registered."""
        assert get_handler("textInput") is not None
        assert get_handler("storyboard") is not None
        assert get_handler("textToImage") is not None
        assert get_handler("imageToVideo") is not None
        assert get_handler("videoConcat") is not None
        assert get_handler("output") is not None

    def test_get_nonexistent_handler(self):
        """Test getting nonexistent handler returns None."""
        assert get_handler("nonexistent") is None


class TestRealTextInputHandler:
    """Tests for RealTextInputHandler."""

    def setup_method(self):
        """Setup providers and handlers."""
        clear_providers()
        init_providers(mock=True)
        init_real_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    @pytest.mark.asyncio
    async def test_execute_with_prompt(self):
        """Test executing with a prompt."""
        handler = get_handler("textInput")
        task = {
            "id": "task-1",
            "config": {"prompt": "test prompt"},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert "output" in result
        assert result["output"]["type"] == "text"

    @pytest.mark.asyncio
    async def test_execute_empty_prompt(self):
        """Test executing with empty prompt."""
        handler = get_handler("textInput")
        task = {
            "id": "task-1",
            "config": {"prompt": ""},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert result["output"]["content"] == ""


class TestRealStoryboardHandler:
    """Tests for RealStoryboardHandler."""

    def setup_method(self):
        """Setup providers and handlers."""
        clear_providers()
        init_providers(mock=True)
        init_real_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    @pytest.mark.asyncio
    async def test_execute_generates_scenes(self):
        """Test storyboard generates structured scenes."""
        handler = get_handler("storyboard")
        task = {
            "id": "task-1",
            "config": {
                "prompt": "Create a video about nature",
                "scenes": 3,
                "style": "cinematic",
            },
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert result["output"]["type"] == "list<scene>"
        assert result["output"]["count"] == 3
        assert len(result["output"]["scenes"]) == 3

        # Check scene structure
        scene = result["output"]["scenes"][0]
        assert "scene_id" in scene
        assert "narration" in scene
        assert "image_prompt" in scene
        assert "video_prompt" in scene
        assert "duration_seconds" in scene


class TestRealTextToImageHandler:
    """Tests for RealTextToImageHandler."""

    def setup_method(self):
        """Setup providers and handlers."""
        clear_providers()
        init_providers(mock=True)
        init_real_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    @pytest.mark.asyncio
    async def test_execute_generates_image(self):
        """Test image generation."""
        handler = get_handler("textToImage")
        task = {
            "id": "task-1",
            "item_key": "scene-001",
            "config": {
                "provider": "mock",
                "image_prompt": "A beautiful sunset over mountains",
                "width": 1024,
                "height": 768,
            },
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert result["output"]["type"] == "list<image>"
        assert "asset_id" in result["output"]
        assert "path" in result["output"]
        assert result["output"]["scene_id"] == "scene-001"

    @pytest.mark.asyncio
    async def test_execute_no_prompt(self):
        """Test image generation with no prompt."""
        handler = get_handler("textToImage")
        task = {
            "id": "task-1",
            "config": {"image_prompt": ""},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "error"


class TestRealVideoConcatHandler:
    """Tests for RealVideoConcatHandler."""

    def setup_method(self):
        """Setup providers and handlers."""
        clear_providers()
        init_providers(mock=True)
        init_real_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    @pytest.mark.asyncio
    async def test_execute_no_videos(self):
        """Test concatenation with no videos (returns mock)."""
        handler = get_handler("videoConcat")
        task = {
            "id": "task-1",
            "config": {
                "filename": "output.mp4",
                "video_paths": [],
            },
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert result["output"]["type"] == "video"
        assert result["output"]["filename"] == "output.mp4"


class TestRealOutputHandler:
    """Tests for RealOutputHandler."""

    def setup_method(self):
        """Setup providers and handlers."""
        clear_providers()
        init_providers(mock=True)
        init_real_handlers()

    def teardown_method(self):
        """Cleanup."""
        clear_providers()

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test output handler."""
        handler = get_handler("output")
        task = {
            "id": "task-1",
            "config": {},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result["status"] == "ok"
        assert result["output"]["type"] == "final"
        assert "message" in result["output"]
