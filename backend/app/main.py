import shutil
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import AgentRequest, WorkflowSpec
from .workflow_factory import create_prompt_to_video

app = FastAPI(title="ai_video_create API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

