"""Template service — predefined workflow templates with SQLite persistence."""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.models import WorkflowSpec, TemplateInfo, TemplateDetail
from backend.app.db.connection import get_connection


# --- Built-in Templates ---

_BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "prompt-to-video": {
        "name": "提示词生成视频",
        "description": "从文字描述生成完整视频：提示词 → 分镜 → 图片 → 视频 → 合成",
        "tags": ["视频", "生成", "完整流程"],
        "nodes": [
            {"id": "n1", "type": "studio", "position": {"x": 100, "y": 200},
             "data": {"label": "输入提示词", "description": "视频主题描述", "kind": "textInput",
                      "inputType": None, "outputType": "text", "config": {"prompt": ""}}},
            {"id": "n2", "type": "studio", "position": {"x": 350, "y": 200},
             "data": {"label": "生成分镜", "description": "将提示词拆分为多个场景", "kind": "storyboard",
                      "inputType": "text", "outputType": "list<scene>", "config": {"scenes": 5, "style": "cinematic"}}},
            {"id": "n3", "type": "studio", "position": {"x": 600, "y": 200},
             "data": {"label": "生成图片", "description": "为每个场景生成图片", "kind": "textToImage",
                      "inputType": "list<scene>", "outputType": "list<image>", "config": {"mapOver": True}}},
            {"id": "n4", "type": "studio", "position": {"x": 850, "y": 200},
             "data": {"label": "图片转视频", "description": "将图片转为视频片段", "kind": "imageToVideo",
                      "inputType": "list<image>", "outputType": "list<video>", "config": {"mapOver": True, "duration": 4}}},
            {"id": "n5", "type": "studio", "position": {"x": 1100, "y": 200},
             "data": {"label": "合成视频", "description": "拼接所有视频片段", "kind": "videoConcat",
                      "inputType": "list<video>", "outputType": "video", "config": {}}},
            {"id": "n6", "type": "studio", "position": {"x": 1350, "y": 200},
             "data": {"label": "输出", "description": "最终视频输出", "kind": "output",
                      "inputType": "video", "outputType": None, "config": {}}},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "type": "smoothstep"},
            {"id": "e2-3", "source": "n2", "target": "n3", "type": "smoothstep"},
            {"id": "e3-4", "source": "n3", "target": "n4", "type": "smoothstep"},
            {"id": "e4-5", "source": "n4", "target": "n5", "type": "smoothstep"},
            {"id": "e5-6", "source": "n5", "target": "n6", "type": "smoothstep"},
        ],
    },
    "image-storyboard": {
        "name": "图片故事板",
        "description": "生成图片故事板（无视频合成）",
        "tags": ["图片", "故事板"],
        "nodes": [
            {"id": "n1", "type": "studio", "position": {"x": 100, "y": 200},
             "data": {"label": "输入提示词", "description": "故事主题", "kind": "textInput",
                      "inputType": None, "outputType": "text", "config": {"prompt": ""}}},
            {"id": "n2", "type": "studio", "position": {"x": 350, "y": 200},
             "data": {"label": "生成分镜", "description": "拆分场景", "kind": "storyboard",
                      "inputType": "text", "outputType": "list<scene>", "config": {"scenes": 6, "style": "illustration"}}},
            {"id": "n3", "type": "studio", "position": {"x": 600, "y": 200},
             "data": {"label": "生成图片", "description": "生成插画", "kind": "textToImage",
                      "inputType": "list<scene>", "outputType": "list<image>", "config": {"mapOver": True}}},
            {"id": "n4", "type": "studio", "position": {"x": 850, "y": 200},
             "data": {"label": "输出", "description": "图片集", "kind": "output",
                      "inputType": "list<image>", "outputType": None, "config": {}}},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "type": "smoothstep"},
            {"id": "e2-3", "source": "n2", "target": "n3", "type": "smoothstep"},
            {"id": "e3-4", "source": "n3", "target": "n4", "type": "smoothstep"},
        ],
    },
    "quick-video": {
        "name": "快速视频",
        "description": "最简视频生成（跳过分镜，直接图转视频）",
        "tags": ["视频", "快速"],
        "nodes": [
            {"id": "n1", "type": "studio", "position": {"x": 100, "y": 200},
             "data": {"label": "输入提示词", "description": "视频描述", "kind": "textInput",
                      "inputType": None, "outputType": "text", "config": {"prompt": ""}}},
            {"id": "n2", "type": "studio", "position": {"x": 350, "y": 200},
             "data": {"label": "生成图片", "description": "生成关键帧", "kind": "textToImage",
                      "inputType": "text", "outputType": "list<image>", "config": {}}},
            {"id": "n3", "type": "studio", "position": {"x": 600, "y": 200},
             "data": {"label": "图片转视频", "description": "生成视频", "kind": "imageToVideo",
                      "inputType": "list<image>", "outputType": "list<video>", "config": {"mapOver": True, "duration": 4}}},
            {"id": "n4", "type": "studio", "position": {"x": 850, "y": 200},
             "data": {"label": "合成视频", "description": "拼接", "kind": "videoConcat",
                      "inputType": "list<video>", "outputType": "video", "config": {}}},
            {"id": "n5", "type": "studio", "position": {"x": 1100, "y": 200},
             "data": {"label": "输出", "description": "最终视频", "kind": "output",
                      "inputType": "video", "outputType": None, "config": {}}},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "type": "smoothstep"},
            {"id": "e2-3", "source": "n2", "target": "n3", "type": "smoothstep"},
            {"id": "e3-4", "source": "n3", "target": "n4", "type": "smoothstep"},
            {"id": "e4-5", "source": "n4", "target": "n5", "type": "smoothstep"},
        ],
    },
    "realistic-ski-lesson": {
        "name": "写实滑雪教学",
        "description": "冬季单板滑雪教学：1 Scene → 2 图片变体 → 2 × 3s 视频 → 合成约 6s 成片",
        "tags": ["滑雪", "教学", "写实", "变体"],
        "nodes": [
            {"id": "n1", "type": "studio", "position": {"x": 100, "y": 200},
             "data": {"label": "教学描述", "description": "滑雪教学场景描述", "kind": "textInput",
                      "inputType": None, "outputType": "text",
                      "config": {"prompt": ""}}},
            {"id": "n2", "type": "studio", "position": {"x": 350, "y": 200},
             "data": {"label": "分镜生成", "description": "生成 1 个教学场景", "kind": "storyboard",
                      "inputType": "text", "outputType": "list<scene>",
                      "config": {
                          "scenes": 1,
                          "style": "写实电影感",
                          "globalStyle": (
                              "写实电影感，晴朗冬季白天，低机位35mm，自然光，浅景深，"
                              "4K冬季运动摄影"
                          ),
                          "globalNegativePrompt": (
                              "第三个人，背景人物，人群，双板滑雪，错误固定器，"
                              "肢体畸形，文字，水印，卡通，插画"
                          ),
                          "scenes_data": [
                              {
                                  "scene_id": "scene-001",
                                  "narration": "教练讲解前脚固定、后脚自由的单脚蹬行准备姿势。",
                                  "duration_seconds": 3,
                                  "image_prompt": (
                                      "写实电影感冬季单板滑雪教学照片，晴朗白天，平缓的初级雪道。"
                                      "画面严格只有两个人，背景没有任何其他人物。\n\n"
                                      "左侧是一位单板滑雪教练，双脚都固定在同一块单板滑雪板的固定器中，"
                                      "保持稳定半蹲姿势，一只手向前伸出，手指明确指向右侧学员的前脚固定器，"
                                      "神态专注耐心，正在讲解如何单脚蹬行。\n\n"
                                      "右侧是一位初学者学员，站在自己的单板滑雪板上，仅前脚固定在前脚固定器内，"
                                      "后脚完全未固定并踩在雪地上准备蹬行；膝盖微屈，身体侧向，视线看向前方，"
                                      "板头清晰指向预定滑行方向。两人的滑雪板彼此独立，装备结构合理，"
                                      "肢体与固定器关系清晰准确。\n\n"
                                      "雪面有真实滑痕和轻微飞溅雪粒，远处雪山与缆车自然虚化。"
                                      "中景，低机位，35mm 镜头，浅景深，自然阳光，真实雪地反射，"
                                      "电影级色彩，4K，超写实，高细节，专业冬季运动摄影，"
                                      "清晰准确的人体比例、手脚和单板固定器。"
                                  ),
                                  "negative_prompt": (
                                      "第三个人，背景人物，人群，其他滑雪者，多余人物，双板滑雪，"
                                      "滑雪杖，两人共用一块单板，学员双脚都固定，学员后脚固定在板上，"
                                      "教练脚未固定，错误固定器，额外的腿，额外的手，多余手指，"
                                      "肢体融合，手指方向错误，板头方向错误，单板断裂，装备漂浮，"
                                      "错误透视，卡通，插画，CG 感，低清晰度，模糊，过曝，"
                                      "文字，标志，水印"
                                  ),
                                  "video_prompt": (
                                      "保持首帧中的两个人、左右位置、服装、单板和固定器结构完全一致。"
                                      "镜头进行非常轻微、平稳的低机位前推。"
                                      "左侧教练保持半蹲，一只手继续指向学员前脚固定器并做小幅自然讲解手势；"
                                      "右侧学员前脚保持固定、后脚保持自由并在雪地上轻轻蹬行一次，"
                                      "膝盖微屈，板头持续朝向滑行方向。"
                                      "雪面产生少量真实雪粒，远处雪山与缆车保持虚化。"
                                      "不要新增人物，不要切镜，不要改变装备，不要让后脚自动固定，"
                                      "不要改变为双板滑雪。写实电影感，自然日光，运动摄影，时长 3 秒。"
                                  ),
                                  "metadata": {
                                      "variantCount": 2,
                                      "peopleCount": 2,
                                      "backgroundPeopleAllowed": False,
                                  },
                              },
                          ],
                      }}},
            {"id": "n3", "type": "studio", "position": {"x": 600, "y": 200},
             "data": {"label": "生成图片（双变体）", "description": "每个场景生成 2 张变体图片",
                      "kind": "textToImage",
                      "inputType": "list<scene>", "outputType": "list<image>",
                      "config": {
                          "mapOver": True,
                          "variantCount": 2,
                          "variants": [
                              {"id": "variant-01",
                               "promptSuffix": "略偏教练方向的低机位三分之四侧视角，突出教练指向固定器的手势"},
                              {"id": "variant-02",
                               "promptSuffix": "低机位略宽中景，学员单脚蹬行准备姿态更清晰，雪粒略有动态"},
                          ],
                          "size": "1280x720",
                      }}},
            {"id": "n4", "type": "studio", "position": {"x": 850, "y": 200},
             "data": {"label": "图片转视频", "description": "每张图片生成 3 秒视频",
                      "kind": "imageToVideo",
                      "inputType": "list<image>", "outputType": "list<video>",
                      "config": {"mapOver": True, "variantCount": 2, "duration": 3, "resolution": "480P"}}},
            {"id": "n5", "type": "studio", "position": {"x": 1100, "y": 200},
             "data": {"label": "合成视频", "description": "按变体顺序拼接", "kind": "videoConcat",
                      "inputType": "list<video>", "outputType": "video",
                      "config": {"filename": "ski-lesson-final.mp4"}}},
            {"id": "n6", "type": "studio", "position": {"x": 1350, "y": 200},
             "data": {"label": "输出", "description": "最终视频输出", "kind": "output",
                      "inputType": "video", "outputType": None, "config": {}}},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "type": "smoothstep",
             "sourceHandle": "text", "targetHandle": "prompt"},
            {"id": "e2-3", "source": "n2", "target": "n3", "type": "smoothstep",
             "sourceHandle": "scenes", "targetHandle": "scene",
             "data": {"mode": "map", "itemKey": "scene_id"}},
            {"id": "e3-4", "source": "n3", "target": "n4", "type": "smoothstep",
             "sourceHandle": "images", "targetHandle": "image",
             "data": {"mode": "map", "itemKey": "scene_id::variant_id"}},
            {"id": "e4-5", "source": "n4", "target": "n5", "type": "smoothstep",
             "sourceHandle": "videos", "targetHandle": "videos",
             "data": {"mode": "aggregate", "order": "variant_index"}},
            {"id": "e5-6", "source": "n5", "target": "n6", "type": "smoothstep",
             "sourceHandle": "video", "targetHandle": "video"},
        ],
    },
}


class TemplateService:
    """模板管理服务 — 内置模板 + SQLite 持久化自定义模板。"""

    def __init__(self) -> None:
        self._templates = dict(_BUILTIN_TEMPLATES)

    def _load_custom_templates(self) -> dict[str, dict[str, Any]]:
        """从数据库加载自定义模板。"""
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, name, description, tags, spec_json FROM templates WHERE is_builtin = 0"
            ).fetchall()
            result = {}
            for row in rows:
                spec = json.loads(row["spec_json"])
                result[row["id"]] = {
                    "name": row["name"],
                    "description": row["description"],
                    "tags": json.loads(row["tags"]),
                    "nodes": spec.get("nodes", []),
                    "edges": spec.get("edges", []),
                }
            return result
        except Exception:
            return {}

    def list_templates(self) -> list[TemplateInfo]:
        """列出所有模板。"""
        result = []
        # 内置模板
        for tid, t in self._templates.items():
            result.append(TemplateInfo(
                id=tid, name=t["name"], description=t["description"],
                tags=t.get("tags", []),
                node_count=len(t.get("nodes", [])),
            ))
        # 自定义模板（从数据库加载）
        custom = self._load_custom_templates()
        for tid, t in custom.items():
            result.append(TemplateInfo(
                id=f"custom:{tid}", name=t["name"], description=t["description"],
                tags=t.get("tags", []),
                node_count=len(t.get("nodes", [])),
            ))
        return result

    def get_template(self, template_id: str) -> TemplateDetail | None:
        """获取模板详情。"""
        # 先查内置模板
        t = self._templates.get(template_id)
        if t:
            spec = WorkflowSpec(
                id=f"template-{template_id}",
                name=t["name"],
                nodes=[self._dict_to_node(n) for n in t["nodes"]],
                edges=[self._dict_to_edge(e) for e in t["edges"]],
            )
            return TemplateDetail(
                id=template_id, name=t["name"], description=t["description"],
                tags=t.get("tags", []), spec=spec,
            )

        # 再查自定义模板（从数据库）
        if template_id.startswith("custom:"):
            cid = template_id[7:]
        else:
            cid = template_id

        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT name, description, tags, spec_json FROM templates WHERE id = ?",
                (cid,),
            ).fetchone()
            if row:
                spec_dict = json.loads(row["spec_json"])
                spec = WorkflowSpec(
                    id=f"template-{cid}",
                    name=spec_dict.get("name", row["name"]),
                    nodes=[self._dict_to_node(n) for n in spec_dict.get("nodes", [])],
                    edges=[self._dict_to_edge(e) for e in spec_dict.get("edges", [])],
                )
                return TemplateDetail(
                    id=f"custom:{cid}", name=row["name"], description=row["description"],
                    tags=json.loads(row["tags"]), spec=spec,
                )
        except Exception:
            pass

        return None

    def create_from_template(self, template_id: str, params: dict | None = None) -> WorkflowSpec | None:
        """从模板创建工作流。"""
        detail = self.get_template(template_id)
        if not detail:
            return None

        spec = detail.spec
        # 创建新实例（新 ID）
        new_spec = WorkflowSpec(
            id=f"wf-{uuid.uuid4().hex[:8]}",
            name=params.get("name", spec.name) if params else spec.name,
            nodes=spec.nodes,
            edges=spec.edges,
        )

        # 应用参数（如填充 prompt）
        if params and "prompt" in params:
            for node in new_spec.nodes:
                if node.data.kind == "textInput":
                    node.data.config["prompt"] = params["prompt"]

        return new_spec

    def save_as_template(
        self, spec: WorkflowSpec, name: str, description: str = "", tags: list[str] | None = None
    ) -> str:
        """保存工作流为自定义模板（持久化到 SQLite）。"""
        tid = uuid.uuid4().hex[:8]
        now = _now_iso()

        spec_dict = {
            "name": spec.name,
            "nodes": [self._node_to_dict(n) for n in spec.nodes],
            "edges": [self._edge_to_dict(e) for e in spec.edges],
        }

        try:
            conn = get_connection()
            conn.execute(
                "INSERT INTO templates (id, name, description, tags, spec_json, is_builtin, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (tid, name, description, json.dumps(tags or [], ensure_ascii=False),
                 json.dumps(spec_dict, ensure_ascii=False), now, now),
            )
            conn.commit()
        except Exception:
            # 如果数据库不可用，回退到内存存储
            pass

        return f"custom:{tid}"

    def delete_template(self, template_id: str) -> bool:
        """删除自定义模板。"""
        if template_id.startswith("custom:"):
            cid = template_id[7:]
        else:
            cid = template_id

        try:
            conn = get_connection()
            cursor = conn.execute("DELETE FROM templates WHERE id = ? AND is_builtin = 0", (cid,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    @staticmethod
    def _dict_to_node(d: dict) -> "WorkflowNode":
        from backend.app.models import WorkflowNode, NodeData, Position
        return WorkflowNode(
            id=d["id"],
            type=d.get("type", "studio"),
            position=Position(**d["position"]),
            data=NodeData(**d["data"]),
        )

    @staticmethod
    def _dict_to_edge(d: dict) -> "WorkflowEdge":
        from backend.app.models import WorkflowEdge
        return WorkflowEdge(**d)

    @staticmethod
    def _node_to_dict(node: "WorkflowNode") -> dict:
        return {
            "id": node.id,
            "type": node.type,
            "position": {"x": node.position.x, "y": node.position.y},
            "data": {
                "label": node.data.label,
                "description": node.data.description,
                "kind": node.data.kind,
                "inputType": node.data.inputType,
                "outputType": node.data.outputType,
                "status": node.data.status,
                "config": node.data.config,
            },
        }

    @staticmethod
    def _edge_to_dict(edge: "WorkflowEdge") -> dict:
        return {"id": edge.id, "source": edge.source, "target": edge.target, "type": edge.type}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Global instance
_template_service: TemplateService | None = None


def get_template_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service
