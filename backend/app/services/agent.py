"""Agent service — LLM-driven workflow generation and modification."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from backend.app.models import (
    WorkflowSpec, WorkflowNode, WorkflowEdge, NodeData, Position,
    GraphPatch, NodeUpdate,
)
from backend.app.providers import get_provider
from backend.app.providers.base import ProviderError

logger = logging.getLogger(__name__)

# 节点类型目录（供 LLM 参考）
NODE_CATALOG = {
    "textInput": {
        "description": "输入提示词，作为工作流的起点",
        "inputType": None,
        "outputType": "text",
        "config_keys": ["prompt"],
    },
    "storyboard": {
        "description": "将文本拆分为多个场景（分镜），每个场景包含叙述、图片提示词、视频提示词",
        "inputType": "text",
        "outputType": "list<scene>",
        "config_keys": ["scenes", "style"],
    },
    "textToImage": {
        "description": "为每个场景生成一张图片（支持 mapOver 展开）",
        "inputType": "list<scene>",
        "outputType": "list<image>",
        "config_keys": ["mapOver"],
    },
    "imageToVideo": {
        "description": "将图片转为视频片段（支持 mapOver 展开）",
        "inputType": "list<image>",
        "outputType": "list<video>",
        "config_keys": ["mapOver", "duration"],
    },
    "videoConcat": {
        "description": "将多个视频片段拼接为一个完整视频",
        "inputType": "list<video>",
        "outputType": "video",
        "config_keys": ["filename"],
    },
    "output": {
        "description": "工作流的终点，输出最终视频",
        "inputType": "video",
        "outputType": None,
        "config_keys": [],
    },
}

# 有效连线规则
VALID_EDGES = {
    ("textInput", "storyboard"),
    ("textInput", "textToImage"),
    ("storyboard", "textToImage"),
    ("textToImage", "imageToVideo"),
    ("imageToVideo", "videoConcat"),
    ("videoConcat", "output"),
}

SYSTEM_PROMPT = f"""你是一个 AI 视频创作工作流助手。你可以帮助用户生成和修改视频创作工作流。

## 可用节点类型

{json.dumps(NODE_CATALOG, ensure_ascii=False, indent=2)}

## 连线规则

- textInput 的输出 (text) → storyboard 或 textToImage 的输入
- storyboard 的输出 (list<scene>) → textToImage 的输入
- textToImage 的输出 (list<image>) → imageToVideo 的输入
- imageToVideo 的输出 (list<video>) → videoConcat 的输入
- videoConcat 的输出 (video) → output 的输入

## 输出格式

请以 JSON 格式输出，包含 "nodes" 和 "edges" 数组。
每个节点需要: id, position(x,y), data(label, description, kind, config)
每条边需要: id, source, target

使用中文回复。"""


class AgentService:
    """LLM 驱动的 Agent 服务。"""

    def __init__(self, provider_name: str | None = None) -> None:
        self._provider_name = provider_name

    def _get_provider(self):
        if self._provider_name:
            return get_provider(self._provider_name)
        from backend.app.config import get_settings
        configured = get_provider(get_settings().DEFAULT_LLM_PROVIDER.value)
        if configured and configured.capabilities.text:
            return configured
        # 按优先级尝试
        for name in ("openai_compat", "openai", "ollama", "mock"):
            p = get_provider(name)
            if p:
                return p
        return None

    async def generate_from_prompt(self, prompt: str, config: dict | None = None) -> WorkflowSpec:
        """从自然语言生成完整工作流。

        Args:
            prompt: 用户描述（中文）
            config: 可选配置（scenes, style 等）

        Returns:
            生成的 WorkflowSpec
        """
        config = config or {}
        provider = self._get_provider()

        if not provider or not provider.capabilities.text:
            logger.warning("No text provider available, using template fallback")
            return self._template_fallback(prompt, config)

        user_message = f"""请根据以下描述生成一个视频创作工作流：

"{prompt}"

要求：
- 场景数量：{config.get('scenes', 5)}
- 风格：{config.get('style', 'cinematic')}
- 生成一个完整的线性工作流
- 每个节点设置合理的 position（从左到右，间距 250）"""

        try:
            response_text = await provider.generate_text(
                SYSTEM_PROMPT + "\n\n" + user_message,
                {"temperature": 0.7, "max_tokens": 4096},
            )

            return self._parse_workflow_response(response_text, prompt)

        except ProviderError as e:
            logger.error(f"Agent generation failed: {e}")
            return self._template_fallback(prompt, config)

    async def modify_workflow(
        self, spec: WorkflowSpec, instruction: str
    ) -> GraphPatch:
        """修改现有工作流。

        Args:
            spec: 当前工作流
            instruction: 修改指令

        Returns:
            GraphPatch（待用户确认）
        """
        provider = self._get_provider()

        if not provider or not provider.capabilities.text:
            return self._simple_patch_fallback(spec, instruction)

        # 序列化当前工作流为文本
        workflow_text = self._serialize_workflow_for_llm(spec)

        modify_prompt = f"""当前工作流：
{workflow_text}

用户指令：{instruction}

请生成一个 GraphPatch JSON，包含以下字段：
- description: 修改描述
- add_nodes: 新增节点列表（如有）
- remove_nodes: 删除的节点 ID 列表（如有）
- update_nodes: 更新节点列表（id + 新 config）
- add_edges: 新增边列表（如有）
- remove_edges: 删除的边 ID 列表（如有）

只返回 JSON，不要其他文字。"""

        try:
            response_text = await provider.generate_text(modify_prompt, {"temperature": 0.3})
            return self._parse_patch_response(response_text)

        except ProviderError as e:
            logger.error(f"Agent modification failed: {e}")
            return self._simple_patch_fallback(spec, instruction)

    async def explain_workflow(self, spec: WorkflowSpec) -> str:
        """解释工作流功能。"""
        provider = self._get_provider()

        workflow_text = self._serialize_workflow_for_llm(spec)

        explain_prompt = f"""请解释以下视频创作工作流的功能和流程：

{workflow_text}

用简洁的中文说明：
1. 这个工作流做什么
2. 经过哪些步骤
3. 最终产出什么"""

        if provider and provider.capabilities.text:
            try:
                return await provider.generate_text(explain_prompt, {"temperature": 0.3})
            except ProviderError:
                pass

        # Fallback: 简单描述
        steps = []
        for node in spec.nodes:
            steps.append(f"{node.data.label} ({node.data.kind})")
        return f"这个工作流包含 {len(spec.nodes)} 个步骤：{' → '.join(steps)}"

    def _parse_workflow_response(self, text: str, prompt: str) -> WorkflowSpec:
        """解析 LLM 响应为 WorkflowSpec。"""
        try:
            # 提取 JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            nodes = [self._dict_to_node(n) for n in data.get("nodes", [])]
            edges = [self._dict_to_edge(e) for e in data.get("edges", [])]

            if not nodes:
                raise ValueError("No nodes in response")

            return WorkflowSpec(
                id=f"wf-{uuid.uuid4().hex[:8]}",
                name=prompt[:30] or "Generated Workflow",
                nodes=nodes,
                edges=edges,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse workflow response: {e}")
            return self._template_fallback(prompt, {})

    def _parse_patch_response(self, text: str) -> GraphPatch:
        """解析 LLM 响应为 GraphPatch。"""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            return GraphPatch(
                description=data.get("description", ""),
                add_nodes=[self._dict_to_node(n) for n in data.get("add_nodes", [])],
                remove_nodes=data.get("remove_nodes", []),
                update_nodes=[NodeUpdate(**u) for u in data.get("update_nodes", [])],
                add_edges=[self._dict_to_edge(e) for e in data.get("add_edges", [])],
                remove_edges=data.get("remove_edges", []),
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse patch response: {e}")
            return GraphPatch(description="解析失败，未应用修改")

    def _serialize_workflow_for_llm(self, spec: WorkflowSpec) -> str:
        """将工作流序列化为 LLM 可读文本。"""
        lines = [f"名称: {spec.name}", f"节点数: {len(spec.nodes)}", ""]
        for node in spec.nodes:
            config_str = json.dumps(node.data.config, ensure_ascii=False)
            lines.append(
                f"节点 [{node.id}] {node.data.label}\n"
                f"  类型: {node.data.kind}\n"
                f"  输入: {node.data.inputType} → 输出: {node.data.outputType}\n"
                f"  配置: {config_str}"
            )
        lines.append("")
        lines.append("连线:")
        for edge in spec.edges:
            lines.append(f"  {edge.source} → {edge.target}")
        return "\n".join(lines)

    def _template_fallback(self, prompt: str, config: dict) -> WorkflowSpec:
        """模板降级方案 — 解析 prompt 中的场景数并应用。"""
        import re
        # 从 prompt 中提取场景数
        match = re.search(r"(\d+)\s*镜头", prompt)
        scene_count = max(1, min(int(match.group(1)) if match else config.get("scenes", 5), 20))

        from backend.app.services.templates import get_template_service
        tmpl = get_template_service().create_from_template("prompt-to-video", {
            "name": prompt[:30],
            "prompt": prompt,
        })
        if tmpl:
            # 更新 storyboard 节点的 scenes 配置
            for node in tmpl.nodes:
                if node.data.kind == "storyboard":
                    node.data.config["scenes"] = scene_count
            return tmpl
        # 最终降级
        return WorkflowSpec(
            id=f"wf-{uuid.uuid4().hex[:8]}",
            name=prompt[:30] or "Untitled",
            nodes=[], edges=[],
        )

    def _simple_patch_fallback(self, spec: WorkflowSpec, instruction: str) -> GraphPatch:
        """简单 patch 降级。"""
        return GraphPatch(description=f"无法处理指令: {instruction}")

    @staticmethod
    def _dict_to_node(d: dict) -> WorkflowNode:
        return WorkflowNode(
            id=d["id"],
            type=d.get("type", "studio"),
            position=Position(x=d.get("position", {}).get("x", 0), y=d.get("position", {}).get("y", 0)),
            data=NodeData(**d["data"]),
        )

    @staticmethod
    def _dict_to_edge(d: dict) -> WorkflowEdge:
        return WorkflowEdge(**d)


# Global instance
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
