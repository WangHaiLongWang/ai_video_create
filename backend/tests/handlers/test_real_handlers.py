"""Tests for real handlers."""

import pytest
from backend.app.handlers import init_mock_handlers, init_real_handlers, get_handler
from backend.app.handlers.real_handlers import _provider_name
from backend.app.providers import init_providers, clear_providers, get_provider
from backend.app.config import get_settings, reset_settings


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
        assert result.status == "succeeded"
        assert result.output is not None
        assert result.output.type == "text"
        assert result.output.metadata["content"] == "test prompt"

    @pytest.mark.asyncio
    async def test_execute_empty_prompt(self):
        """Test executing with empty prompt."""
        handler = get_handler("textInput")
        task = {
            "id": "task-1",
            "config": {"prompt": ""},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result.status == "succeeded"
        assert result.output.metadata["content"] == ""


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
        assert result.status == "succeeded"
        assert result.output is not None
        assert result.output.type == "text"
        scenes = result.output.metadata["scenes"]
        assert result.output.metadata["count"] == 3
        assert len(scenes) == 3

        # Check scene structure
        scene = scenes[0]
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
        assert result.status == "succeeded"
        assert result.output.type == "image"
        assert result.output.asset_id is not None
        assert result.output.scene_id == "scene-001"
        assert "path" in result.output.metadata

    @pytest.mark.asyncio
    async def test_execute_no_prompt(self):
        """Test image generation with no prompt."""
        handler = get_handler("textToImage")
        task = {
            "id": "task-1",
            "config": {"image_prompt": ""},
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result.status == "failed"
        assert result.error is not None
        assert result.error.code == "NO_PROMPT"


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
        """Real concatenation never reports a synthetic success."""
        handler = get_handler("videoConcat")
        task = {
            "id": "task-1",
            "config": {
                "filename": "output.mp4",
                "video_paths": [],
            },
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result.status == "failed"
        assert result.error.code == "NO_VIDEO_INPUTS"
        assert result.output is None
        assert result.artifacts == []


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
        assert result.status == "succeeded"
        assert result.output is not None
        assert result.output.type == "video"
        assert "message" in result.output.metadata


class TestProviderTrapFallback:
    """Seedream pins provider:"doubao"; mock-only runs must still execute."""

    def setup_method(self):
        import os

        clear_providers()
        init_providers(mock=True)
        init_real_handlers()
        # Pin mock defaults explicitly — a developer .env may select real providers.
        self._env_backup = {
            k: os.environ.get(k)
            for k in (
                "AI_VIDEO_DEFAULT_LLM_PROVIDER",
                "AI_VIDEO_DEFAULT_IMAGE_PROVIDER",
                "AI_VIDEO_DEFAULT_VIDEO_PROVIDER",
            )
        }
        os.environ["AI_VIDEO_DEFAULT_LLM_PROVIDER"] = "mock"
        os.environ["AI_VIDEO_DEFAULT_IMAGE_PROVIDER"] = "mock"
        os.environ["AI_VIDEO_DEFAULT_VIDEO_PROVIDER"] = "mock"
        reset_settings()

    def teardown_method(self):
        import os

        clear_providers()
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_settings()

    def test_doubao_locked_module_resolves_to_mock_without_key(self):
        """A provider:"doubao" module falls back to mock when no doubao key exists."""
        assert get_provider("doubao") is None
        assert get_provider("mock") is not None
        # Defaults are mock (pinned above).
        assert get_settings().DEFAULT_IMAGE_PROVIDER.value == "mock"

        name = _provider_name({"provider": "doubao"}, "image")
        assert name == "mock"

    @pytest.mark.asyncio
    async def test_doubao_locked_image_node_executes_under_mock(self):
        """End-to-end: the pinned-doubao image node produces an image via mock."""
        handler = get_handler("textToImage")
        task = {
            "id": "task-seedream",
            "execution_id": "exec-1",
            "node_id": "seedream-1",
            "item_key": "scene-001",
            "config": {
                "provider": "doubao",
                "image_model": "doubao-seedream-5-0-pro-260628",
                "image_prompt": "A modern city skyline at dawn",
            },
        }
        result = await handler.execute(task, {"worker_id": "test"})
        assert result.status == "succeeded"
        assert result.output.type == "image"
        assert result.output.asset_id is not None

    def test_real_provider_default_does_not_silently_fall_back(self):
        """When the capability default is a real provider, a missing provider fails loudly."""
        import os

        os.environ["AI_VIDEO_DEFAULT_IMAGE_PROVIDER"] = "doubao"
        reset_settings()
        try:
            name = _provider_name({"provider": "doubao"}, "image")
            assert name == "doubao"  # NOT silently rewritten to mock
            assert get_provider(name) is None
        finally:
            os.environ["AI_VIDEO_DEFAULT_IMAGE_PROVIDER"] = "mock"
            reset_settings()
