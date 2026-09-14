import shutil
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.executions import router as executions_router, start_worker_background, stop_worker_background
from .api.workflows import router as workflows_router
from .db.connection import close_connection, init_db
from .models import AgentRequest, WorkflowSpec
from .workflow_factory import create_prompt_to_video


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await start_worker_background()
    yield
    await stop_worker_background()
    close_connection()


app = FastAPI(title="ai_video_create API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows_router)
app.include_router(executions_router)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "python": sys.version.split()[0],
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "mode": "local",
    }


@app.post("/api/workflows/validate")
async def validate_workflow(workflow: WorkflowSpec) -> dict[str, object]:
    return {"valid": True, "nodes": len(workflow.nodes), "edges": len(workflow.edges)}


@app.post("/api/agent/generate", response_model=WorkflowSpec)
async def generate_workflow(request: AgentRequest) -> WorkflowSpec:
    return create_prompt_to_video(request.prompt)
