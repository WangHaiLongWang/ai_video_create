"""Storyboard Materializer — 将 Storyboard NodeResult 转换为 ScenePromptBundle。

职责：
1. 从执行结果中提取场景数据
2. 填充 ScenePromptBundle 结构
3. 生成稳定 scene_id
4. 应用全局样式和负面提示

scene_id 稳定性保证：
- 如果输入场景自带 scene_id 字段，原样保留（同一输入 → 同一 scene_id）
- 如果输入场景没有 scene_id，按其在输入列表中的位置生成确定性 ID（scene-001, scene-002, ...）
- 多次调用 materialize_storyboard 对相同输入会产生相同的 scene_id
"""

from __future__ import annotations

import hashlib
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


def compute_deterministic_scene_id(scene_data: dict[str, Any], position: int) -> str:
    """为没有 scene_id 的场景生成确定性 ID。

    基于场景核心内容（narration + image_prompt + video_prompt）和位置
    生成稳定的 scene_id，确保相同输入总是产生相同的 ID。

    Args:
        scene_data: 场景原始数据字典
        position: 场景在输入列表中的位置（0-based）

    Returns:
        格式为 "scene-XXXXXXXX" 的确定性 scene_id
    """
    # 如果场景自带 scene_id，直接返回（不应调用此函数，但安全回退）
    if scene_data.get("scene_id"):
        return scene_data["scene_id"]

    # 构建决定性 key：核心内容 + 位置
    key_parts = [
        str(scene_data.get("narration", "")),
        str(scene_data.get("image_prompt", "")),
        str(scene_data.get("video_prompt", "")),
        str(position),
    ]
    raw_key = "|".join(key_parts)
    hash_val = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:8]
    return f"scene-{hash_val}"


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
    allow_empty: bool = True,
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

    Args:
        storyboard_result: Storyboard 节点的执行结果字典
        workflow_id: 工作流 ID
        execution_id: 执行 ID
        storyboard_id: 故事板 ID
        title: 故事板标题
        global_style: 全局样式前缀，将追加到每个场景的 image_prompt
        negative_prompt: 全局负面提示
        allow_empty: 如果为 True，空场景列表返回有效空 bundle；
                     如果为 False，空场景列表抛出 MaterializationError

    Returns:
        ScenePromptBundle — 包含所有场景的完整 bundle

    Raises:
        MaterializationError: 当 allow_empty=False 且无法提取场景时
    """
    raw_scenes = _extract_scenes(storyboard_result)

    if not raw_scenes:
        if allow_empty:
            effective_title = title or f"Storyboard {storyboard_id or 'Untitled'}"
            return ScenePromptBundle(
                storyboard_id=storyboard_id or "sb-generated",
                workflow_id=workflow_id or "wf-unknown",
                execution_id=execution_id or "ex-unknown",
                title=effective_title,
                global_style=global_style or None,
                negative_prompt=negative_prompt or None,
                scenes=[],
                source="execution",
            )
        raise MaterializationError(
            "No scenes found in storyboard result. "
            "Expected scenes in output.metadata.scenes, output.scenes, or scenes."
        )

    # Sort by index to ensure ordering
    raw_scenes = sorted(raw_scenes, key=lambda s: s.get("index", 0))

    scenes: list[SceneEntry] = []
    for i, scene_data in enumerate(raw_scenes):
        # 确定 scene_id：优先使用输入自带的，否则生成确定性 ID
        scene_id = scene_data.get("scene_id")
        if not scene_id:
            scene_id = compute_deterministic_scene_id(scene_data, i)

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
