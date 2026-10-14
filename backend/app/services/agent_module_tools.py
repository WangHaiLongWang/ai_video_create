"""Agent Module Tools -- discover and describe modules for the Agent system prompt.

Provides functions to list/get published modules and format them for inclusion
in the MiMo system prompt, so the Agent can select modules instead of base
node kinds when appropriate.
"""

from __future__ import annotations

from typing import Any

from backend.app.services import agent_trace
from backend.app.services.module_registry import get_module_registry


def list_modules_for_agent(
    status: str = "published",
    capability: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """List modules in a format suitable for the Agent system prompt.

    Returns simplified info: id, version, label, description, baseKind,
    category, capability, ports summary.
    """
    registry = get_module_registry()
    modules = registry.list_modules(status=status, capability=capability)

    result: list[dict] = []
    for m in modules:
        if category and m.category != category:
            continue

        # Summarize ports
        input_ports = [p.get("id", "") for p in m.ports.get("inputs", [])]
        output_ports = [p.get("id", "") for p in m.ports.get("outputs", [])]

        result.append({
            "id": m.id,
            "version": m.version,
            "label": m.label,
            "description": m.description,
            "baseKind": m.base_kind,
            "category": m.category,
            "capability": m.provider_policy.capability,
            "inputPorts": input_ports,
            "outputPorts": output_ports,
        })

    agent_trace.safe_add_step(
        None, "tool", "list_modules_for_agent", "ok", 0,
        {"module_count": len(result)},
    )
    return result


def get_module_for_agent(module_id: str, version: str | None = None) -> dict | None:
    """Get detailed module info for the Agent.

    Returns: id, version, label, description, baseKind, category,
    providerPolicy, configSchema, ports, defaultConfig.

    Returns None if the module is not found.
    """
    registry = get_module_registry()
    module = registry.get_module(module_id, version=version)
    if module is None:
        agent_trace.safe_add_step(
            None, "tool", "get_module_for_agent", "error", 0, {"found": False},
        )
        return None

    agent_trace.safe_add_step(
        None, "tool", "get_module_for_agent", "ok", 0, {"found": True},
    )

    return {
        "id": module.id,
        "version": module.version,
        "label": module.label,
        "description": module.description,
        "baseKind": module.base_kind,
        "category": module.category,
        "providerPolicy": {
            "capability": module.provider_policy.capability,
            "allowed": module.provider_policy.allowed,
            "default": module.provider_policy.default,
            "locked": module.provider_policy.locked,
        },
        "configSchema": module.config_schema,
        "ports": module.ports,
        "defaultConfig": module.default_config,
    }


def format_modules_for_system_prompt(modules: list[dict]) -> str:
    """Format module list as text for inclusion in Agent system prompt.

    Groups by category, shows key info per module.
    """
    if not modules:
        return ""

    # Group by category
    categories: dict[str, list[dict]] = {}
    for mod in modules:
        cat = mod.get("category", "other")
        categories.setdefault(cat, []).append(mod)

    lines: list[str] = []
    lines.append("## 可用模块 (Published Modules)")
    lines.append("")
    lines.append("当用户请求匹配以下模块时，应优先使用模块而非基础节点类型。")
    lines.append("在节点中使用 moduleId 字段指定模块。")
    lines.append("")

    for cat, cat_modules in sorted(categories.items()):
        lines.append(f"### {cat}")
        lines.append("")
        for mod in cat_modules:
            mod_id = mod["id"]
            label = mod["label"]
            desc = mod.get("description", "")
            base_kind = mod.get("baseKind", "")
            inputs = ", ".join(mod.get("inputPorts", []))
            outputs = ", ".join(mod.get("outputPorts", []))
            cap = mod.get("capability", "")

            lines.append(f"- **{label}** (`{mod_id}`)")
            lines.append(f"  - 基础类型: {base_kind}, 能力: {cap}")
            lines.append(f"  - 描述: {desc}")
            if inputs:
                lines.append(f"  - 输入端口: {inputs}")
            if outputs:
                lines.append(f"  - 输出端口: {outputs}")
            lines.append("")

    lines.append("使用模块时，在节点中添加 `moduleId` 字段:")
    lines.append('```json')
    lines.append('{"alias": "img", "kind": "textToImage", "moduleId": "builtin.seedream.text-to-image", "config": {}}')
    lines.append('```')
    lines.append("")

    return "\n".join(lines)
