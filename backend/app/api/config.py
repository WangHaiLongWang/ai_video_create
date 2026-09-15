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
