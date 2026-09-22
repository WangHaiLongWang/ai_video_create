# 可复用模块化节点与 Seedream 推进计划

> 状态：Active
> 日期：2026-09-22
> 上级计划：[DELIVERY-PLAN.md](DELIVERY-PLAN.md)
> 关联计划：[RC-CLOSURE-PLAN.md](RC-CLOSURE-PLAN.md)、[DOUBAO-SEEDANCE-PLAN.md](DOUBAO-SEEDANCE-PLAN.md)

## 0. 2026-09-22 验证检查点

| 工单/能力 | 状态 | 当前证据 | 下一出口 |
|---|---|---|---|
| MOD-001 ModuleDefinition 契约 | 基础完成 | TS/Pydantic + frontend 16 tests | 共享生成源/fixture |
| MOD-002 内置 Registry/Seedream | 基础完成 | Registry + GET API + backend 29 tests | 前后端单一来源 |
| MOD-003 NodeInstance reference | 类型存在 | NodeInstanceExtension/Pydantic extension | 接入 Workflow NodeData/API/DB roundtrip |
| MOD-004 Schema Property Renderer | 部分完成 | ModuleConfigSection 已存在 | 使用远端版本、组件测试/E2E |
| MOD-005 Execution Resolver | 未接入 | Registry 有 config merge helper | compiler/start/snapshot/handler 接入 |
| MOD-006 Seedream E2E | 未完成 | Contract/Provider 已有 | Palette → drop → config → Mock run |
| Module Palette | 组件存在未挂载 | ModulePalette/ModuleCard 文件存在 | App 挂载 + Canvas module DnD |
| Module 生命周期 | 未实现 | 只有内存只读 GET API | SQLite draft/publish/archive |

专项验证报告：[`frontend-modularity-agent-validation-2026-09-22.md`](../../reports/frontend-modularity-agent-validation-2026-09-22.md)。

## 1. 决策摘要

当前系统已经支持“节点实例级”的自定义字段和端口，但尚未形成真正的“可复用模块系统”。

本计划采用三层模型：

```text
BaseNodeKind（平台执行能力）
  → ModuleDefinition（可复用、版本化组件）
    → NodeInstance（画布实例和局部覆盖）
```

- `BaseNodeKind` 继续由平台白名单控制，如 `textToImage`、`imageToVideo`。
- `ModuleDefinition` 定义名称、图标、字段 Schema、默认配置、Provider 约束、端口展示和版本。
- `NodeInstance` 只保存 `moduleId/moduleVersion`、位置和实例覆盖，不复制整份模块定义。
- v1 不允许用户上传 JavaScript/Python Handler，不执行任意表达式。
- Seedream 作为首个内置模块，复用 `textToImage` Handler，并将 Provider 固定为 `doubao`。

## 2. 当前代码评估

### 2.1 已具备的基础

| 能力 | 代码位置 | 可复用程度 |
|---|---|---|
| Node Manifest 和端口类型 | `frontend/src/schemas/node-manifest.ts`, `backend/app/schemas/node_manifest.py` | 可作为模块契约基础 |
| 自定义字段 Schema/UI | `types.ts`, `FieldEditorDialog.tsx`, `PropertyPanel.tsx` | 可迁移到 ModuleDefinition config schema |
| 自定义端口 CRUD | `PortEditor.tsx`, `PortEditorDialog.tsx`, `store.ts` | 可作为模块设计器 UI 基础 |
| Handler Registry | `backend/app/handlers/__init__.py` | 支持 baseKind 到执行器映射 |
| Provider capability | `providers/base.py`, `real_handlers.py` | Seedream 可直接复用 image capability |
| Agent manifest tools | `agent_tools.py` | 可扩展为模块发现工具 |
| WorkflowSpec 2.0 | 前后端 schema/migration | 可增加 module reference |

### 2.2 当前硬编码点

1. 前端 `NodeKind` 是六项固定 union。
2. `NODE_CATALOG`、`workflow.ts`、`StudioNode.icons`、Agent label map 分别维护节点信息。
3. 后端 `_NODE_CATALOG_V2`、`workflow_factory.NODE_DEFS` 和 Handler registry 再维护一套定义。
4. `configSchema` 已存在于 Manifest 类型，但没有驱动 PropertyPanel；当前 legacy config 只按值类型生成 input。
5. 自定义端口可以写入 WorkflowSpec，但 Handler/Compiler 不理解新增端口的输入输出语义。
6. Compiler 仍以 `kind in (textToImage, imageToVideo)` 和 `config.mapOver` 判断执行行为。
7. Agent 只能从硬编码 Catalog 发现节点，不能发现用户模块或模块版本。

### 2.3 关键风险判断

不能直接把“添加字段/端口”升级为任意执行节点：

- 字段没有 Provider 参数映射时，只是无法消费的 JSON。
- 端口没有 input/output binding 时，会产生看似合法但运行时无效的 Edge。
- 任意 Handler 脚本会引入 RCE、秘密泄露、跨平台和版本兼容风险。
- 模块定义若直接内嵌到每个 Node，会造成升级和差异审计困难。

因此首版模块化必须是“声明式 UI + 白名单执行能力”，不是插件运行时。

## 3. 目标数据模型

### 3.1 ModuleDefinition

```json
{
  "id": "builtin.seedream.text-to-image",
  "version": "1.0.0",
  "status": "published",
  "baseKind": "textToImage",
  "category": "image",
  "label": "Seedream 文生图",
  "description": "使用火山方舟 Seedream 生成图片",
  "icon": "image-square",
  "providerPolicy": {
    "capability": "image",
    "allowed": ["doubao"],
    "default": "doubao",
    "locked": true
  },
  "configSchema": {
    "type": "object",
    "properties": {
      "image_model": {"type": "string", "title": "模型 / Endpoint ID"},
      "size": {"type": "string", "title": "图片尺寸", "default": "1280x720"},
      "negative_prompt": {"type": "string", "format": "textarea"},
      "seed": {"type": "integer", "minimum": -1, "default": -1},
      "watermark": {"type": "boolean", "default": false},
      "variantCount": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1}
    },
    "required": ["image_model"]
  },
  "defaultConfig": {
    "provider": "doubao",
    "image_model": "doubao-seedream-5-0-pro-260628",
    "size": "1280x720",
    "mapOver": true
  },
  "ports": {
    "inputs": [{"id": "scene", "type": "scene", "required": true, "cardinality": "one"}],
    "outputs": [{"id": "image", "type": "image", "required": false, "cardinality": "one"}]
  },
  "execution": {"mapOver": "scene"},
  "metadata": {"builtin": true, "provider": "volcengine"}
}
```

### 3.2 NodeInstance

```json
{
  "id": "seedream-1",
  "type": "studio",
  "position": {"x": 680, "y": 150},
  "data": {
    "kind": "textToImage",
    "moduleId": "builtin.seedream.text-to-image",
    "moduleVersion": "1.0.0",
    "label": "商品主图生成",
    "configOverrides": {
      "size": "1920x1080",
      "seed": 42
    },
    "status": "idle"
  }
}
```

运行前解析：

```text
effectiveConfig = module.defaultConfig
                + workflow/module binding
                + node.configOverrides
                + scheduler scene/variant injection
```

秘密值不允许进入 ModuleDefinition、WorkflowSpec 或导出文件。

### 3.3 端口规则

首版分为两类：

- 核心端口：由 `baseKind` 契约定义，可改 label/排序/可见性，不可改 ID/type/direction。
- 扩展端口：只有存在白名单 binding 时才可执行，例如 `reference_image → config.reference_asset_id`。

没有 binding 的自定义端口只能保存为 draft，发布模块和启动执行时必须返回 `UNBOUND_MODULE_PORT`。

## 4. 模块生命周期

```text
Draft
  → validate
  → publish version 1.0.0（不可变）
  → palette discovery
  → create node instance
  → optional new draft 1.1.0
  → explicit workflow upgrade with diff
  → archive（已有 workflow 仍可解析）
```

规则：

- 已发布版本不可原地修改。
- 删除模块只允许 archive，不能破坏历史工作流。
- 模块升级必须展示字段、端口、Provider 和调用量变化。
- 内置模块可 clone 为用户模块；内置定义不可删除。
- 导入 workflow 时缺失模块应进入 degraded/read-only 状态，不可静默替换。

## 5. 目标架构

```text
ModuleDefinition Repository/API
            │
            ├─ Module Palette / Module Designer
            ├─ Schema-driven Property Renderer
            ├─ Graph Validator + Binding Validator
            ├─ Workflow Agent list_modules tool
            └─ Execution Resolver
                    │
                    └─ baseKind Handler → capability Provider
```

### 单一事实来源

建议新增：

```text
schemas/module-definition.schema.json
schemas/base-node-manifest.json
```

由共享 fixture 或生成脚本产出前端 TypeScript 和后端 Pydantic 映射，逐步替换多份 Catalog。

## 6. 前端产品设计

### 6.1 Module Palette

- 分类：Input、LLM、Image、Video、Transform、Output、My Modules。
- 搜索 label、capability、Provider 和 tag。
- 卡片展示版本、Provider、输入输出端口、预计外部调用。
- 拖入时生成 NodeInstance，而不是复制完整模块定义。

### 6.2 Module Designer

分区：

1. 基本信息：名称、说明、分类、图标、标签。
2. 执行能力：baseKind，只能从白名单选择。
3. Provider Policy：capability、允许列表、默认 Provider、是否锁定。
4. 属性 Schema：字段类型、约束、默认值、帮助文本、高级字段。
5. 端口：核心端口展示覆盖和有 binding 的扩展端口。
6. 预览：节点卡片和 PropertyPanel 实时预览。
7. 校验/发布：错误、warning、版本号、diff 和调用量变化。

### 6.3 Schema-driven PropertyPanel

将当前 `renderFieldValue` 抽成 FieldRenderer Registry：

```text
string/text → TextField
string/textarea → TextareaField
integer/number → NumberField
boolean → SwitchField
enum → SelectField
array enum → MultiSelectField
prompt → PromptEditor
asset reference → AssetPicker
provider/model → ProviderModelPicker
```

字段组件必须支持 validation、disabled/locked、help、default、reset、secret rejection 和错误定位。

## 7. Backend/API 计划

### 数据表

```text
module_definitions
  id, version, status, base_kind, definition_json,
  created_at, updated_at, published_at, archived_at

module_usage
  workflow_id, node_id, module_id, module_version
```

唯一键：`(id, version)`。

### API

```text
GET    /api/modules?status=published&capability=image
POST   /api/modules                         创建 draft
GET    /api/modules/{id}/versions/{version}
PUT    /api/modules/{id}/draft              更新 draft
POST   /api/modules/{id}/validate
POST   /api/modules/{id}/publish
POST   /api/modules/{id}/clone
POST   /api/modules/{id}/archive
POST   /api/workflows/{id}/modules/upgrade  预览/应用升级
```

所有写接口需要 expected_version；错误使用统一结构化 envelope。

### Execution Resolver

编译前执行：

1. 加载精确 module version；
2. 验证 baseKind 和 Provider capability；
3. 合并并校验 effective config；
4. 校验 port binding；
5. 生成不可变 ExecutionSnapshot；
6. Compiler/Handler 只消费解析后的 baseKind/config。

## 8. Seedream 首个纵向模块

### 8.1 范围

模块 ID：`builtin.seedream.text-to-image`。

复用能力：

- baseKind：`textToImage`；
- Handler：`RealTextToImageHandler`；
- Provider：`doubao`；
- Provider method：`generate_image`；
- scene/variant map、AssetManager 和 retry 均复用现有链路。

不新增 `seedream` NodeKind，不复制 Handler。

### 8.2 节点字段

| 字段 | 类型 | 默认值 | 规则 |
|---|---|---|---|
| provider | locked select | doubao | 实例不可改 |
| image_model | ProviderModelPicker | 正式模型/Endpoint | 必填 |
| size | select/text | 1280x720 | Provider 校验 |
| negative_prompt | textarea | 空 | 可由 Scene 覆盖/合并 |
| seed | number | -1 | -1 或非负整数 |
| watermark | boolean | false | — |
| variantCount | number | 1 | 1-4，触发调用量更新 |

API Key 只来自 Provider Settings/secret reference。

### 8.3 当前外部阻断

2026-09-21 验证确认：Key 和模型目录有效，但账号未激活 `doubao-seedream-5-0-pro-260628`。模块可以完成 Mock/Contract/编辑闭环，但真实 UAT 需要先激活模型或填写已运行的 Endpoint ID。

### 8.4 Seedream 验收链

```text
创建 Seedream 模块节点
→ Scene prompt 输入
→ 节点属性覆盖 size/seed/variantCount
→ 运行前调用量预估
→ 生成 1-2 张图片
→ Asset 预览/下载
→ 保存刷新后 module reference 和配置不丢失
→ 模块升级 preview 不破坏旧 workflow
```

## 9. 工单与排期

### Phase M0：契约与 Seedream 薄切片（P0，5-7 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| MOD-001 | 0.5d 剩余 | 前后端从共享 Schema/fixture 生成 | 消除 port/cardinality 漂移 |
| MOD-002 | 0.5d 剩余 | 统一内置 Registry/Seedream definition | 前端不再维护重复 builtin |
| MOD-003 | 1d | NodeData/WorkflowSpec 接入 module reference + migration | API/DB/export roundtrip |
| MOD-004 | 1d 剩余 | Schema-driven Property Renderer 接远端版本 | Seedream 字段正确渲染/校验 |
| MOD-005 | 1d | Execution Resolver 合并 effective config | Handler 收到 doubao/model/size/seed |
| MOD-006 | 1d | 挂载 Palette、module drop、Seedream Playwright | 创建→配置→保存→Mock 执行通过 |

### Phase M1：用户模块设计器（P1，5-7 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| MOD-101 | 1.5d | SQLite migration + repository + optimistic lock | 重启恢复，版本不可变 |
| MOD-102 | 2d | Module Designer 基础信息/字段/Provider Policy | draft 可保存和预览 |
| MOD-103 | 1d | 核心端口覆盖 + binding validator | 无 binding 不可发布 |
| MOD-104 | 1d | Palette 分类/搜索/My Modules | published 模块可拖入 |
| MOD-105 | 1d | clone/publish/archive UI | 生命周期 E2E |

### Phase M2：升级、Agent 与治理（P1，4-6 天）

| ID | 工作量 | 任务 | 验收 |
|---|---:|---|---|
| MOD-201 | 1.5d | 模块升级 diff/兼容检查 | 字段/端口/调用量变化可见 |
| MOD-202 | 1d | Agent `list_modules/get_module` 工具 | Prompt 优先选择已发布模块 |
| MOD-203 | 1d | export/import module dependency | 缺模块进入 degraded 状态 |
| MOD-204 | 1d | secret/SSRF/size/JSON 安全限制 | 安全测试全绿 |
| MOD-205 | 1d | 性能与 100 模块 Palette 基准 | 搜索/加载满足指标 |

预计：2 人 3 周；单人 4-5 周。M0 可独立交付 Seedream 模块价值。

## 10. 测试与验收矩阵

### Contract

- ModuleDefinition 前后端 roundtrip 一致。
- 旧 WorkflowSpec 无 module reference 时正确迁移。
- published version 不可变；archive 不破坏引用。
- Provider capability、字段 Schema、端口 binding 校验一致。

### Frontend

- 新建、编辑、clone、publish、archive 模块。
- 从 My Modules 拖入并生成正确 NodeInstance。
- 字段 validation、默认值、reset、locked、advanced 正确。
- 保存/刷新/导入/导出保持 module ID/version。

### Runtime

- resolver 合并顺序稳定且生成 ExecutionSnapshot。
- 自定义 label/icon 不影响 Handler。
- 无 binding 端口、未知 module/version、禁用 Provider 均在启动前失败。
- 模块升级不自动改变已执行的 snapshot。

### Seedream

- Mock 和 httpx Contract 必须进入 PR 门禁。
- 真实生成必须显式手工/nightly，限制 1 scene、1 variant。
- 未激活模型显示 `MODEL_NOT_ACTIVATED`，不得只显示通用 404。
- 成功后记录 asset、scene_id、variant_id、model/endpoint 和耗时，不记录 Key/URL。

## 11. CI 与发布门禁

:codex-annotation{index="1"}

- 新增 Playwright CI job，同时启动 Mock FastAPI 与 Vite。
- 模块设计器、Seedream 节点创建/配置/保存/Mock 执行进入 Chromium required checks。
- 移除 integration 中的 `|| true`；必选测试失败必须阻断。
- 外部 Seedream UAT 放在 manual/nightly job，使用受限 Secrets 和调用量上限。
- Windows/macOS/Linux 对同一 commit 运行 unit/type/build；Linux 运行 browser/media integration。
- Actions URL、commit SHA、Playwright report 和测试 artifact 写入验收报告。

## 12. Definition of Done

- [ ] Seedream 内置模块无需新增 NodeKind/Handler 即可运行。
- [ ] 用户模块可 draft、publish、clone、archive，发布版本不可变。
- [ ] PropertyPanel 由 configSchema 驱动，不再依赖任意 key/value 推断。
- [ ] 无 binding 的自定义端口不能发布或执行。
- [ ] Workflow 保存精确 module ID/version，可迁移、导入和降级显示。
- [ ] Agent 能发现并选择模块，但不能创建任意执行代码。
- [ ] unit/contract/API/Playwright required checks 全绿，无 `|| true`。
- [ ] 同一 commit 的三平台证据完成归档。
- [ ] Seedream 真实 UAT 在模型激活后通过；激活前保持 External Blocked。

## 13. 明确不做

- 浏览器上传并执行 JavaScript/Python。
- 用户自定义 Docker 镜像或任意网络请求节点。
- 任意表达式/脚本形式的端口映射。
- 模块市场、签名分发、第三方依赖安装。
- 在 WorkflowSpec、ModuleDefinition 或日志中保存 API Key。
