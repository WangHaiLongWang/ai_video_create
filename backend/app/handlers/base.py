"""Mock handlers for all node types — Phase B mock pipeline."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any


class MockHandler:
    """Mock 基类：模拟延迟后返回成功。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.3)  # 模拟处理时间
        return {"status": "ok", "task_id": task["id"]}


class TextInputHandler(MockHandler):
    """主题输入节点。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.1)
        prompt = task.get("config", {}).get("prompt", "")
        return {"status": "ok", "output": {"type": "text", "content": prompt}}


class StoryboardHandler(MockHandler):
    """分镜生成节点 — 生成结构化场景列表。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.5)
        scene_count = int(task.get("config", {}).get("scenes", 5))
        style = task.get("config", {}).get("style", "cinematic")
        scenes = []
        for i in range(scene_count):
            scenes.append({
                "scene_id": f"scene-{i + 1:03d}",
                "index": i,
                "narration": f"场景 {i + 1} 的叙述文本",
                "image_prompt": f"场景 {i + 1} 的图像提示词，风格: {style}",
                "video_prompt": f"场景 {i + 1} 的视频提示词",
                "duration_seconds": 4,
            })
        return {"status": "ok", "output": {"type": "list<scene>", "scenes": scenes, "count": scene_count}}


class TextToImageHandler(MockHandler):
    """文生图节点 — 为每个场景生成 mock 图片。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.65)
        scene_id = task.get("item_key", "unknown")
        scene_index = task.get("config", {}).get("scene_index", 0)
        asset_id = f"img-{uuid.uuid4().hex[:8]}"
        return {
            "status": "ok",
            "output": {
                "type": "list<image>",
                "asset_id": asset_id,
                "scene_id": scene_id,
                "path": f"data/assets/{asset_id}.png",
                "width": 1920,
                "height": 1080,
            },
        }


class ImageToVideoHandler(MockHandler):
    """图生视频节点 — 为每张图片生成 mock 视频。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(1.1)
        scene_id = task.get("item_key", "unknown")
        asset_id = f"vid-{uuid.uuid4().hex[:8]}"
        duration = task.get("config", {}).get("duration", 4)
        return {
            "status": "ok",
            "output": {
                "type": "list<video>",
                "asset_id": asset_id,
                "scene_id": scene_id,
                "path": f"data/assets/{asset_id}.mp4",
                "duration_seconds": duration,
            },
        }


class VideoConcatHandler(MockHandler):
    """视频合成节点 — 合并所有视频片段。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.8)
        asset_id = f"final-{uuid.uuid4().hex[:8]}"
        return {
            "status": "ok",
            "output": {
                "type": "video",
                "asset_id": asset_id,
                "path": f"data/assets/{asset_id}.mp4",
                "filename": task.get("config", {}).get("filename", "output.mp4"),
            },
        }


class OutputHandler(MockHandler):
    """成片输出节点。"""

    async def execute(self, task: dict, context: dict) -> dict:
        await asyncio.sleep(0.2)
        return {
            "status": "ok",
            "output": {
                "type": "final",
                "message": "工作流执行完成",
            },
        }
