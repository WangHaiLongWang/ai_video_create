"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ProviderCapabilities(BaseModel):
    """Capabilities of a provider."""
    text: bool = False
    image: bool = False
    video: bool = False


class BaseProvider(ABC):
    """Abstract base class for all AI providers.

    Subclasses must implement at least one capability:
    - text: Generate text from prompts
    - image: Generate images from prompts
    - video: Generate videos from images/prompts
    """

    name: str
    capabilities: ProviderCapabilities

    @abstractmethod
    async def generate_text(self, prompt: str, config: dict[str, Any] | None = None) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt
            config: Optional configuration (temperature, max_tokens, etc.)

        Returns:
            Generated text content

        Raises:
            ProviderError: If generation fails
        """
        ...

    @abstractmethod
    async def generate_image(self, prompt: str, config: dict[str, Any] | None = None) -> bytes:
        """Generate an image from a prompt.

        Args:
            prompt: The input prompt describing the image
            config: Optional configuration (size, quality, style, etc.)

        Returns:
            Image data as bytes (PNG format)

        Raises:
            ProviderError: If generation fails
        """
        ...

    @abstractmethod
    async def generate_video(
        self, image_path: str, prompt: str, config: dict[str, Any] | None = None
    ) -> bytes:
        """Generate a video from an image and prompt.

        Args:
            image_path: Path to the input image
            prompt: The input prompt describing the video motion
            config: Optional configuration (duration, fps, etc.)

        Returns:
            Video data as bytes (MP4 format)

        Raises:
            ProviderError: If generation fails
        """
        ...

    async def health_check(self) -> bool:
        """Check if the provider is available and configured correctly.

        Returns:
            True if healthy, False otherwise
        """
        return True


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, provider_name: str, message: str, cause: Exception | None = None):
        self.provider_name = provider_name
        self.cause = cause
        super().__init__(f"[{provider_name}] {message}")


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is not properly configured."""

    def __init__(self, provider_name: str, missing_config: str):
        super().__init__(provider_name, f"Not configured: {missing_config}")


class ProviderConnectionError(ProviderError):
    """Raised when unable to connect to provider."""

    def __init__(self, provider_name: str, url: str, cause: Exception | None = None):
        super().__init__(provider_name, f"Cannot connect to {url}", cause)


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is hit."""

    def __init__(self, provider_name: str, retry_after: float | None = None):
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f", retry after {retry_after}s"
        super().__init__(provider_name, msg)
