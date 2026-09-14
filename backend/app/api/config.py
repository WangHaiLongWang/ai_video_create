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
    openai_model: str
    openai_image_model: str
    comfyui_api_url: str
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
    openai_model: str | None = None
    openai_image_model: str | None = None
    comfyui_api_url: str | None = None


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
        openai_model=settings.OPENAI_MODEL,
        openai_image_model=settings.OPENAI_IMAGE_MODEL,
        comfyui_api_url=settings.COMFYUI_API_URL,
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
    if request.openai_model:
        settings.OPENAI_MODEL = request.openai_model
    if request.openai_image_model:
        settings.OPENAI_IMAGE_MODEL = request.openai_image_model
    if request.comfyui_api_url:
        settings.COMFYUI_API_URL = request.comfyui_api_url

    # Reinitialize providers
    clear_providers()
    init_providers(
        mock=(settings.DEFAULT_LLM_PROVIDER.value == "mock"),
        ollama_url=settings.OLLAMA_API_URL if settings.DEFAULT_LLM_PROVIDER.value == "ollama" else None,
        openai_key=settings.OPENAI_API_KEY if settings.DEFAULT_LLM_PROVIDER.value == "openai" else None,
        comfyui_url=settings.COMFYUI_API_URL if settings.DEFAULT_IMAGE_PROVIDER.value == "comfyui" else None,
    )

    # Reinitialize handlers
    use_mock = (settings.DEFAULT_LLM_PROVIDER.value == "mock")
    init_handlers(use_mock=use_mock)

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
