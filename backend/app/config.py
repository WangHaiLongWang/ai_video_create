"""Application configuration — Pydantic Settings with environment variable support."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProviderType(str, Enum):
    """Supported AI provider types."""
    MOCK = "mock"
    OLLAMA = "ollama"
    OPENAI = "openai"
    COMFYUI = "comfyui"


class ProviderConfig(BaseModel):
    """Configuration for a specific AI provider."""
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    extra_params: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseSettings):
    """Application settings — loaded from environment variables and .env file."""

    # Provider defaults
    DEFAULT_LLM_PROVIDER: ProviderType = ProviderType.MOCK
    DEFAULT_IMAGE_PROVIDER: ProviderType = ProviderType.MOCK
    DEFAULT_VIDEO_PROVIDER: ProviderType = ProviderType.MOCK

    # Provider configurations
    OLLAMA_API_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_IMAGE_SIZE: str = "1792x1024"

    COMFYUI_API_URL: str = "http://localhost:8188"
    COMFYUI_CHECKPOINT: str = "sd_xl_base_1.0.safetensors"

    # Storage
    ASSET_DIR: str = "data/assets"
    FFMPEG_PATH: str = "ffmpeg"

    # Worker settings
    WORKER_POLL_INTERVAL: float = 0.5
    WORKER_LEASE_SECONDS: int = 30

    # Database
    DB_PATH: str = "data/ai_video_create.db"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def get_provider_config(self, provider_type: ProviderType) -> ProviderConfig:
        """Get configuration for a specific provider type."""
        if provider_type == ProviderType.OLLAMA:
            return ProviderConfig(
                api_url=self.OLLAMA_API_URL,
                model=self.OLLAMA_MODEL,
            )
        elif provider_type == ProviderType.OPENAI:
            return ProviderConfig(
                api_url="https://api.openai.com/v1",
                api_key=self.OPENAI_API_KEY,
                model=self.OPENAI_MODEL,
                extra_params={
                    "image_model": self.OPENAI_IMAGE_MODEL,
                    "image_size": self.OPENAI_IMAGE_SIZE,
                },
            )
        elif provider_type == ProviderType.COMFYUI:
            return ProviderConfig(
                api_url=self.COMFYUI_API_URL,
                extra_params={
                    "checkpoint": self.COMFYUI_CHECKPOINT,
                },
            )
        else:  # MOCK
            return ProviderConfig()


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
