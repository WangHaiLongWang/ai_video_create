"""Storyboard Materializer — 将 Storyboard NodeResult 转换为 ScenePromptBundle。

职责：
1. 从执行结果中提取场景数据
2. 填充 ScenePromptBundle 结构
3. 生成稳定 scene_id
4. 应用全局样式和负面提示
"""

from __future__ import annotations

from typing import Any

from ..schemas.scene_bundle import (
    SceneEntry,
    SceneImagePrompt,
    ScenePromptBundle,
    SceneVideoPrompt,
)


class MaterializationError(Exception):
    """Materialization error."""
    pass


def _extract_scenes(storyboard_result: dict[str, Any]) -> list[dict[str, Any]]:
    """从 Storyboard 节点结果中提取 scenes 列表。

    支持三种存储格式：
    1. result["output"]["metadata"]["scenes"] — NodeResult 标准格式
    2. result["output"]["scenes"] — legacy 格式
    3. result["scenes"] — 最外层直接存储（兼容）
    """
    # 格式 1: output.metadata.scenes
    output = storyboard_result.get("output", {})
    if isinstance(output, dict):
        meta = output.get("metadata", {})
        if isinstance(meta, dict) and "scenes" in meta:
            return meta["scenes"]

        # 格式 2: output.scenes (legacy)
        if "scenes" in output:
            return output["scenes"]

    # 格式 3: result.scenes (flat)
    if "scenes" in storyboard_result:
        return storyboard_result["scenes"]

    return []


def _build_image_prompt(
    scene_data: dict[str, Any],
    global_style: str,
    negative_prompt: str,
) -> SceneImagePrompt:
    """从场景数据构建 SceneImagePrompt。"""
    prompt_text = scene_data.get("image_prompt", "") or scene_data.get("imagePrompt", "")

    # Apply global style prefix if present
    if global_style and prompt_text:
        prompt_text = f"{prompt_text}, {global_style}"

    neg = scene_data.get("image_negative_prompt") or scene_data.get("imageNegativePrompt")
    if negative_prompt and not neg:
        neg = negative_prompt

    return SceneImagePrompt(
        prompt=prompt_text,
        negative_prompt=neg,
        provider=scene_data.get("image_provider") or scene_data.get("imageProvider"),
        model=scene_data.get("image_model") or scene_data.get("imageModel"),
        size=scene_data.get("image_size") or scene_data.get("imageSize"),
        seed=scene_data.get("image_seed", -1),
    )


def _build_video_prompt(
    scene_data: dict[str, Any],
) -> SceneVideoPrompt:
    """从场景数据构建 SceneVideoPrompt。"""
    prompt_text = scene_data.get("video_prompt", "") or scene_data.get("videoPrompt", "")

    return SceneVideoPrompt(
        prompt=prompt_text,
        provider=scene_data.get("video_provider") or scene_data.get("videoProvider"),
        model=scene_data.get("video_model") or scene_data.get("videoModel"),
        resolution=scene_data.get("video_resolution") or scene_data.get("videoResolution"),
        ratio=scene_data.get("video_ratio") or scene_data.get("videoRatio"),
        duration=int(scene_data.get("duration_seconds", 5)),
        audio=scene_data.get("video_audio", True),
        seed=scene_data.get("video_seed", -1),
    )


def materialize_storyboard(
    storyboard_result: dict[str, Any],
    *,
    workflow_id: str = "",
    execution_id: str = "",
    storyboard_id: str = "",
    title: str = "",
    global_style: str = "",
    negative_prompt: str = "",
) -> ScenePromptBundle:
    """从 Storyboard 节点的执行结果生成 ScenePromptBundle。

    storyboard_result expected format::

        {
            "output": {
                "metadata": {
                    "scenes": [
                        {
                            "scene_id": "scene-001",
                            "index": 0,
                            "narration": "...",
                            "image_prompt": "...",
                            "video_prompt": "...",
                            "duration_seconds": 5.0,
                            "metadata": {}
                        }
                    ]
                }
            }
        }

    Raises:
        MaterializationError: if scenes cannot be extracted
    """
    raw_scenes = _extract_scenes(storyboard_result)

    if not raw_scenes:
        raise MaterializationError(
            "No scenes found in storyboard result. "
            "Expected scenes in output.metadata.scenes, output.scenes, or scenes."
        )

    # Sort by index to ensure ordering
    raw_scenes = sorted(raw_scenes, key=lambda s: s.get("index", 0))

    scenes: list[SceneEntry] = []
    for i, scene_data in enumerate(raw_scenes):
        scene_id = scene_data.get("scene_id") or f"scene-{i + 1:03d}"
        index = scene_data.get("index", i)

        image = _build_image_prompt(scene_data, global_style, negative_prompt)
        video = _build_video_prompt(scene_data)

        entry = SceneEntry(
            scene_id=scene_id,
            index=index,
            title=scene_data.get("title") or f"Scene {index + 1}",
            narration=scene_data.get("narration", ""),
            duration_seconds=float(scene_data.get("duration_seconds", 5.0)),
            locked=False,
            image=image,
            video=video,
            transition=scene_data.get("transition"),
            metadata=scene_data.get("metadata", {}),
        )
        scenes.append(entry)

    effective_title = title or f"Storyboard {storyboard_id or 'Untitled'}"

    return ScenePromptBundle(
        storyboard_id=storyboard_id or "sb-generated",
        workflow_id=workflow_id or "wf-unknown",
        execution_id=execution_id or "ex-unknown",
        title=effective_title,
        global_style=global_style or None,
        negative_prompt=negative_prompt or None,
        scenes=scenes,
        source="execution",
    )
