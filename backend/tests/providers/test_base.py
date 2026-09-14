"""Tests for provider base classes and registry."""

import pytest
from backend.app.providers import (
    init_providers,
    list_providers,
    get_provider,
    clear_providers,
)
from backend.app.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderNotConfiguredError,
)


class TestProviderCapabilities:
    """Tests for ProviderCapabilities model."""

    def test_default_capabilities(self):
        """Test default capabilities are all False."""
        caps = ProviderCapabilities()
        assert caps.text is False
        assert caps.image is False
        assert caps.video is False

    def test_custom_capabilities(self):
        """Test custom capabilities."""
        caps = ProviderCapabilities(text=True, image=True)
        assert caps.text is True
        assert caps.image is True
        assert caps.video is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        caps = ProviderCapabilities(text=True)
        d = caps.model_dump()
        assert d["text"] is True
        assert d["image"] is False


class TestProviderRegistry:
    """Tests for provider registry functions."""

    def setup_method(self):
        """Clear providers before each test."""
        clear_providers()

    def test_register_and_get(self):
        """Test registering and retrieving a provider."""
        from backend.app.providers.mock_provider import MockProvider

        provider = MockProvider()
        init_providers(mock=True)

        retrieved = get_provider("mock")
        assert retrieved is not None
        assert retrieved.name == "mock"

    def test_get_nonexistent_provider(self):
        """Test getting a provider that doesn't exist."""
        result = get_provider("nonexistent")
        assert result is None

    def test_list_providers(self):
        """Test listing all providers."""
        init_providers(mock=True)

        providers = list_providers()
        assert len(providers) >= 1
        assert any(p["name"] == "mock" for p in providers)

    def test_clear_providers(self):
        """Test clearing all providers."""
        init_providers(mock=True)
        assert len(list_providers()) > 0

        clear_providers()
        assert len(list_providers()) == 0

    def test_init_multiple_providers(self):
        """Test initializing multiple providers."""
        init_providers(mock=True, ollama_url="http://localhost:11434")

        providers = list_providers()
        names = [p["name"] for p in providers]
        assert "mock" in names
        # Ollama may fail health check but should still register


class TestProviderErrors:
    """Tests for provider error classes."""

    def test_provider_error(self):
        """Test ProviderError."""
        err = ProviderError("test_provider", "something went wrong")
        assert "test_provider" in str(err)
        assert "something went wrong" in str(err)
        assert err.provider_name == "test_provider"

    def test_provider_error_with_cause(self):
        """Test ProviderError with exception cause."""
        original = ValueError("original error")
        err = ProviderError("test", "wrapper", cause=original)
        assert err.cause is original

    def test_not_configured_error(self):
        """Test ProviderNotConfiguredError."""
        err = ProviderNotConfiguredError("openai", "api_key")
        assert "api_key" in str(err)

    def test_connection_error(self):
        """Test ProviderConnectionError."""
        from backend.app.providers.base import ProviderConnectionError
        err = ProviderConnectionError("ollama", "http://localhost:11434")
        assert "localhost" in str(err)
