# React Flow 节点自定义与 Workflow Agent 前瞻计划

> 状态：Active 子计划  
> 日期：2026-09-18
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)  
> 关联：[FRONTEND-FLOW-SCENE-PLAN.md](FRONTEND-FLOW-SCENE-PLAN.md)

## 0. 2026-09-18 代码检查点

| 工单 | 状态 | 当前代码证据 | 剩余出口 |
|---|---|---|---|
| RF-001 | Done | Handle 14px、`overflow: visible`、30%-70% 布局 | Playwright 实测命中区 |
| RF-002 | Partial | `isValidConnection`、`connectionRadius=20` 已有 | 增加 Strict mode 与连接会话状态 |
| RF-003 | Partial | Store 会校验并写 `connectionError` | 改为结构化 `ConnectResult`，覆盖前置拒绝 |
| RF-004 | Partial | Toast 已挂载 | 兼容端口高亮、inline/ARIA 原因反馈 |
| RF-005 | Todo | 尚无 `flow-connection.spec.ts` | 浏览器连线/拖拽矩阵全绿 |
| FIELD-001 | Done/需统一 | TS FieldDefinition/validator 已有 | 与后端/共享 Schema 对齐 |
| FIELD-002 | Done 基础版 | FieldEditorDialog、动态字段 UI | 完整类型与可访问性验收 |
| FIELD-003 | Done 基础版 | add/update/remove/duplicate/reorder actions | rename 同步迁移 config key |
| FIELD-004 | Partial | 字段删除/Undo 基础存在 | 影响分析和单事务验收 |
| FIELD-005 | Todo | PortEditor 只读，添加按钮禁用 | 受约束端口 CRUD 与 Edge 联动 |
| FIELD-006 | Done 基础版 | WorkflowSpec 2.0 + v1 migration | API/DB/viewport roundtrip |
| FIELD-007 | Partial | Schema/store/component 单测存在 | Playwright 字段/端口 E2E |
| AGENT-201 | Done | WorkflowIntent Pydantic 模型 | Schema 版本冻结 |
| AGENT-202 | Done 基础版 | manifests/templates/validate/layout tools | 工具与共享契约一致性 |
| AGENT-203 | Done 基础版 | alias compiler 和 Handle edges | MiMo 结构化输出主链 |
| AGENT-204 | Done 基础版 | bounded repair + repair steps | golden case 失败率验收 |
| AGENT-205 | Done 基础版 | 调用量/时长估算 | 真实价格/预算策略后置 |
| AGENT-206 | Backend Done | v2 preview/modify/apply API 已注册 | 前端 API contract 接入 |
| AGENT-207 | Partial | 前端有 intent/cost/repair 展示代码 | 当前仍调用 v1，适配 `compiled_workflow` |
| AGENT-208 | Todo | 未形成可核验审计闭环 | 脱敏、限额、审计持久化 |
| AGENT-209 | Partial | compiler/preview/repair tests 已有 | 30+ 中文 golden cases |
| AGENT-210 | Todo | 无 Agent v2 浏览器闭环 | Prompt → apply → save → run |

当前关键路径已经从“修 DOM 才能连线”转为：`RF-002..005 → 后端权威校验 → FIELD-005/007 → AGENT-206/207/210`。

## 1. 目标

交付一个真正可用的可视化工作流编辑器：

1. 用户可以添加/删除节点配置字段；
2. 高级用户可以受约束地添加/删除自定义端口；
3. 节点间连线可见、易点击、可验证、有错误提示；
4. 工作流可保存、导入、导出、迁移和运行；
5. Workflow Agent 能根据用户 Prompt 生成完整 WorkflowSpec 2.0；
6. Agent 输出先校验、修复和预览，用户确认后再应用。

## 2. 当前根因分析

### 2.1 连线“不可行”的直接原因

| 根因 | 当前代码 | 用户表现 |
|---|---|---|
| Handle 命中区过小 | `.node-handle` 为 9×9px | 很难开始/结束拖线 |
| Handle 被裁剪 | `.studio-node { overflow:hidden }` | 外伸部分不可点击 |
| 垂直定位公式错误 | 单端口约 80%，第二端口约 97% | 端口贴底、重叠、被裁剪 |
| 无 Canvas 预校验 | 未设置 `isValidConnection` | 拖线时不知道目标是否兼容 |
| 拒绝静默 | Store 仅 `console.warn` | 放开后“没有反应” |
| Agent 格式落后 | Agent Prompt 只要求 source/target | Agent 图缺 Handle ID |
| 旧图兼容不一致 | v1 migration 主要在前端加载 | API/Agent/模板路径可能返回旧边 |

### 2.2 自定义字段现状

- PropertyPanel 只遍历已有 `config` key。
- 没有“添加字段/删除字段”操作。
- 字段无 label、description、type、required、default、options、secret 等定义。
- 任意字符串 key 会导致不同节点和后端 Handler 无法理解。
- 删除字段没有确认、撤销或下游影响检查。

### 2.3 Workflow Agent 现状

- 使用自然语言要求模型返回 JSON，然后 `json.loads`。
- Agent 内部 NODE_CATALOG 与前后端 Manifest 分开维护。
- SYSTEM_PROMPT 仍描述旧 `inputType/outputType` 与 source/target Edge。
- 未要求 WorkflowSpec 2.0、ports、sourceHandle/targetHandle、viewport 和 EdgeData。
- 解析失败直接回退固定模板，没有基于 validator 的有限自修复。
- generate-preview 有预览，但 warnings 未包含真实图校验问题。

## 3. 节点字段模型

### 3.1 保留字段

以下字段属于平台契约，用户不能删除：

```text
id, type, position
data.kind, data.label, data.description, data.status
data.ports, data.config
```

### 3.2 自定义配置字段

在节点中增加 `fieldSchema`，值仍保存在 `config`：

```json
{
  "data": {
    "fieldSchema": [
      {
        "id": "camera_motion",
        "label": "运镜",
        "type": "select",
        "required": false,
        "default": "slow_push",
        "options": [
          {"label": "缓慢前推", "value": "slow_push"},
          {"label": "固定镜头", "value": "static"}
        ],
        "description": "传给视频 Provider 的运镜提示",
        "advanced": false
      }
    ],
    "config": {"camera_motion": "slow_push"}
  }
}
```

首版字段类型：

```text
text, textarea, number, boolean, select, multi_select, json, prompt
```

规则：

- ID 使用 snake_case，节点内唯一。
- 禁止覆盖保留字段和 `provider/model` 等 manifest-owned 字段，除非以 override 方式明确编辑。
- secret 类型首版不开放；Key 只进入 Provider 设置。
- JSON 字段限制大小并做 Schema 校验。
- 删除字段默认同时删除 config 值，可选择保留 orphan value 供恢复。

### 3.3 自定义端口字段

端口编辑独立于普通配置字段：

```json
{
  "id": "reference_image",
  "label": "参考图",
  "direction": "input",
  "type": "image",
  "required": false,
  "cardinality": "many"
}
```

删除端口时：

1. 检查关联 Edge；
2. 显示将删除的连线；
3. 用户二次确认；
4. 一个 Undo 事务同时删除端口和边；
5. 后端重新验证完整图。

首版只允许从受支持类型中选择，不允许任意自定义类型。

## 4. React Flow 连线修复设计

### 4.1 节点 DOM

将节点分成外壳和内容：

```text
.studio-node-shell      overflow: visible
  ├─ Handle             14-18px 命中区
  └─ .studio-node-card  overflow: hidden
```

端口按实际行布局，不用百分比公式：

```text
header
input port row 1
input port row 2
config summary
output port row 1
```

Handle 与 label 同一行，鼠标和键盘均能聚焦。

### 4.2 Canvas 连接状态

新增：

- `isValidConnection`：拖动期间即时验证。
- `onConnectStart/onConnectEnd`：记录 source port 和失败原因。
- `connectionRadius`：提高目标吸附范围。
- `connectionLineComponent`：合法/非法使用不同颜色。
- `connectionMode=Strict`：只允许 source → target。
- 兼容端口加 `.is-connectable`，不兼容端口降暗。
- Toast/inline message 显示 `TYPE_MISMATCH`、`CARDINALITY_VIOLATION` 等错误。

### 4.3 Store 行为

`onConnect` 改为返回结果：

```ts
type ConnectResult =
  | { ok: true; edgeId: string }
  | { ok: false; error: ValidationError }
```

必须处理：

- Handle 缺失；
- self-loop；
- duplicate edge；
- direction；
- type mismatch；
- cardinality；
- 新边导致 DAG cycle；
- manifest 未知。

成功 Edge 自动推导 mode：

- one → one：direct
- many → one 且目标 execution.mapOver：map
- one/many → many aggregate port：aggregate

### 4.4 后端权威校验

必须在以下入口统一调用 `validate_graph`：

- create workflow；
- update workflow；
- import workflow；
- Agent generate preview；
- Agent modify preview/apply；
- execution start。

返回结构化 422：

```json
{
  "error": {
    "code": "WORKFLOW_GRAPH_INVALID",
    "message": "工作流包含 2 个连接错误",
    "details": {"errors": []}
  }
}
```

## 5. 自定义字段 UI

### 5.1 PropertyPanel

新增分区：

```text
基础配置
Provider 配置
自定义字段
端口（高级）
危险操作
```

操作：

- `+ 添加字段` 打开 FieldEditorDialog；
- 字段菜单支持重命名、复制、上移/下移、删除；
- 删除前显示影响；
- 表单即时校验；
- 保存为一个 Undo 步骤；
- Manifest 字段显示锁图标，不允许删除。

### 5.2 FieldEditorDialog

字段：ID、label、type、description、required、default、options、advanced。

验收：

- 重复/非法 ID 不可保存；
- select 必须至少一个 option；
- number default 必须为 number；
- 删除字段后导出/导入不复活；
- Undo 可以恢复字段和值。

## 6. Workflow Agent 目标架构

### 6.1 Agent 工作流

```text
User Prompt
  → Intent Parser
  → Template/Node Discovery Tools
  → Structured WorkflowSpec 2.0 Candidate
  → Graph Validator
  → Layout Service
  → bounded repair (最多 2 次)
  → Preview(diff/warnings/cost estimate)
  → User Confirm
  → Apply with expected_version
```

### 6.2 Agent 工具

| 工具 | 用途 |
|---|---|
| `list_node_manifests` | 获取节点、端口和 config schema |
| `list_templates` | 优先复用官方模板 |
| `get_workflow` | 修改现有图 |
| `validate_workflow` | 获取结构化错误 |
| `layout_workflow` | 计算位置，不让 LLM 猜坐标 |
| `preview_patch` | 生成 diff、风险和调用量 |
| `estimate_calls` | 估算 LLM/图片/视频次数和时长 |

Agent 不直接访问数据库、不执行代码、不调用收费 Provider。

### 6.3 结构化输出

Agent 输出 WorkflowIntent，而不是直接自由生成所有 React Flow 字段：

```json
{
  "name": "滑雪教学短视频",
  "templateId": "prompt-to-video",
  "nodes": [
    {"alias": "story", "kind": "storyboard", "config": {"scenes": 1}},
    {"alias": "image", "kind": "textToImage", "config": {"variantCount": 2}},
    {"alias": "video", "kind": "imageToVideo", "config": {"duration": 3}}
  ],
  "connections": [
    {"from": "story.scenes", "to": "image.scene", "mode": "map"}
  ]
}
```

后端 Compiler 将 alias/port 转为稳定 ID、React Flow Edge 和位置。这比让模型直接生成坐标和 UUID 更可靠。

### 6.4 Prompt 解析能力

需要提取：

- 用户目标和模板类别；
- scene 数量；
- 每 scene 图片变体数量；
- 视频时长、分辨率、比例、音频；
- Provider/模型偏好；
- 是否需要拼接；
- 内容硬约束和 negative prompt；
- 输出策略和预计调用量。

不确定项必须进入 preview warning，不默默猜测高成本配置。

### 6.5 安全与可靠性

- 仅允许 Node Manifest 白名单 kind/port/config。
- 严禁输出 API Key、绝对路径和签名 URL。
- 限制节点数、边数、scene 数和预计外部调用数。
- 有损 patch、Provider 变化和调用量上升必须确认。
- Agent 输出保存 prompt/version/model/validator errors，但脱敏。
- LLM 不可用时优先模板 fallback，并标记 `generated_by=template`。

## 7. 工单计划

### 7.1 连线恢复（P0，2-3 天）

| ID | 工作量 | 任务 | 文件 | 验收 |
|---|---:|---|---|---|
| RF-001 | 0.5d | 修复 overflow 和 Handle 布局 | `StudioNode.tsx`, CSS | 每个端口 ≥14px 可点击 |
| RF-002 | 0.5d | Canvas `isValidConnection` 与 Strict mode | `Canvas.tsx` | 拖线实时反馈 |
| RF-003 | 0.5d | Store 返回结构化 ConnectResult | `store.ts` | 不再静默失败 |
| RF-004 | 0.5d | Toast/端口高亮/失败提示 | Canvas/CSS | 用户看到拒绝原因 |
| RF-005 | 1d | 鼠标/键盘 Playwright 连线矩阵 | `e2e/flow-connection.spec.ts` | 6 条默认边和错误场景通过 |

### 7.2 自定义字段（P0/P1，1.5-2 周）

| ID | 工作量 | 任务 |
|---|---:|---|
| FIELD-001 | 1d | FieldDefinition Schema、reserved key、validator |
| FIELD-002 | 2d | FieldEditorDialog 与动态表单渲染 |
| FIELD-003 | 1d | 添加/删除/重命名/排序 Store actions |
| FIELD-004 | 1d | 删除确认、Edge/端口影响分析、Undo 事务 |
| FIELD-005 | 1.5d | 高级 PortEditor，类型/基数/required |
| FIELD-006 | 1d | WorkflowSpec 2.0 roundtrip/migration |
| FIELD-007 | 1.5d | 单元与 Playwright E2E |

### 7.3 Workflow Agent 2.0（P0，2-3 周）

| ID | 工作量 | 任务 |
|---|---:|---|
| AGENT-201 | 1.5d | WorkflowIntent Pydantic/JSON Schema |
| AGENT-202 | 2d | Manifest/Template/Validate/Layout 工具层 |
| AGENT-203 | 2d | Structured output 与 alias compiler |
| AGENT-204 | 1.5d | Validator-driven repair（最多 2 次） |
| AGENT-205 | 1d | 调用量/成本估算与 warning |
| AGENT-206 | 2d | Generate/Modify preview API v2 |
| AGENT-207 | 2d | 前端 diff、字段/端口变更展示和确认 |
| AGENT-208 | 1d | 审计记录、脱敏和限额 |
| AGENT-209 | 2d | 30+ 中文 golden cases |
| AGENT-210 | 2d | Playwright：Prompt → 完整可连线流程 |

## 8. 实施顺序

```text
RF-001..005（先让人工连线真正可用）
  → FIELD-001..004（安全自定义配置字段）
  → AGENT-201/202（共享契约和工具）
  → FIELD-005..007（高级端口）
  → AGENT-203..210（生成、修复、预览、E2E）
```

不得在连线基础交互仍不可用时先扩展 Agent；否则 Agent 生成的图无法由用户验证和修正。

## 9. 验收矩阵

### 人工编辑

1. 从任意合法 source Handle 拖到合法 target Handle，边立即出现。
2. 类型不兼容目标不能落边，并显示原因。
3. 同一 one 输入第二条边被拒绝。
4. 自环、重复边和成环被拒绝。
5. 保存刷新后 Handle ID 和 EdgeData 不丢失。
6. 添加 text/number/select/boolean/prompt 字段并编辑值。
7. 删除自定义字段可 Undo；Manifest 字段不可删。
8. 删除有连线端口时明确列出并同步删除边。

### Agent

1. “生成提示词到视频流程”返回合法 WorkflowSpec 2.0。
2. “生成两张图，每张转 3 秒视频再拼接”正确生成 variant fan-out。
3. 所有 Edge 都有 sourceHandle/targetHandle。
4. Agent 不产生未知节点或端口。
5. 非法候选最多修复 2 次，仍失败则返回 errors，不应用。
6. 用户取消 preview 时数据库和画布不变化。
7. 应用使用 expected_version，冲突返回 409。
8. 输出不包含 Key、签名 URL 或绝对路径。

## 10. 里程碑

| 里程碑 | 时间 | 出口 |
|---|---:|---|
| A：连线恢复 | 2-3 天 | 人工默认工作流可完整连线 |
| B：自定义字段 | 1.5-2 周 | 字段/端口添加删除可保存、撤销、迁移 |
| C：Agent 2.0 | 2-3 周 | Prompt 生成完整可验证图，30+ golden cases |

2 人并行预计 3-4 周；单人预计 5-7 周。里程碑 A 完成后重新评估交互工作量。
