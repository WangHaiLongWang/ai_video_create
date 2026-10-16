"""Structured WorkflowIntent parser using MiMo.

Reads a user prompt and generates a structured WorkflowIntent by calling
MiMo with a carefully crafted system prompt.  Falls back to the template
workflow when MiMo is unavailable or returns invalid JSON.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)
from backend.app.services import agent_trace
from backend.app.schemas.node_catalog import load_node_catalog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chinese numeral mapping
# ---------------------------------------------------------------------------

_CN_NUM_MAP = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1,
    "二": 2, "两": 2, "贰": 2,
    "三": 3, "叁": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陆": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
}


def _parse_cn_number(text: str) -> int | None:
    """Parse a Chinese numeral string into an integer.

    Supports simple cases like: 两, 三, 十, 十二, 二十, 二十三, 百.
    Returns None if parsing fails.
    """
    text = text.strip()
    if not text:
        return None

    # Fast path: pure Arabic digits
    if text.isdigit():
        return int(text)

    # Simple single character
    if text in _CN_NUM_MAP:
        return _CN_NUM_MAP[text]

    # Compound: e.g. 十二, 二十, 二十三
    result = 0
    current = 0
    for ch in text:
        if ch in _CN_NUM_MAP:
            val = _CN_NUM_MAP[ch]
            if val == 10:
                if current == 0:
                    current = 1
                result += current * 10
                current = 0
            elif val == 100:
                if current == 0:
                    current = 1
                result += current * 100
                current = 0
            else:
                current = val
        else:
            return None
    result += current
    return result if result > 0 else None


def _parse_unicode_number(text: str) -> int | None:
    """Parse the common Chinese numerals used in real workflow prompts."""
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3,
              "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text in digits:
        return digits[text]
    total = 0
    current = 0
    for char in text:
        if char in digits:
            current = digits[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    total += current
    return total or None


# ---------------------------------------------------------------------------
# Available node kinds and port definitions (from the unified manifest)
# ---------------------------------------------------------------------------

_SHARED_CATALOG = load_node_catalog()
NODE_KINDS = list(_SHARED_CATALOG)
PORT_DEFINITIONS = {
    kind: {
        "input": [port.id for port in manifest.ports.inputs],
        "output": [port.id for port in manifest.ports.outputs],
    }
    for kind, manifest in _SHARED_CATALOG.items()
}


def _catalog_prompt_section() -> str:
    lines = ["## 可用节点类型", ""]
    for manifest in _SHARED_CATALOG.values():
        lines.append(f"- {manifest.kind}: {manifest.description or manifest.label}")
    lines.extend(["", "## 端口定义", ""])
    for kind, manifest in _SHARED_CATALOG.items():
        inputs = ", ".join(port.id for port in manifest.ports.inputs) or "none"
        outputs = ", ".join(port.id for port in manifest.ports.outputs) or "none"
        lines.append(f"- {kind}: input ports: {inputs}, output ports: {outputs}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# System prompt for MiMo
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是一个视频创作工作流意图解析器。你的任务是将用户的自然语言描述解析为一个结构化的 WorkflowIntent JSON。

## 连线规则

- textInput.text -> storyboard.prompt
- storyboard.scenes -> textToImage.scene (mode: "map")
- textToImage.image -> imageToVideo.image (mode: "map")
- imageToVideo.video -> videoConcat.video (mode: "aggregate")
- videoConcat.video -> output.video

## 输出格式

请输出一个 JSON 对象，包含以下字段：

{
  "name": "工作流名称（从 prompt 中提取或自动生成）",
  "description": "工作流描述（可选）",
  "nodes": [
    {
      "alias": "节点的唯一别名",
      "kind": "节点类型",
      "config": {},
      "label": "显示标签（可选）"
    }
  ],
  "connections": [
    {
      "source": {"node": "源节点别名", "port": "源端口"},
      "target": {"node": "目标节点别名", "port": "目标端口"},
      "mode": "direct 或 map 或 aggregate"
    }
  ],
  "scene_count": 从用户描述中提取的场景数量，未提及则为 null,
  "variant_count": 从用户描述中提取的每个场景变体数量，未提及则为 null,
  "reasoning": "你对用户需求的理解和推理过程"
}

## 规则

1. scene_count: 从用户描述中提取场景数量。常见模式："N个场景"、"N个镜头"、"N个场景"。未提及则为 null。
2. variant_count: 从用户描述中提取每个场景的变体数量。常见模式："每张图N张"、"每个场景N个变体"。未提及则为 null。
3. 如果用户明确说"不要视频"、"只生成图片"、"不要合成"等，不要包含 imageToVideo 和 videoConcat 节点。
4. 如果用户说"只生成一张图片"，使用 textInput -> storyboard -> textToImage -> output.asset。
5. 输出必须是合法的 JSON，不要包含 markdown 代码块标记。
6. 节点 alias 必须唯一。
7. 连线必须遵循连线规则。
"""

# ---------------------------------------------------------------------------
# Example prompts for the system prompt (few-shot)
# ---------------------------------------------------------------------------

_EXAMPLES = """

## 示例

### 示例 1: 简单图片生成
用户: "只生成一张图片，不要视频，不要合成"
输出:
{
  "name": "简单图片生成",
  "nodes": [
    {"alias": "input", "kind": "textInput", "config": {"prompt": "只生成一张图片，不要视频，不要合成"}},
    {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 1}},
    {"alias": "textToImage", "kind": "textToImage", "config": {}},
    {"alias": "output", "kind": "output", "config": {}}
  ],
  "connections": [
    {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
    {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
    {"source": {"node": "textToImage", "port": "image"}, "target": {"node": "output", "port": "asset"}, "mode": "direct"}
  ],
  "scene_count": 1,
  "variant_count": null,
  "reasoning": "用户明确要求只生成图片，不要视频和合成，因此输出图片资产到 output.asset"
}

### 示例 2: 多场景多变体
用户: "生成两个场景，每个场景两张图，每张图生成5秒视频并合成"
输出:
{
  "name": "多场景多变体视频",
  "nodes": [
    {"alias": "input", "kind": "textInput", "config": {"prompt": "生成两个场景，每个场景两张图，每张图生成5秒视频并合成"}},
    {"alias": "storyboard", "kind": "storyboard", "config": {"scenes": 2}},
    {"alias": "textToImage", "kind": "textToImage", "config": {}},
    {"alias": "imageToVideo", "kind": "imageToVideo", "config": {"duration": 5}},
    {"alias": "videoConcat", "kind": "videoConcat", "config": {}},
    {"alias": "output", "kind": "output", "config": {}}
  ],
  "connections": [
    {"source": {"node": "input", "port": "text"}, "target": {"node": "storyboard", "port": "prompt"}, "mode": "direct"},
    {"source": {"node": "storyboard", "port": "scenes"}, "target": {"node": "textToImage", "port": "scene"}, "mode": "map"},
    {"source": {"node": "textToImage", "port": "image"}, "target": {"node": "imageToVideo", "port": "image"}, "mode": "map"},
    {"source": {"node": "imageToVideo", "port": "video"}, "target": {"node": "videoConcat", "port": "video"}, "mode": "aggregate"},
    {"source": {"node": "videoConcat", "port": "video"}, "target": {"node": "output", "port": "video"}, "mode": "direct"}
  ],
  "scene_count": 2,
  "variant_count": 2,
  "reasoning": "用户要求两个场景，每个场景两张图（variant_count=2），生成5秒视频并合成完整视频"
}
"""


def _build_system_prompt() -> str:
    """Build the full system prompt with examples."""
    base = _SYSTEM_PROMPT + "\n\n" + _catalog_prompt_section() + _EXAMPLES

    # Append available modules section
    try:
        from backend.app.services.agent_module_tools import (
            list_modules_for_agent,
            format_modules_for_system_prompt,
        )
        modules = list_modules_for_agent()
        if modules:
            base += "\n" + format_modules_for_system_prompt(modules)
    except Exception:
        pass  # If module tools fail, just use base prompt

    return base


def _extract_scene_count(prompt: str) -> int | None:
    """Extract scene count from the user prompt using regex patterns.

    Common Chinese patterns:
    - "N个场景" (N = Arabic or Chinese numeral)
    - "N个镜头"
    - "N个片段"
    - "N scenes"
    """
    # Handle real Unicode user input before the legacy mojibake-compatible
    # patterns retained below for old fixtures.
    chinese_number = r"[\d零〇一二两三四五六七八九十百]+"
    for pattern in (
        rf"({chinese_number})\s*个(?:场景|镜头|片段)",
        r"(\d+)\s*scenes?",
    ):
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return _parse_unicode_number(match.group(1))

    # Patterns that capture either Arabic digits or Chinese numeral characters
    patterns = [
        r"([\d零〇一二两三四五六七八九十百壹贰叁肆伍陆柒捌玖拾佰]+)\s*个场景",
        r"([\d零〇一二两三四五六七八九十百壹贰叁肆伍陆柒捌玖拾佰]+)\s*个镜头",
        r"([\d零〇一二两三四五六七八九十百壹贰叁肆伍陆柒捌玖拾佰]+)\s*个片段",
        r"(\d+)\s*scenes?",
    ]
    for pat in patterns:
        m = re.search(pat, prompt, re.IGNORECASE)
        if m:
            raw = m.group(1)
            if raw.isdigit():
                return int(raw)
            return _parse_cn_number(raw)
    return None


def _extract_variant_count(prompt: str) -> int | None:
    """Extract variant count from the user prompt.

    Common Chinese patterns:
    - "每张图N张"
    - "每个场景N张图"
    - "每个场景N个变体"
    """
    chinese_number = r"[\d零〇一二两三四五六七八九十百]+"
    for pattern in (
        rf"每(?:个)?场景\s*({chinese_number})\s*(?:张图(?:片)?|个变体)",
        rf"每张图\s*({chinese_number})\s*(?:张|个变体)",
    ):
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return _parse_unicode_number(match.group(1))

    cn_digits = r"[\d零〇一二两三四五六七八九十百壹贰叁肆伍陆柒捌玖拾佰]+"
    patterns = [
        rf"每张图\s*({cn_digits})\s*张",
        rf"每个场景\s*({cn_digits})\s*张",
        rf"每个场景\s*({cn_digits})\s*个变体",
        rf"每.*?({cn_digits})\s*个变体",
    ]
    for pat in patterns:
        m = re.search(pat, prompt, re.IGNORECASE)
        if m:
            raw = m.group(1)
            if raw.isdigit():
                return int(raw)
            return _parse_cn_number(raw)
    return None


def _wants_no_video(prompt: str) -> bool:
    """Check if the prompt explicitly says no video generation."""
    no_video_patterns = [
        "不要视频",
        "无需视频",
        "只生成图片",
        "只生成一张图",
        "不生成视频",
        "不要合成",
        "不要视频",
        "不要合成",
        "只生成图片",
        "只生成一张图",
        "不要视频",
        "no video",
        "without video",
    ]
    lower = prompt.lower()
    return any(p in lower for p in no_video_patterns)


def _parse_json_response(text: str) -> dict | None:
    """Extract and parse JSON from MiMo's response.

    Handles responses that may be wrapped in markdown code blocks.
    """
    # Try to extract from markdown code block
    if "```json" in text:
        try:
            text = text.split("```json")[1].split("```")[0]
        except (IndexError, ValueError):
            pass
    elif "```" in text:
        try:
            text = text.split("```")[1].split("```")[0]
        except (IndexError, ValueError):
            pass

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _dict_to_intent(data: dict, prompt: str) -> WorkflowIntent | None:
    """Convert a parsed JSON dict into a validated WorkflowIntent.

    Returns None if the data is invalid.
    """
    try:
        nodes_data = data.get("nodes", [])
        if not nodes_data:
            return None

        nodes: list[NodeIntent] = []
        for n in nodes_data:
            if not isinstance(n, dict):
                return None
            alias = n.get("alias", "")
            kind = n.get("kind", "")
            if not alias or not kind:
                return None
            if kind not in NODE_KINDS:
                logger.warning(f"Unknown node kind: {kind}")
                return None
            nodes.append(NodeIntent(
                alias=alias,
                kind=kind,
                moduleId=n.get("moduleId"),
                moduleVersion=n.get("moduleVersion"),
                configOverrides=n.get("configOverrides", {}),
                config=n.get("config", {}),
                label=n.get("label"),
            ))

        connections: list[ConnectionIntent] = []
        for c in data.get("connections", []):
            if not isinstance(c, dict):
                return None
            source_data = c.get("source", {})
            target_data = c.get("target", {})
            if not isinstance(source_data, dict) or not isinstance(target_data, dict):
                return None
            connections.append(ConnectionIntent(
                source=PortRef(node=source_data.get("node", ""), port=source_data.get("port", "")),
                target=PortRef(node=target_data.get("node", ""), port=target_data.get("port", "")),
                mode=c.get("mode", "direct"),
            ))

        # Validate that all connection aliases reference existing nodes
        node_aliases = {n.alias for n in nodes}
        for conn in connections:
            if conn.source.node not in node_aliases:
                logger.warning(f"Connection references unknown source node: {conn.source.node}")
                return None
            if conn.target.node not in node_aliases:
                logger.warning(f"Connection references unknown target node: {conn.target.node}")
                return None

        scene_count = data.get("scene_count")
        variant_count = data.get("variant_count")

        intent = WorkflowIntent(
            name=data.get("name", prompt[:50] if prompt else "Generated Workflow"),
            description=data.get("description"),
            nodes=nodes,
            connections=connections,
            scene_count=scene_count,
            variant_count=variant_count,
            duration=data.get("duration"),
            resolution=data.get("resolution"),
            warnings=[],
        )
        return _normalize_image_only_intent(_apply_intent_constraints(intent))
    except Exception as exc:
        logger.warning(f"Failed to build WorkflowIntent from parsed data: {exc}")
        return None


def _normalize_image_only_intent(intent: WorkflowIntent) -> WorkflowIntent:
    """Normalize image-only workflows to the explicit polymorphic asset sink."""
    kinds = {node.kind for node in intent.nodes}
    if "textToImage" not in kinds or "imageToVideo" in kinds:
        return intent
    output_aliases = {node.alias for node in intent.nodes if node.kind == "output"}
    if not output_aliases:
        return intent
    connections: list[ConnectionIntent] = []
    for conn in intent.connections:
        if conn.target.node in output_aliases:
            connections.append(conn.model_copy(update={
                "target": PortRef(node=conn.target.node, port="asset"),
            }))
        elif conn.source.node not in output_aliases:
            connections.append(conn)
    return intent.model_copy(update={
        "connections": connections,
        "warnings": [*intent.warnings, "Image output normalized to output.asset"],
    })


def _apply_intent_constraints(intent: WorkflowIntent) -> WorkflowIntent:
    """Copy planning constraints into the configs consumed at execution."""
    nodes: list[NodeIntent] = []
    for node in intent.nodes:
        config = dict(node.config)
        if node.kind == "storyboard" and intent.scene_count is not None:
            config["scenes"] = intent.scene_count
        elif node.kind == "textToImage" and intent.variant_count is not None:
            config["variantCount"] = intent.variant_count
        elif node.kind == "imageToVideo":
            if intent.duration is not None:
                config["duration"] = intent.duration
            if intent.resolution is not None:
                config["resolution"] = intent.resolution
        nodes.append(node.model_copy(update={"config": config}))
    return intent.model_copy(update={"nodes": nodes})


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------

def _template_fallback(prompt: str) -> WorkflowIntent:
    """Build a default WorkflowIntent matching the standard 6-node pipeline."""
    agent_trace.safe_add_step(
        None, "fallback", "template_fallback", "ok", 0,
        {"reason": "llm_unavailable_or_parse_failed"},
    )
    scene_count = _extract_scene_count(prompt) or 5
    variant_count = _extract_variant_count(prompt)

    no_video = _wants_no_video(prompt)

    nodes = [
        NodeIntent(alias="input", kind="textInput", config={"prompt": prompt}),
        NodeIntent(alias="storyboard", kind="storyboard", config={"scenes": scene_count}),
        NodeIntent(alias="textToImage", kind="textToImage"),
    ]
    connections = [
        ConnectionIntent(
            source=PortRef(node="input", port="text"),
            target=PortRef(node="storyboard", port="prompt"),
        ),
        ConnectionIntent(
            source=PortRef(node="storyboard", port="scenes"),
            target=PortRef(node="textToImage", port="scene"),
            mode="map",
        ),
    ]

    if not no_video:
        nodes.extend([
            NodeIntent(alias="imageToVideo", kind="imageToVideo"),
            NodeIntent(alias="videoConcat", kind="videoConcat"),
            NodeIntent(alias="output", kind="output"),
        ])
        connections.extend([
            ConnectionIntent(
                source=PortRef(node="textToImage", port="image"),
                target=PortRef(node="imageToVideo", port="image"),
                mode="map",
            ),
            ConnectionIntent(
                source=PortRef(node="imageToVideo", port="video"),
                target=PortRef(node="videoConcat", port="video"),
                mode="aggregate",
            ),
            ConnectionIntent(
                source=PortRef(node="videoConcat", port="video"),
                target=PortRef(node="output", port="video"),
            ),
        ])
    else:
        nodes.append(NodeIntent(alias="output", kind="output"))
        connections.append(
            ConnectionIntent(
                source=PortRef(node="textToImage", port="image"),
                target=PortRef(node="output", port="asset"),
            )
        )

    return WorkflowIntent(
        name=prompt[:50] if prompt else "Generated Workflow",
        description=prompt,
        nodes=nodes,
        connections=connections,
        scene_count=scene_count,
        variant_count=variant_count,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def parse_workflow_intent(
    prompt: str,
    provider: Any | None = None,
) -> WorkflowIntent:
    """Parse a user prompt into a structured WorkflowIntent.

    Uses MiMo (or any text-capable provider) to generate the intent.
    Falls back to a template-based intent if the provider is unavailable
    or returns invalid JSON.

    Args:
        prompt: The user's natural language description.
        provider: A text-capable provider instance. If None, falls back
                  to the template.

    Returns:
        A validated WorkflowIntent.
    """
    if provider is None:
        logger.info("No provider available, using template fallback")
        agent_trace.safe_add_step(
            None, "parse", "structured_intent", "skipped", 0, {"reason": "no_provider"},
        )
        return _template_fallback(prompt)

    system_prompt = _build_system_prompt()
    full_prompt = f"{system_prompt}\n\n用户需求: {prompt}\n\n请输出 WorkflowIntent JSON:"

    try:
        response_text = await provider.generate_text(
            full_prompt,
            {"temperature": 0.3, "max_tokens": 4096},
        )
    except Exception as exc:
        logger.warning(f"Provider call failed: {exc}, using template fallback")
        agent_trace.safe_add_step(
            None, "parse", "structured_intent", "error", 0,
            {"error_type": type(exc).__name__},
        )
        return _template_fallback(prompt)

    # Parse JSON
    data = _parse_json_response(response_text)
    if data is None:
        logger.warning("Failed to parse provider response as JSON, using template fallback")
        agent_trace.safe_add_step(
            None, "parse", "structured_intent", "error", 0, {"reason": "invalid_json"},
        )
        return _template_fallback(prompt)

    # Build intent
    intent = _dict_to_intent(data, prompt)
    if intent is None:
        logger.warning("Invalid intent data from provider, using template fallback")
        agent_trace.safe_add_step(
            None, "parse", "structured_intent", "error", 0, {"reason": "invalid_intent"},
        )
        return _template_fallback(prompt)

    agent_trace.safe_add_step(
        None, "parse", "structured_intent", "ok", 0,
        {"node_count": len(intent.nodes), "connection_count": len(intent.connections)},
    )

    # Add reasoning as a warning if present
    reasoning = data.get("reasoning")
    if reasoning:
        intent.warnings.append(f"Parser reasoning: {reasoning}")

    return intent


def get_system_prompt() -> str:
    """Return the system prompt used for MiMo (for testing/inspection)."""
    return _build_system_prompt()
