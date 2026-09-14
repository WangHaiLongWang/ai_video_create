"""Template service — predefined workflow templates."""

from __future__ import annotations

import uuid
from typing import Any

from backend.app.models import WorkflowSpec, TemplateInfo, TemplateDetail


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
}


class TemplateService:
    """模板管理服务。"""

    def __init__(self) -> None:
        self._templates = dict(_BUILTIN_TEMPLATES)
        self._custom_templates: dict[str, dict[str, Any]] = {}

    def list_templates(self) -> list[TemplateInfo]:
        """列出所有模板。"""
        result = []
        for tid, t in self._templates.items():
            result.append(TemplateInfo(
                id=tid, name=t["name"], description=t["description"],
                tags=t.get("tags", []),
                node_count=len(t.get("nodes", [])),
            ))
        for tid, t in self._custom_templates.items():
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

        # 再查自定义模板
        if template_id.startswith("custom:"):
            cid = template_id[7:]
        else:
            cid = template_id
        t = self._custom_templates.get(cid)
        if t:
            spec = WorkflowSpec(
                id=f"template-{cid}",
                name=t["name"],
                nodes=[self._dict_to_node(n) for n in t["nodes"]],
                edges=[self._dict_to_edge(e) for e in t["edges"]],
            )
            return TemplateDetail(
                id=f"custom:{cid}", name=t["name"], description=t["description"],
                tags=t.get("tags", []), spec=spec,
            )

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
        """保存工作流为自定义模板。"""
        tid = uuid.uuid4().hex[:8]
        self._custom_templates[tid] = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "nodes": [self._node_to_dict(n) for n in spec.nodes],
            "edges": [self._edge_to_dict(e) for e in spec.edges],
        }
        return f"custom:{tid}"

    def delete_template(self, template_id: str) -> bool:
        """删除自定义模板。"""
        if template_id.startswith("custom:"):
            cid = template_id[7:]
        else:
            cid = template_id
        if cid in self._custom_templates:
            del self._custom_templates[cid]
            return True
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


# Global instance
_template_service: TemplateService | None = None


def get_template_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service
