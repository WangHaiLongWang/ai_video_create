# Phase D: Agent 与模板体验

> 2026-09-15

---

## 目标

将 Workflow Agent 从"硬编码模板"升级为"LLM 驱动的智能编排"，并完善模板系统和前端设置体验。

---

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                  前端 (React)                        │
│  ┌───────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Agent     │  │ Settings     │  │ Template    │  │
│  │ Composer  │  │ Panel        │  │ Selector    │  │
│  │ (Enhanced)│  │ (New)        │  │ (New)       │  │
│  └─────┬─────┘  └──────┬───────┘  └──────┬──────┘  │
│        │               │                 │          │
│  ┌─────▼───────────────▼─────────────────▼──────┐  │
│  │              API Client                        │  │
│  └───────────────────┬───────────────────────────┘  │
└──────────────────────┼──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  后端 (FastAPI)                       │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Agent API    │  │ Config API  │  │ Template   │  │
│  │ (Enhanced)   │  │ (Extended)  │  │ API (New)  │  │
│  └──────┬───────┘  └─────────────┘  └──────┬─────┘  │
│         │                                   │        │
│  ┌──────▼───────────────────────────────────▼─────┐  │
│  │           Agent Service                         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────┐  │  │
│  │  │ LLM Client │  │ Tool       │  │ Graph    │  │  │
│  │  │ (Provider) │  │ Registry   │  │ Patcher  │  │  │
│  │  └────────────┘  └────────────┘  └──────────┘  │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 详细任务

### D1: Agent Service（核心）

**文件**: `backend/app/services/agent.py`

```python
class AgentService:
    """LLM-driven workflow agent with tool calling."""

    async def generate_from_prompt(self, prompt: str, config: dict) -> WorkflowSpec:
        """从自然语言生成完整工作流。"""
        # 1. 构建系统提示词（包含可用节点、端口类型、工具描述）
        # 2. 调用 LLM（带 tools 参数）
        # 3. 解析 LLM 响应 → 生成节点 + 边
        # 4. 校验 → 返回 WorkflowSpec

    async def modify_workflow(self, workflow: WorkflowSpec, instruction: str) -> GraphPatch:
        """修改现有工作流。"""
        # 1. 序列化当前工作流为文本描述
        # 2. 调用 LLM（带 modify_workflow 工具）
        # 3. 解析 → 生成 GraphPatch（add/remove/update nodes/edges）
        # 4. 返回 patch（不直接应用，等用户确认）

    async def explain_workflow(self, workflow: WorkflowSpec) -> str:
        """解释工作流功能。"""
        # 将工作流序列化 → LLM 总结功能和流程
```

**工具定义（LLM Tool Calling）**:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": "添加一个节点到工作流",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["textInput", "storyboard", ...]},
                    "label": {"type": "string"},
                    "config": {"type": "object"},
                },
                "required": ["kind", "label"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "connect_nodes",
            "description": "连接两个节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["source_id", "target_id"]
            }
        }
    },
    # ... update_node, remove_node, etc.
]
```

### D2: GraphPatch 模型

**文件**: `backend/app/models.py`（扩展）

```python
class GraphPatch(BaseModel):
    """工作流修改补丁。"""
    description: str                    # 修改描述
    add_nodes: list[WorkflowNode]       # 新增节点
    remove_nodes: list[str]             # 删除节点 ID
    update_nodes: list[NodeUpdate]      # 更新节点
    add_edges: list[WorkflowEdge]       # 新增边
    remove_edges: list[str]             # 删除边 ID

class NodeUpdate(BaseModel):
    id: str
    label: str | None = None
    config: dict[str, Any] | None = None
```

### D3: Agent API

**文件**: `backend/app/api/agent.py`

```
POST /api/agent/generate     — 从提示词生成工作流（已有，增强）
POST /api/agent/modify       — 修改工作流（返回 GraphPatch）
POST /api/agent/explain      — 解释工作流功能
POST /api/agent/apply-patch  — 应用 GraphPatch 到工作流
```

### D4: 模板系统

**文件**: `backend/app/services/templates.py`

```python
TEMPLATES = {
    "prompt-to-video": {
        "name": "提示词生成视频",
        "description": "从文字描述生成完整视频",
        "nodes": [...], "edges": [...],
        "tags": ["视频", "生成"],
    },
    "image-storyboard": {
        "name": "图片分镜",
        "description": "生成图片分镜故事板",
        ...
    },
    # ... 更多模板
}

class TemplateService:
    def list_templates(self) -> list[TemplateInfo]
    def get_template(self, template_id: str) -> WorkflowSpec
    def create_from_template(self, template_id: str, params: dict) -> WorkflowSpec
    def save_as_template(self, workflow: WorkflowSpec, name: str) -> str
```

**API**: `backend/app/api/templates.py`

```
GET  /api/templates              — 列出所有模板
GET  /api/templates/{id}         — 获取模板详情
POST /api/templates/{id}/create  — 从模板创建工作流
POST /api/templates/save         — 保存当前工作流为模板
```

### D5: 前端设置面板

**文件**: `frontend/src/components/SettingsPanel.tsx`

```tsx
// 功能：
// - Provider 选择（下拉框）
// - API Key 输入（密码框 + 显示/隐藏）
// - Ollama URL 配置
// - ComfyUI URL 配置
// - 测试连接按钮
// - 保存设置
```

### D6: 前端模板选择器

**文件**: `frontend/src/components/TemplateSelector.tsx`

```tsx
// 功能：
// - 模板卡片列表（名称 + 描述 + 标签）
// - 搜索过滤
// - 点击应用模板
// - 从当前工作流保存为模板
```

### D7: Agent Composer 增强

**文件**: `frontend/src/components/AgentComposer.tsx`（更新）

```tsx
// 新增功能：
// - 支持"修改工作流"模式（输入修改指令）
// - GraphPatch diff 预览
// - 确认/取消应用
// - 解释工作流按钮
```

### D8: 测试

| 测试文件 | 覆盖 |
|---------|------|
| `tests/services/test_agent.py` | AgentService 生成/修改/解释 |
| `tests/services/test_templates.py` | 模板 CRUD |
| `tests/api/test_agent_api.py` | Agent API 端点 |
| `tests/api/test_templates_api.py` | 模板 API 端点 |

---

## 实现顺序

1. **D2** GraphPatch 模型（无依赖）
2. **D1** Agent Service（依赖 D2 + Provider）
3. **D4** 模板系统（无依赖）
4. **D3** Agent + Template API（依赖 D1 + D4）
5. **D8** 测试（依赖 D1-D4）
6. **D5** 前端设置面板（依赖 Config API）
7. **D6** 前端模板选择器（依赖 Template API）
8. **D7** Agent Composer 增强（依赖 Agent API + D5/D6）

---

## 验收标准

- [ ] LLM 可从提示词生成合法工作流
- [ ] LLM 可修改现有工作流并返回 GraphPatch
- [ ] GraphPatch 可正确应用到工作流
- [ ] 模板系统可列出/应用/保存模板
- [ ] 前端设置页可配置 Provider
- [ ] 前端模板选择器可浏览/应用模板
- [ ] 所有测试通过
- [ ] 无 TypeScript 错误
