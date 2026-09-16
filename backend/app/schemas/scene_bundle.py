from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    """Convert snake_case field name to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class SceneImagePrompt(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    prompt: str
    negative_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    size: str | None = None
    seed: int = -1
    reference_asset_ids: list[str] = Field(default_factory=list)


class SceneVideoPrompt(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    prompt: str
    provider: str | None = None
    model: str | None = None
    resolution: str | None = None
    ratio: str | None = None
    duration: int = 5
    audio: bool = True
    seed: int = -1
    first_frame_asset_id: str | None = None


class SceneEntry(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    scene_id: str
    index: int
    title: str
    narration: str
    duration_seconds: float = 5.0
    locked: bool = False
    image: SceneImagePrompt
    video: SceneVideoPrompt
    transition: dict | None = None
    metadata: dict = Field(default_factory=dict)


class ScenePromptBundle(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    schema_version: Literal["1.0"] = "1.0"
    storyboard_id: str
    workflow_id: str
    execution_id: str
    title: str
    global_style: str | None = None
    negative_prompt: str | None = None
    scenes: list[SceneEntry]
    exported_at: str | None = None
    source: Literal['draft', 'execution', 'merged'] | None = None
