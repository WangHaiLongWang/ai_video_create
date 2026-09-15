"""FastAPI application entry point."""

import logging
import shutil
import sys
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.executions import router as executions_router
from .api.workflows import router as workflows_router
from .api.config import router as config_router
from .api.agent import router as agent_router
from .api.templates import router as templates_router
from .api.assets import router as assets_router
from .db.connection import close_connection, init_db
from .engine.worker import WorkerPool
from .models import AgentRequest, WorkflowSpec
from .workflow_factory import create_prompt_to_video
from .config import get_settings
from .providers import init_providers
from .handlers import init_handlers
from .services.asset_manager import get_asset_manager
from .middleware import SecurityMiddleware, InputSanitizeMiddleware


_worker_pool: WorkerPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup resources."""
    global _worker_pool

    # Initialize database
    init_db()

    # Load configuration
    settings = get_settings()

    # Initialize providers — 每个能力独立选择 Provider
    from .providers import init_providers as _init_providers
    from .providers.mock_provider import MockProvider
    from .providers.base import ProviderCapabilities

    # 始终注册 Mock Provider（作为 fallback）
    from .providers import register_provider
    register_provider(MockProvider())

    # 根据 LLM Provider 设置注册文本生成 Provider
    if settings.DEFAULT_LLM_PROVIDER == "ollama":
        try:
            from .providers.ollama_provider import OllamaProvider
            register_provider(OllamaProvider(api_url=settings.OLLAMA_API_URL))
        except Exception as e:
            logger.warning(f"Failed to register Ollama provider: {e}")
    elif settings.DEFAULT_LLM_PROVIDER == "openai_compat":
        if settings.OPENAI_COMPAT_API_KEY:
            try:
                from .providers.openai_compat_provider import OpenAICompatProvider
                register_provider(OpenAICompatProvider(
                    api_key=settings.OPENAI_COMPAT_API_KEY,
                    api_url=settings.OPENAI_COMPAT_API_URL,
                    model=settings.OPENAI_COMPAT_MODEL,
                    display_name=settings.OPENAI_COMPAT_NAME,
                    auth_header=settings.OPENAI_COMPAT_AUTH_HEADER,
                    auth_scheme=settings.OPENAI_COMPAT_AUTH_SCHEME,
                    max_tokens_param=settings.OPENAI_COMPAT_MAX_TOKENS_PARAM,
                    default_config={
                        "max_tokens": settings.OPENAI_COMPAT_MAX_TOKENS,
                        "temperature": settings.OPENAI_COMPAT_TEMPERATURE,
                        "top_p": settings.OPENAI_COMPAT_TOP_P,
                        "timeout": settings.OPENAI_COMPAT_TIMEOUT,
                    },
                ))
            except Exception as e:
                logger.warning(f"Failed to register custom LLM provider: {e}")
        else:
            logger.info("Custom LLM selected without an API key; Mock remains available")
    # 根据 Image Provider 设置注册图像生成 Provider
    if settings.DEFAULT_IMAGE_PROVIDER == "comfyui":
        try:
            from .providers.comfyui_provider import ComfyUIProvider
            register_provider(ComfyUIProvider(api_url=settings.COMFYUI_API_URL))
        except Exception as e:
            logger.warning(f"Failed to register ComfyUI provider: {e}")
    elif settings.DEFAULT_IMAGE_PROVIDER == "openai":
        pass
    elif settings.DEFAULT_IMAGE_PROVIDER == "dashscope":
        try:
            from .providers.dashscope_provider import DashScopeProvider
            register_provider(DashScopeProvider(
                api_key=settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY,
                api_url=settings.DASHSCOPE_API_URL,
                image_model=settings.DASHSCOPE_IMAGE_MODEL,
                default_config={
                    "size": settings.DASHSCOPE_IMAGE_SIZE,
                    "use_async": settings.DASHSCOPE_USE_ASYNC,
                    "prompt_extend": settings.DASHSCOPE_PROMPT_EXTEND,
                    "prompt_extend_mode": settings.DASHSCOPE_PROMPT_EXTEND_MODE,
                    "enable_thinking": settings.DASHSCOPE_ENABLE_THINKING,
                    "watermark": settings.DASHSCOPE_WATERMARK,
                },
            ))
        except Exception as e:
            logger.warning(f"Failed to register DashScope provider: {e}")

    # OpenAI-compatible Provider 可能只用于图像能力，必须独立于默认 LLM 注册。
    if (
        settings.DEFAULT_LLM_PROVIDER == "openai"
        or settings.DEFAULT_IMAGE_PROVIDER == "openai"
    ):
        try:
            from .providers.openai_provider import OpenAIProvider
            register_provider(OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                api_url=settings.OPENAI_API_URL,
                model=settings.OPENAI_MODEL,
                image_model=settings.OPENAI_IMAGE_MODEL,
            ))
        except Exception as e:
            logger.warning(f"Failed to register OpenAI-compatible provider: {e}")

    # 根据 Video Provider 设置注册视频生成 Provider
    if settings.DEFAULT_VIDEO_PROVIDER == "comfyui":
        try:
            from .providers.comfyui_provider import ComfyUIProvider
            register_provider(ComfyUIProvider(api_url=settings.COMFYUI_API_URL))
        except Exception as e:
            logger.warning(f"Failed to register ComfyUI video provider: {e}")
    elif settings.DEFAULT_VIDEO_PROVIDER == "wan3":
        try:
            from .providers.wan3_provider import Wan3VideoProvider
            register_provider(Wan3VideoProvider(
                api_key=settings.WAN3_API_KEY or settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY,
                api_url=settings.WAN3_API_URL,
                model=settings.WAN3_MODEL,
                default_config={
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
            ))
        except Exception as e:
            logger.warning(f"Failed to register Wan3 provider: {e}")

    # Real handlers resolve each capability independently and may still use the
    # always-registered Mock Provider for capabilities configured as mock.
    init_handlers(use_mock=False)

    # Initialize asset manager
    get_asset_manager()

    # 启动 Worker 池
    _worker_pool = WorkerPool(
        worker_count=settings.WORKER_COUNT,
        poll_interval=settings.WORKER_POLL_INTERVAL,
        lease_seconds=settings.WORKER_LEASE_SECONDS,
    )
    await _worker_pool.start()

    yield

    # 停止 Worker 池
    if _worker_pool:
        await _worker_pool.stop()
    close_connection()


app = FastAPI(title="ai_video_create API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityMiddleware, rate_limit=200)
app.add_middleware(InputSanitizeMiddleware)

# Include routers
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(config_router)
app.include_router(agent_router)
app.include_router(templates_router)
app.include_router(assets_router)

# Mount static files for serving assets
try:
    asset_manager = get_asset_manager()
    app.mount("/assets", StaticFiles(directory=str(asset_manager.asset_dir)), name="assets")
except Exception:
    pass  # Will fail if directory doesn't exist yet


@app.get("/api/health")
async def health() -> dict[str, object]:
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "ok",
        "python": sys.version.split()[0],
        "ffmpeg": shutil.which(settings.FFMPEG_PATH) is not None,
        "mode": "local",
        "version": "0.2.0",
    }


@app.post("/api/workflows/validate")
async def validate_workflow(workflow: WorkflowSpec) -> dict[str, object]:
    """Validate a workflow specification."""
    return {"valid": True, "nodes": len(workflow.nodes), "edges": len(workflow.edges)}
