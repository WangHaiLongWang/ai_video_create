"""Application configuration — Pydantic Settings with environment variable support."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


class ProviderType(str, Enum):
    """Supported AI provider types."""
    MOCK = "mock"
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENAI_COMPAT = "openai_compat"
    DASHSCOPE = "dashscope"
    WAN3 = "wan3"
    DOUBAO = "doubao"
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
    OPENAI_API_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_IMAGE_SIZE: str = "1792x1024"

    # Generic OpenAI-compatible text provider. Defaults to Xiaomi MiMo.
    OPENAI_COMPAT_NAME: str = "Xiaomi MiMo"
    OPENAI_COMPAT_API_URL: str = "https://api.xiaomimimo.com/v1"
    OPENAI_COMPAT_API_KEY: str = ""
    OPENAI_COMPAT_MODEL: str = "mimo-v2.5-pro"
    OPENAI_COMPAT_AUTH_HEADER: str = "api-key"
    OPENAI_COMPAT_AUTH_SCHEME: str = ""
    OPENAI_COMPAT_MAX_TOKENS_PARAM: str = "max_completion_tokens"
    OPENAI_COMPAT_MAX_TOKENS: int = 4096
    OPENAI_COMPAT_TEMPERATURE: float = 1.0
    OPENAI_COMPAT_TOP_P: float = 0.95
    OPENAI_COMPAT_TIMEOUT: float = 120.0

    DASHSCOPE_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_IMAGE_MODEL: str = "qwen-image-3.0"
    DASHSCOPE_IMAGE_SIZE: str = "1280x720"
    DASHSCOPE_USE_ASYNC: bool = False
    DASHSCOPE_PROMPT_EXTEND: bool = True
    DASHSCOPE_PROMPT_EXTEND_MODE: str = "direct"
    DASHSCOPE_ENABLE_THINKING: bool = True
    DASHSCOPE_WATERMARK: bool = False

    WAN3_API_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    WAN3_API_KEY: str = ""
    WAN3_MODEL: str = "wan3.0-video"
    WAN3_RESOLUTION: str = "480P"
    WAN3_RATIO: str = "adaptive"
    WAN3_DURATION: int = 5
    WAN3_AUDIO: bool = True
    WAN3_SEED: int = -1
    WAN3_PROMPT_EXTEND: bool = True
    WAN3_WATERMARK: bool = False
    WAN3_POLL_INTERVAL: float = 5.0
    WAN3_TIMEOUT: int = 1800

    # Volcengine Ark media provider. Model fields may also be Ark endpoint IDs.
    DOUBAO_API_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_API_KEY: str = ""
    DOUBAO_IMAGE_MODEL: str = "doubao-seedream-5-0-pro-260628"
    DOUBAO_VIDEO_MODEL: str = "doubao-seedance-2-5-260628"
    DOUBAO_IMAGE_SIZE: str = "1280x720"
    DOUBAO_VIDEO_RESOLUTION: str = "720p"
    DOUBAO_VIDEO_RATIO: str = "adaptive"
    DOUBAO_VIDEO_DURATION: int = 5
    DOUBAO_SEED: int = -1
    DOUBAO_WATERMARK: bool = False
    DOUBAO_CAMERA_FIXED: bool = False
    DOUBAO_POLL_INTERVAL: float = 5.0
    DOUBAO_TIMEOUT: int = 1800

    COMFYUI_API_URL: str = "http://localhost:8188"
    COMFYUI_CHECKPOINT: str = "sd_xl_base_1.0.safetensors"

    # Storage
    ASSET_DIR: str = "data/assets"
    FFMPEG_PATH: str = "ffmpeg"

    # Worker settings
    WORKER_POLL_INTERVAL: float = 0.5
    WORKER_LEASE_SECONDS: int = 30
    WORKER_COUNT: int = 2

    # Database
    DB_PATH: str = "data/ai_video_create.db"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False

    model_config = {
        "env_prefix": "AI_VIDEO_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @model_validator(mode="after")
    def _validate_worker_count(self) -> "Settings":
        if self.WORKER_COUNT < 1:
            self.WORKER_COUNT = 1
        elif self.WORKER_COUNT > 8:
            self.WORKER_COUNT = 8
        return self

    def get_provider_config(self, provider_type: ProviderType) -> ProviderConfig:
        """Get configuration for a specific provider type."""
        if provider_type == ProviderType.OLLAMA:
            return ProviderConfig(
                api_url=self.OLLAMA_API_URL,
                model=self.OLLAMA_MODEL,
            )
        elif provider_type == ProviderType.OPENAI:
            return ProviderConfig(
                api_url=self.OPENAI_API_URL,
                api_key=self.OPENAI_API_KEY,
                model=self.OPENAI_MODEL,
                extra_params={
                    "image_model": self.OPENAI_IMAGE_MODEL,
                    "image_size": self.OPENAI_IMAGE_SIZE,
                },
            )
        elif provider_type == ProviderType.OPENAI_COMPAT:
            return ProviderConfig(
                api_url=self.OPENAI_COMPAT_API_URL,
                api_key=self.OPENAI_COMPAT_API_KEY,
                model=self.OPENAI_COMPAT_MODEL,
                extra_params={
                    "name": self.OPENAI_COMPAT_NAME,
                    "auth_header": self.OPENAI_COMPAT_AUTH_HEADER,
                    "auth_scheme": self.OPENAI_COMPAT_AUTH_SCHEME,
                    "max_tokens_param": self.OPENAI_COMPAT_MAX_TOKENS_PARAM,
                    "max_tokens": self.OPENAI_COMPAT_MAX_TOKENS,
                    "temperature": self.OPENAI_COMPAT_TEMPERATURE,
                    "top_p": self.OPENAI_COMPAT_TOP_P,
                    "timeout": self.OPENAI_COMPAT_TIMEOUT,
                },
            )
        elif provider_type == ProviderType.COMFYUI:
            return ProviderConfig(
                api_url=self.COMFYUI_API_URL,
                extra_params={
                    "checkpoint": self.COMFYUI_CHECKPOINT,
                },
            )
        elif provider_type == ProviderType.DASHSCOPE:
            return ProviderConfig(
                api_url=self.DASHSCOPE_API_URL,
                api_key=self.DASHSCOPE_API_KEY or self.OPENAI_API_KEY,
                model=self.DASHSCOPE_IMAGE_MODEL,
                extra_params={
                    "image_size": self.DASHSCOPE_IMAGE_SIZE,
                    "use_async": self.DASHSCOPE_USE_ASYNC,
                    "prompt_extend": self.DASHSCOPE_PROMPT_EXTEND,
                    "prompt_extend_mode": self.DASHSCOPE_PROMPT_EXTEND_MODE,
                    "enable_thinking": self.DASHSCOPE_ENABLE_THINKING,
                    "watermark": self.DASHSCOPE_WATERMARK,
                },
            )
        elif provider_type == ProviderType.WAN3:
            return ProviderConfig(
                api_url=self.WAN3_API_URL,
                api_key=self.WAN3_API_KEY or self.DASHSCOPE_API_KEY or self.OPENAI_API_KEY,
                model=self.WAN3_MODEL,
                extra_params={
                    "resolution": self.WAN3_RESOLUTION,
                    "ratio": self.WAN3_RATIO,
                    "duration": self.WAN3_DURATION,
                    "audio": self.WAN3_AUDIO,
                    "seed": self.WAN3_SEED,
                    "prompt_extend": self.WAN3_PROMPT_EXTEND,
                    "watermark": self.WAN3_WATERMARK,
                    "poll_interval": self.WAN3_POLL_INTERVAL,
                    "timeout": self.WAN3_TIMEOUT,
                },
            )
        elif provider_type == ProviderType.DOUBAO:
            return ProviderConfig(
                api_url=self.DOUBAO_API_URL,
                api_key=self.DOUBAO_API_KEY,
                model=self.DOUBAO_VIDEO_MODEL,
                extra_params={
                    "image_model": self.DOUBAO_IMAGE_MODEL,
                    "image_size": self.DOUBAO_IMAGE_SIZE,
                    "resolution": self.DOUBAO_VIDEO_RESOLUTION,
                    "ratio": self.DOUBAO_VIDEO_RATIO,
                    "duration": self.DOUBAO_VIDEO_DURATION,
                    "seed": self.DOUBAO_SEED,
                    "watermark": self.DOUBAO_WATERMARK,
                    "camera_fixed": self.DOUBAO_CAMERA_FIXED,
                    "poll_interval": self.DOUBAO_POLL_INTERVAL,
                    "timeout": self.DOUBAO_TIMEOUT,
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
