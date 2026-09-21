"""Configuration API — manage providers and settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.config import get_settings, ProviderType
from backend.app.providers import list_providers, get_provider, clear_providers, init_providers
from backend.app.handlers import init_handlers
from backend.app.services.asset_manager import get_asset_manager

router = APIRouter(prefix="/api/config", tags=["config"])


class ProviderInfo(BaseModel):
    """Provider information response."""
    name: str
    display_name: str = ""
    capabilities: dict[str, bool]


class SettingsResponse(BaseModel):
    """Settings response (without secrets)."""
    default_llm_provider: str
    default_image_provider: str
    default_video_provider: str
    ollama_api_url: str
    ollama_model: str
    openai_api_url: str
    openai_model: str
    openai_image_model: str
    openai_compat_name: str
    openai_compat_api_url: str
    openai_compat_model: str
    openai_compat_auth_header: str
    openai_compat_auth_scheme: str
    openai_compat_max_tokens_param: str
    openai_compat_max_tokens: int
    openai_compat_temperature: float
    openai_compat_top_p: float
    openai_compat_timeout: float
    dashscope_api_url: str
    dashscope_image_model: str
    dashscope_image_size: str
    dashscope_use_async: bool
    dashscope_prompt_extend: bool
    dashscope_prompt_extend_mode: str
    dashscope_enable_thinking: bool
    dashscope_watermark: bool
    comfyui_api_url: str
    wan3_api_url: str
    wan3_model: str
    wan3_resolution: str
    wan3_ratio: str
    wan3_duration: int
    wan3_audio: bool
    wan3_seed: int
    wan3_prompt_extend: bool
    wan3_watermark: bool
    wan3_poll_interval: float
    wan3_timeout: int
    doubao_api_url: str
    doubao_image_model: str
    doubao_video_model: str
    doubao_image_size: str
    doubao_video_resolution: str
    doubao_video_ratio: str
    doubao_video_duration: int
    doubao_seed: int
    doubao_watermark: bool
    doubao_camera_fixed: bool
    doubao_poll_interval: float
    doubao_timeout: int
    asset_dir: str
    ffmpeg_path: str


class UpdateSettingsRequest(BaseModel):
    """Settings update request."""
    default_llm_provider: str | None = None
    default_image_provider: str | None = None
    default_video_provider: str | None = None
    ollama_api_url: str | None = None
    ollama_model: str | None = None
    openai_api_key: str | None = None
    openai_api_url: str | None = None
    openai_model: str | None = None
    openai_image_model: str | None = None
    openai_compat_name: str | None = None
    openai_compat_api_url: str | None = None
    openai_compat_api_key: str | None = None
    openai_compat_model: str | None = None
    openai_compat_auth_header: str | None = None
    openai_compat_auth_scheme: str | None = None
    openai_compat_max_tokens_param: str | None = None
    openai_compat_max_tokens: int | None = None
    openai_compat_temperature: float | None = None
    openai_compat_top_p: float | None = None
    openai_compat_timeout: float | None = None
    dashscope_api_url: str | None = None
    dashscope_api_key: str | None = None
    dashscope_image_model: str | None = None
    dashscope_image_size: str | None = None
    dashscope_use_async: bool | None = None
    dashscope_prompt_extend: bool | None = None
    dashscope_prompt_extend_mode: str | None = None
    dashscope_enable_thinking: bool | None = None
    dashscope_watermark: bool | None = None
    comfyui_api_url: str | None = None
    wan3_api_url: str | None = None
    wan3_api_key: str | None = None
    wan3_model: str | None = None
    wan3_resolution: str | None = None
    wan3_ratio: str | None = None
    wan3_duration: int | None = None
    wan3_audio: bool | None = None
    wan3_seed: int | None = None
    wan3_prompt_extend: bool | None = None
    wan3_watermark: bool | None = None
    wan3_poll_interval: float | None = None
    wan3_timeout: int | None = None
    doubao_api_url: str | None = None
    doubao_api_key: str | None = None
    doubao_image_model: str | None = None
    doubao_video_model: str | None = None
    doubao_image_size: str | None = None
    doubao_video_resolution: str | None = None
    doubao_video_ratio: str | None = None
    doubao_video_duration: int | None = None
    doubao_seed: int | None = None
    doubao_watermark: bool | None = None
    doubao_camera_fixed: bool | None = None
    doubao_poll_interval: float | None = None
    doubao_timeout: int | None = None


class TestProviderRequest(BaseModel):
    """Provider test request."""
    provider_name: str


class AssetInfo(BaseModel):
    """Asset information."""
    path: str
    url: str
    size: int
    created: str
    modified: str
    extension: str


@router.get("/providers")
async def get_providers() -> list[ProviderInfo]:
    """List all registered providers."""
    providers = list_providers()
    return [ProviderInfo(**p) for p in providers]


@router.get("/settings")
async def get_settings_endpoint() -> SettingsResponse:
    """Get current settings (without secrets)."""
    settings = get_settings()
    return SettingsResponse(
        default_llm_provider=settings.DEFAULT_LLM_PROVIDER.value,
        default_image_provider=settings.DEFAULT_IMAGE_PROVIDER.value,
        default_video_provider=settings.DEFAULT_VIDEO_PROVIDER.value,
        ollama_api_url=settings.OLLAMA_API_URL,
        ollama_model=settings.OLLAMA_MODEL,
        openai_api_url=settings.OPENAI_API_URL,
        openai_model=settings.OPENAI_MODEL,
        openai_image_model=settings.OPENAI_IMAGE_MODEL,
        openai_compat_name=settings.OPENAI_COMPAT_NAME,
        openai_compat_api_url=settings.OPENAI_COMPAT_API_URL,
        openai_compat_model=settings.OPENAI_COMPAT_MODEL,
        openai_compat_auth_header=settings.OPENAI_COMPAT_AUTH_HEADER,
        openai_compat_auth_scheme=settings.OPENAI_COMPAT_AUTH_SCHEME,
        openai_compat_max_tokens_param=settings.OPENAI_COMPAT_MAX_TOKENS_PARAM,
        openai_compat_max_tokens=settings.OPENAI_COMPAT_MAX_TOKENS,
        openai_compat_temperature=settings.OPENAI_COMPAT_TEMPERATURE,
        openai_compat_top_p=settings.OPENAI_COMPAT_TOP_P,
        openai_compat_timeout=settings.OPENAI_COMPAT_TIMEOUT,
        dashscope_api_url=settings.DASHSCOPE_API_URL,
        dashscope_image_model=settings.DASHSCOPE_IMAGE_MODEL,
        dashscope_image_size=settings.DASHSCOPE_IMAGE_SIZE,
        dashscope_use_async=settings.DASHSCOPE_USE_ASYNC,
        dashscope_prompt_extend=settings.DASHSCOPE_PROMPT_EXTEND,
        dashscope_prompt_extend_mode=settings.DASHSCOPE_PROMPT_EXTEND_MODE,
        dashscope_enable_thinking=settings.DASHSCOPE_ENABLE_THINKING,
        dashscope_watermark=settings.DASHSCOPE_WATERMARK,
        comfyui_api_url=settings.COMFYUI_API_URL,
        wan3_api_url=settings.WAN3_API_URL,
        wan3_model=settings.WAN3_MODEL,
        wan3_resolution=settings.WAN3_RESOLUTION,
        wan3_ratio=settings.WAN3_RATIO,
        wan3_duration=settings.WAN3_DURATION,
        wan3_audio=settings.WAN3_AUDIO,
        wan3_seed=settings.WAN3_SEED,
        wan3_prompt_extend=settings.WAN3_PROMPT_EXTEND,
        wan3_watermark=settings.WAN3_WATERMARK,
        wan3_poll_interval=settings.WAN3_POLL_INTERVAL,
        wan3_timeout=settings.WAN3_TIMEOUT,
        doubao_api_url=settings.DOUBAO_API_URL,
        doubao_image_model=settings.DOUBAO_IMAGE_MODEL,
        doubao_video_model=settings.DOUBAO_VIDEO_MODEL,
        doubao_image_size=settings.DOUBAO_IMAGE_SIZE,
        doubao_video_resolution=settings.DOUBAO_VIDEO_RESOLUTION,
        doubao_video_ratio=settings.DOUBAO_VIDEO_RATIO,
        doubao_video_duration=settings.DOUBAO_VIDEO_DURATION,
        doubao_seed=settings.DOUBAO_SEED,
        doubao_watermark=settings.DOUBAO_WATERMARK,
        doubao_camera_fixed=settings.DOUBAO_CAMERA_FIXED,
        doubao_poll_interval=settings.DOUBAO_POLL_INTERVAL,
        doubao_timeout=settings.DOUBAO_TIMEOUT,
        asset_dir=settings.ASSET_DIR,
        ffmpeg_path=settings.FFMPEG_PATH,
    )


@router.put("/settings")
async def update_settings(request: UpdateSettingsRequest) -> dict[str, str]:
    """Update settings and reinitialize providers/handlers.

    Note: This updates the in-memory settings only.
    For persistent changes, update the .env file.
    """
    settings = get_settings()

    # Update settings (in-memory only)
    if request.default_llm_provider:
        try:
            settings.DEFAULT_LLM_PROVIDER = ProviderType(request.default_llm_provider)
        except ValueError:
            raise HTTPException(400, f"Invalid provider type: {request.default_llm_provider}")

    if request.default_image_provider:
        try:
            settings.DEFAULT_IMAGE_PROVIDER = ProviderType(request.default_image_provider)
        except ValueError:
            raise HTTPException(400, f"Invalid provider type: {request.default_image_provider}")

    if request.default_video_provider:
        try:
            settings.DEFAULT_VIDEO_PROVIDER = ProviderType(request.default_video_provider)
        except ValueError:
            raise HTTPException(400, f"Invalid provider type: {request.default_video_provider}")

    if request.ollama_api_url:
        settings.OLLAMA_API_URL = request.ollama_api_url
    if request.ollama_model:
        settings.OLLAMA_MODEL = request.ollama_model
    if request.openai_api_key:
        settings.OPENAI_API_KEY = request.openai_api_key
    if request.openai_api_url:
        settings.OPENAI_API_URL = request.openai_api_url
    if request.openai_model:
        settings.OPENAI_MODEL = request.openai_model
    if request.openai_image_model:
        settings.OPENAI_IMAGE_MODEL = request.openai_image_model
    if request.openai_compat_name:
        settings.OPENAI_COMPAT_NAME = request.openai_compat_name
    if request.openai_compat_api_url:
        settings.OPENAI_COMPAT_API_URL = request.openai_compat_api_url
    if request.openai_compat_api_key:
        settings.OPENAI_COMPAT_API_KEY = request.openai_compat_api_key
    if request.openai_compat_model:
        settings.OPENAI_COMPAT_MODEL = request.openai_compat_model
    if request.openai_compat_auth_header:
        if any(char in request.openai_compat_auth_header for char in "\r\n"):
            raise HTTPException(400, "invalid openai_compat_auth_header")
        settings.OPENAI_COMPAT_AUTH_HEADER = request.openai_compat_auth_header
    if request.openai_compat_auth_scheme is not None:
        settings.OPENAI_COMPAT_AUTH_SCHEME = request.openai_compat_auth_scheme
    if request.openai_compat_max_tokens_param:
        if request.openai_compat_max_tokens_param not in {"max_tokens", "max_completion_tokens"}:
            raise HTTPException(400, "unsupported max tokens parameter")
        settings.OPENAI_COMPAT_MAX_TOKENS_PARAM = request.openai_compat_max_tokens_param
    if request.openai_compat_max_tokens is not None:
        if not 1 <= request.openai_compat_max_tokens <= 131072:
            raise HTTPException(400, "openai_compat_max_tokens out of range")
        settings.OPENAI_COMPAT_MAX_TOKENS = request.openai_compat_max_tokens
    if request.openai_compat_temperature is not None:
        if not 0 <= request.openai_compat_temperature <= 2:
            raise HTTPException(400, "openai_compat_temperature out of range")
        settings.OPENAI_COMPAT_TEMPERATURE = request.openai_compat_temperature
    if request.openai_compat_top_p is not None:
        if not 0 < request.openai_compat_top_p <= 1:
            raise HTTPException(400, "openai_compat_top_p out of range")
        settings.OPENAI_COMPAT_TOP_P = request.openai_compat_top_p
    if request.openai_compat_timeout is not None:
        if not 1 <= request.openai_compat_timeout <= 1800:
            raise HTTPException(400, "openai_compat_timeout out of range")
        settings.OPENAI_COMPAT_TIMEOUT = request.openai_compat_timeout
    if request.dashscope_api_url:
        settings.DASHSCOPE_API_URL = request.dashscope_api_url
    if request.dashscope_api_key:
        settings.DASHSCOPE_API_KEY = request.dashscope_api_key
    if request.dashscope_image_model:
        settings.DASHSCOPE_IMAGE_MODEL = request.dashscope_image_model
    if request.dashscope_image_size:
        settings.DASHSCOPE_IMAGE_SIZE = request.dashscope_image_size
    if request.dashscope_use_async is not None:
        settings.DASHSCOPE_USE_ASYNC = request.dashscope_use_async
    if request.dashscope_prompt_extend is not None:
        settings.DASHSCOPE_PROMPT_EXTEND = request.dashscope_prompt_extend
    if request.dashscope_prompt_extend_mode is not None:
        if request.dashscope_prompt_extend_mode not in {"direct", "agent"}:
            raise HTTPException(400, "dashscope_prompt_extend_mode must be direct or agent")
        settings.DASHSCOPE_PROMPT_EXTEND_MODE = request.dashscope_prompt_extend_mode
    if request.dashscope_enable_thinking is not None:
        settings.DASHSCOPE_ENABLE_THINKING = request.dashscope_enable_thinking
    if request.dashscope_watermark is not None:
        settings.DASHSCOPE_WATERMARK = request.dashscope_watermark
    if request.comfyui_api_url:
        settings.COMFYUI_API_URL = request.comfyui_api_url
    if request.wan3_api_url:
        settings.WAN3_API_URL = request.wan3_api_url
    if request.wan3_api_key:
        settings.WAN3_API_KEY = request.wan3_api_key
    if request.wan3_model:
        if request.wan3_model not in {"wan3.0-video", "wan3.0-video-prime"}:
            raise HTTPException(400, "unsupported wan3_model")
        settings.WAN3_MODEL = request.wan3_model
    if request.wan3_resolution:
        resolution = request.wan3_resolution.upper()
        if resolution not in {"480P", "720P", "1080P"}:
            raise HTTPException(400, "wan3_resolution must be 480P, 720P or 1080P")
        settings.WAN3_RESOLUTION = resolution
    if request.wan3_ratio:
        if request.wan3_ratio not in {"adaptive", "16:9", "4:3", "1:1", "3:4", "9:16"}:
            raise HTTPException(400, "unsupported wan3_ratio")
        settings.WAN3_RATIO = request.wan3_ratio
    if request.wan3_duration is not None:
        if request.wan3_duration != -1 and not 2 <= request.wan3_duration <= 30:
            raise HTTPException(400, "wan3_duration must be -1 or between 2 and 30")
        settings.WAN3_DURATION = request.wan3_duration
    if request.wan3_audio is not None:
        settings.WAN3_AUDIO = request.wan3_audio
    if request.wan3_seed is not None:
        if request.wan3_seed != -1 and not 0 <= request.wan3_seed <= 2147483647:
            raise HTTPException(400, "invalid wan3_seed")
        settings.WAN3_SEED = request.wan3_seed
    if request.wan3_prompt_extend is not None:
        settings.WAN3_PROMPT_EXTEND = request.wan3_prompt_extend
    if request.wan3_watermark is not None:
        settings.WAN3_WATERMARK = request.wan3_watermark
    if request.wan3_poll_interval is not None:
        if request.wan3_poll_interval < 1:
            raise HTTPException(400, "wan3_poll_interval must be at least 1 second")
        settings.WAN3_POLL_INTERVAL = request.wan3_poll_interval
    if request.wan3_timeout is not None:
        if request.wan3_timeout < 60:
            raise HTTPException(400, "wan3_timeout must be at least 60 seconds")
        settings.WAN3_TIMEOUT = request.wan3_timeout
    if request.doubao_api_url:
        settings.DOUBAO_API_URL = request.doubao_api_url
    if request.doubao_api_key:
        settings.DOUBAO_API_KEY = request.doubao_api_key
    if request.doubao_image_model:
        settings.DOUBAO_IMAGE_MODEL = request.doubao_image_model
    if request.doubao_video_model:
        settings.DOUBAO_VIDEO_MODEL = request.doubao_video_model
    if request.doubao_image_size:
        settings.DOUBAO_IMAGE_SIZE = request.doubao_image_size
    if request.doubao_video_resolution:
        value = request.doubao_video_resolution.lower()
        if value not in {"480p", "720p", "1080p"}:
            raise HTTPException(400, "doubao_video_resolution must be 480p, 720p or 1080p")
        settings.DOUBAO_VIDEO_RESOLUTION = value
    if request.doubao_video_ratio:
        if request.doubao_video_ratio not in {"adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"}:
            raise HTTPException(400, "unsupported doubao_video_ratio")
        settings.DOUBAO_VIDEO_RATIO = request.doubao_video_ratio
    if request.doubao_video_duration is not None:
        if request.doubao_video_duration not in {5, 10}:
            raise HTTPException(400, "doubao_video_duration must be 5 or 10")
        settings.DOUBAO_VIDEO_DURATION = request.doubao_video_duration
    if request.doubao_seed is not None:
        if request.doubao_seed < -1:
            raise HTTPException(400, "doubao_seed must be -1 or non-negative")
        settings.DOUBAO_SEED = request.doubao_seed
    if request.doubao_watermark is not None:
        settings.DOUBAO_WATERMARK = request.doubao_watermark
    if request.doubao_camera_fixed is not None:
        settings.DOUBAO_CAMERA_FIXED = request.doubao_camera_fixed
    if request.doubao_poll_interval is not None:
        if request.doubao_poll_interval < 1:
            raise HTTPException(400, "doubao_poll_interval must be at least 1 second")
        settings.DOUBAO_POLL_INTERVAL = request.doubao_poll_interval
    if request.doubao_timeout is not None:
        if request.doubao_timeout < 60:
            raise HTTPException(400, "doubao_timeout must be at least 60 seconds")
        settings.DOUBAO_TIMEOUT = request.doubao_timeout

    # Reinitialize providers
    clear_providers()
    init_providers(
        mock=True,
        ollama_url=settings.OLLAMA_API_URL if settings.DEFAULT_LLM_PROVIDER.value == "ollama" else None,
        openai_key=settings.OPENAI_API_KEY if (
            settings.DEFAULT_LLM_PROVIDER.value == "openai"
            or settings.DEFAULT_IMAGE_PROVIDER.value == "openai"
        ) else None,
        openai_url=settings.OPENAI_API_URL,
        openai_model=settings.OPENAI_MODEL,
        openai_image_model=settings.OPENAI_IMAGE_MODEL,
        openai_compat_key=settings.OPENAI_COMPAT_API_KEY if (
            settings.DEFAULT_LLM_PROVIDER.value == "openai_compat"
        ) else None,
        openai_compat_url=settings.OPENAI_COMPAT_API_URL,
        openai_compat_model=settings.OPENAI_COMPAT_MODEL,
        openai_compat_name=settings.OPENAI_COMPAT_NAME,
        openai_compat_auth_header=settings.OPENAI_COMPAT_AUTH_HEADER,
        openai_compat_auth_scheme=settings.OPENAI_COMPAT_AUTH_SCHEME,
        openai_compat_max_tokens_param=settings.OPENAI_COMPAT_MAX_TOKENS_PARAM,
        openai_compat_default_config={
            "max_tokens": settings.OPENAI_COMPAT_MAX_TOKENS,
            "temperature": settings.OPENAI_COMPAT_TEMPERATURE,
            "top_p": settings.OPENAI_COMPAT_TOP_P,
            "timeout": settings.OPENAI_COMPAT_TIMEOUT,
        },
        dashscope_key=(settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY) if (
            settings.DEFAULT_IMAGE_PROVIDER.value == "dashscope"
        ) else None,
        dashscope_url=settings.DASHSCOPE_API_URL,
        dashscope_image_model=settings.DASHSCOPE_IMAGE_MODEL,
        dashscope_default_config={
            "size": settings.DASHSCOPE_IMAGE_SIZE,
            "use_async": settings.DASHSCOPE_USE_ASYNC,
            "prompt_extend": settings.DASHSCOPE_PROMPT_EXTEND,
            "prompt_extend_mode": settings.DASHSCOPE_PROMPT_EXTEND_MODE,
            "enable_thinking": settings.DASHSCOPE_ENABLE_THINKING,
            "watermark": settings.DASHSCOPE_WATERMARK,
        },
        wan3_key=(settings.WAN3_API_KEY or settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY) if (
            settings.DEFAULT_VIDEO_PROVIDER.value == "wan3"
        ) else None,
        wan3_url=settings.WAN3_API_URL,
        wan3_model=settings.WAN3_MODEL,
        wan3_default_config={
            "resolution": settings.WAN3_RESOLUTION,
            "ratio": settings.WAN3_RATIO,
            "duration": settings.WAN3_DURATION,
            "audio": settings.WAN3_AUDIO,
            "seed": settings.WAN3_SEED,
            "prompt_extend": settings.WAN3_PROMPT_EXTEND,
            "watermark": settings.WAN3_WATERMARK,
            "poll_interval": settings.WAN3_POLL_INTERVAL,
            "timeout": settings.WAN3_TIMEOUT,
        },
        doubao_key=settings.DOUBAO_API_KEY if (
            settings.DEFAULT_IMAGE_PROVIDER.value == "doubao"
            or settings.DEFAULT_VIDEO_PROVIDER.value == "doubao"
        ) else None,
        doubao_url=settings.DOUBAO_API_URL,
        doubao_image_model=settings.DOUBAO_IMAGE_MODEL,
        doubao_video_model=settings.DOUBAO_VIDEO_MODEL,
        doubao_default_config={
            "size": settings.DOUBAO_IMAGE_SIZE,
            "resolution": settings.DOUBAO_VIDEO_RESOLUTION,
            "ratio": settings.DOUBAO_VIDEO_RATIO,
            "duration": settings.DOUBAO_VIDEO_DURATION,
            "seed": settings.DOUBAO_SEED,
            "watermark": settings.DOUBAO_WATERMARK,
            "camera_fixed": settings.DOUBAO_CAMERA_FIXED,
            "poll_interval": settings.DOUBAO_POLL_INTERVAL,
            "timeout": settings.DOUBAO_TIMEOUT,
        },
        comfyui_url=settings.COMFYUI_API_URL if (
            settings.DEFAULT_IMAGE_PROVIDER.value == "comfyui"
            or settings.DEFAULT_VIDEO_PROVIDER.value == "comfyui"
        ) else None,
    )

    # Each real handler resolves the configured provider for its capability.
    init_handlers(use_mock=False)

    return {"status": "ok", "message": "Settings updated and providers reinitialized"}


@router.post("/test-provider")
async def test_provider(request: TestProviderRequest) -> dict[str, Any]:
    """Test a provider connection."""
    provider = get_provider(request.provider_name)
    if not provider:
        raise HTTPException(404, f"Provider not found: {request.provider_name}")

    try:
        is_healthy = await provider.health_check()
        return {
            "status": "ok" if is_healthy else "error",
            "provider": request.provider_name,
            "healthy": is_healthy,
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": request.provider_name,
            "healthy": False,
            "error": str(e),
        }


@router.get("/assets")
async def list_assets(category: str = "") -> list[AssetInfo]:
    """List all assets."""
    asset_manager = get_asset_manager()
    assets = asset_manager.list_assets(category)
    return [AssetInfo(**a) for a in assets]


@router.get("/assets/stats")
async def get_asset_stats() -> dict[str, Any]:
    """Get asset storage statistics."""
    asset_manager = get_asset_manager()

    total_size = asset_manager.get_total_size()
    image_count = len(asset_manager.list_assets("images"))
    video_count = len(asset_manager.list_assets("videos"))
    final_count = len(asset_manager.list_assets("final"))
    temp_count = len(asset_manager.list_assets("temp"))

    return {
        "total_size": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "counts": {
            "images": image_count,
            "videos": video_count,
            "final": final_count,
            "temp": temp_count,
        },
    }


@router.post("/assets/cleanup")
async def cleanup_assets(max_age_days: int = 7) -> dict[str, Any]:
    """Cleanup old temporary assets."""
    asset_manager = get_asset_manager()
    deleted_count = asset_manager.cleanup_old_assets(max_age_days)
    return {
        "status": "ok",
        "deleted_count": deleted_count,
        "max_age_days": max_age_days,
    }


# ---------------------------------------------------------------------------
# Secret rotation
# ---------------------------------------------------------------------------


class RotateSecretsRequest(BaseModel):
    """Request body for rotating all secrets to a new master key."""
    new_master_key: str
    old_master_key: str | None = None  # If None, reads from current env/fallback


class RotateSecretsResponse(BaseModel):
    """Response after secret rotation."""
    status: str
    rotated_count: int
    message: str


@router.post("/rotate-secrets")
async def rotate_all_secrets(request: RotateSecretsRequest) -> RotateSecretsResponse:
    """Re-encrypt all secrets with a new master key.

    The old master key is required either via the request body or the
    ``SECRET_ENCRYPTION_KEY`` environment variable.
    """
    import os

    from backend.app.repositories.configs import (
        get_encrypted_keys,
        get_raw,
        list_secrets,
        re_encrypt_value,
    )
    from backend.app.services.secret_encryption import rotate_key

    old_key = request.old_master_key or os.environ.get("SECRET_ENCRYPTION_KEY", "")
    if not old_key:
        raise HTTPException(
            status_code=400,
            detail="Old master key is required. Provide it in the request body or set SECRET_ENCRYPTION_KEY env var.",
        )

    # Gather all keys that hold secrets
    secret_keys = list_secrets()
    encrypted_keys = get_encrypted_keys()
    keys_to_rotate = list(set(secret_keys + encrypted_keys))

    rotated_count = 0
    errors: list[str] = []

    for key in keys_to_rotate:
        raw_value = get_raw(key)
        if raw_value is None:
            continue
        try:
            new_encrypted = rotate_key(old_key, request.new_master_key, [raw_value])
            re_encrypt_value(key, new_encrypted[0])
            rotated_count += 1
        except Exception as exc:
            errors.append(f"{key}: {exc}")

    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"Rotation partially failed: {'; '.join(errors)}",
        )

    return RotateSecretsResponse(
        status="ok",
        rotated_count=rotated_count,
        message=f"Successfully rotated {rotated_count} secret(s) to the new master key.",
    )
