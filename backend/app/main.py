"""FastAPI application entry point."""

import shutil
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.executions import router as executions_router, start_worker_background, stop_worker_background
from .api.workflows import router as workflows_router
from .api.config import router as config_router
from .api.agent import router as agent_router
from .api.templates import router as templates_router
from .db.connection import close_connection, init_db
from .models import AgentRequest, WorkflowSpec
from .workflow_factory import create_prompt_to_video
from .config import get_settings
from .providers import init_providers
from .handlers import init_handlers
from .services.asset_manager import get_asset_manager
from .middleware import SecurityMiddleware, InputSanitizeMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup resources."""
    # Initialize database
    init_db()

    # Load configuration
    settings = get_settings()

    # Initialize providers
    init_providers(
        mock=(settings.DEFAULT_LLM_PROVIDER.value == "mock"),
        ollama_url=settings.OLLAMA_API_URL if settings.DEFAULT_LLM_PROVIDER.value == "ollama" else None,
        openai_key=settings.OPENAI_API_KEY if settings.DEFAULT_LLM_PROVIDER.value == "openai" else None,
        comfyui_url=settings.COMFYUI_API_URL if settings.DEFAULT_IMAGE_PROVIDER.value == "comfyui" else None,
    )

    # Initialize handlers (mock or real based on config)
    use_mock = (settings.DEFAULT_LLM_PROVIDER.value == "mock")
    init_handlers(use_mock=use_mock)

    # Initialize asset manager
    get_asset_manager()

    # Start background worker
    await start_worker_background()

    yield

    # Cleanup
    await stop_worker_background()
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
