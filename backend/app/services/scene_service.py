"""Scene Service — 管理 Scene Draft、Override 和 Lock。

职责：
1. 创建/读取/更新 Scene Draft
2. 应用用户覆盖（override）
3. 锁定/解锁 scene
4. 合并执行结果和用户编辑
"""

from __future__ import annotations

from typing import Any

from ..schemas.scene_bundle import ScenePromptBundle, SceneEntry


class SceneService:
    """管理 Scene Bundle 的 CRUD 和合并逻辑。"""

    def __init__(self) -> None:
        # In-memory store for now (will be backed by SQLite later)
        self._drafts: dict[str, ScenePromptBundle] = {}  # draft_id -> bundle
        self._counter: int = 0

    def create_draft(self, bundle: ScenePromptBundle) -> str:
        """创建草稿，返回 draft_id。"""
        self._counter += 1
        draft_id = f"draft-{self._counter:04d}"
        self._drafts[draft_id] = bundle
        return draft_id

    def get_draft(self, draft_id: str) -> ScenePromptBundle | None:
        """获取草稿。"""
        return self._drafts.get(draft_id)

    def update_scene(self, draft_id: str, scene_index: int, updates: dict[str, Any]) -> bool:
        """更新指定 scene 的字段。"""
        bundle = self._drafts.get(draft_id)
        if not bundle or scene_index < 0 or scene_index >= len(bundle.scenes):
            return False
        scene = bundle.scenes[scene_index]
        for key, value in updates.items():
            if hasattr(scene, key):
                setattr(scene, key, value)
        return True

    def lock_scene(self, draft_id: str, scene_index: int) -> bool:
        """锁定 scene，防止重新生成覆盖。"""
        bundle = self._drafts.get(draft_id)
        if not bundle or scene_index < 0 or scene_index >= len(bundle.scenes):
            return False
        bundle.scenes[scene_index].locked = True
        return True

    def unlock_scene(self, draft_id: str, scene_index: int) -> bool:
        """解锁 scene。"""
        bundle = self._drafts.get(draft_id)
        if not bundle or scene_index < 0 or scene_index >= len(bundle.scenes):
            return False
        bundle.scenes[scene_index].locked = False
        return True

    def merge_execution(self, draft_id: str, execution_bundle: ScenePromptBundle) -> ScenePromptBundle:
        """合并执行结果和用户覆盖。保留 locked scene 的值。"""
        draft = self._drafts.get(draft_id)
        if not draft:
            return execution_bundle

        merged_scenes = []
        for exec_scene in execution_bundle.scenes:
            # Find corresponding draft scene by scene_id
            draft_scene = next(
                (s for s in draft.scenes if s.scene_id == exec_scene.scene_id),
                None,
            )
            if draft_scene and draft_scene.locked:
                # Keep draft version (user edited + locked)
                merged_scenes.append(draft_scene)
            else:
                # Use execution result
                merged_scenes.append(exec_scene)

        execution_bundle.scenes = merged_scenes
        return execution_bundle

    def import_bundle(self, bundle: ScenePromptBundle) -> str:
        """导入外部 bundle 作为新草稿。"""
        return self.create_draft(bundle)

    def list_drafts(self) -> list[dict[str, Any]]:
        """列出所有草稿摘要。"""
        return [
            {
                "id": did,
                "title": b.title,
                "scene_count": len(b.scenes),
                "schema_version": b.schema_version,
            }
            for did, b in self._drafts.items()
        ]
