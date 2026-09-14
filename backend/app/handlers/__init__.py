"""Handler registry — register and retrieve node handlers."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class NodeHandler(Protocol):
    """Node handler protocol."""

    async def execute(self, task: dict, context: dict) -> dict: ...


# Handler registry
_handlers: dict[str, NodeHandler] = {}


def register_handler(kind: str, handler: NodeHandler) -> None:
    """Register a handler for a node kind."""
    _handlers[kind] = handler
    logger.debug(f"Registered handler for kind: {kind}")


def get_handler(kind: str) -> NodeHandler | None:
    """Get handler for a node kind."""
    return _handlers.get(kind)


def clear_handlers() -> None:
    """Clear all registered handlers (for testing)."""
    _handlers.clear()


def init_mock_handlers() -> None:
    """Initialize mock handlers for development/testing."""
    from backend.app.handlers.base import (
        TextInputHandler,
        StoryboardHandler,
        TextToImageHandler,
        ImageToVideoHandler,
        VideoConcatHandler,
        OutputHandler,
    )

    clear_handlers()
    register_handler("textInput", TextInputHandler())
    register_handler("storyboard", StoryboardHandler())
    register_handler("textToImage", TextToImageHandler())
    register_handler("imageToVideo", ImageToVideoHandler())
    register_handler("videoConcat", VideoConcatHandler())
    register_handler("output", OutputHandler())
    logger.info("Initialized mock handlers")


def init_real_handlers() -> None:
    """Initialize real handlers that use AI providers."""
    from backend.app.handlers.real_handlers import (
        RealTextInputHandler,
        RealStoryboardHandler,
        RealTextToImageHandler,
        RealImageToVideoHandler,
        RealVideoConcatHandler,
        RealOutputHandler,
    )

    clear_handlers()
    register_handler("textInput", RealTextInputHandler())
    register_handler("storyboard", RealStoryboardHandler())
    register_handler("textToImage", RealTextToImageHandler())
    register_handler("imageToVideo", RealImageToVideoHandler())
    register_handler("videoConcat", RealVideoConcatHandler())
    register_handler("output", RealOutputHandler())
    logger.info("Initialized real handlers")


def init_handlers(use_mock: bool = True) -> None:
    """Initialize handlers based on configuration.

    Args:
        use_mock: If True, use mock handlers; otherwise use real handlers
    """
    if use_mock:
        init_mock_handlers()
    else:
        init_real_handlers()
