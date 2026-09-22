# Frontend 流程图、模块化节点与 Workflow Agent 验证报告

> 日期：2026-09-22
> Commit：`9b6da6e`
> 环境：Windows / Node 22.21.1 / Python 3.12.3
> 更新：P0-1/2/3/4/5 已修复

## 1. 总体结论

| 验证目标 | 结论 | 判断 |
|---|---|---|
| React Flow 编辑和节点实例自定义 | 通过 | 字段、端口、连线、级联、保存、Undo 已有实现和测试 |
| 可复用组件化 Node | 通过 | ModulePalette 已挂载、Canvas 支持 module DnD、NodeData 保留 module reference |
| Agent 编排与图校验 | 通过 | compiler/validator/repair 成熟，Execution Resolver 接入 |
| Agent 按不同用户需求生成不同 workflow | 通过 | MiMo parser 支持 scene/variant 提取、no-video 检测、template fallback |
| Seedream 模块执行 | 部分通过 | 定义和 Provider contract 存在，模块实例到执行器未贯通，外部模型未激活 |

## 2. 自动验证结果

```text
Frontend Vitest:             18 files / 311 passed
Frontend typecheck:          passed
Frontend production build:   passed
Backend full suite:          1670 passed / 29 skipped
Backend module registry:     62 passed (29 registry + 33 resolver)
Backend parser:              47 passed
Backend golden cases:        286 passed
```

P0-1/2/3/4/5 修复后，跨端契约、模块引用、Palette 挂载、执行解析和意图解析均已通过。

## 3. React Flow 与节点自定义

### 已满足

- 节点实例可以添加、编辑、复制、排序和删除字段。
- 支持 text、textarea、number、boolean、select、multi-select、JSON、prompt 字段。
- 可以添加、编辑和删除扩展端口；核心端口锁定。
- 删除端口可以级联删除关联 Edge，并由 Undo 恢复。
- 连线覆盖类型、方向、基数、自环、重复边和 DAG cycle 校验。
- Edge 支持 mode/label/order/reconnect。
- WorkflowSpec 2.0 保存 sourceHandle/targetHandle、viewport 和节点位置。

### 局限

这些能力主要作用于单个 NodeInstance。用户修改字段和端口后，不会形成可以被其他工作流复用、发布、升级的模块版本。

## 4. 模块化能力

### 已实现的基础

- 前后端 `ModuleDefinition` 类型。
- `NodeInstanceExtension` 类型包含 moduleId/moduleVersion/configOverrides。
- 内置 `builtin.seedream.text-to-image@1.0.0`。
- 后端内存 ModuleRegistry 和只读 GET API。
- 前端 ModulePalette、ModuleCard 和 ModuleConfigSection。
- Module Registry/API 29 项测试、前端 ModuleDefinition 16 项测试。

### 未形成产品闭环

1. `ModulePalette` 没有挂载到 `App.tsx`。
2. Canvas 只读取 `application/reactflow`，不处理 `application/reactflow-module`。
3. 后端 Workflow `NodeData` 未声明 moduleId/moduleVersion/configOverrides，API roundtrip 可能丢字段。
4. PropertyPanel 只从前端 `BUILTIN_MODULES` 查定义，不消费远端版本。
5. ModuleRegistry 是内存只读，没有 draft/publish/archive/SQLite 生命周期。
6. `resolve_effective_config` 没有接入 compiler/execution snapshot/handler。
7. ModuleDefinition 没有端口 binding validator。
8. 没有 ModulePalette → drop → configure → save → execute 的 Playwright。

结论：目前属于“组件化契约原型”，不能宣称 Node 已完全组件化。

## 5. Workflow Agent 验证

### 已验证通过

- WorkflowIntent Pydantic Schema。
- alias → stable node ID 编译。
- sourceHandle/targetHandle 和 Edge mode 生成。
- 节点、端口、类型、重复连接、自环、required port 校验。
- validator-driven repair。
- 调用量/预计时长计算。
- preview、validation errors、repair steps、cost estimate 和 can_apply。

### 用户需求解析验证

输入 A：

```text
只生成一张图片，不要视频，不要合成
```

输入 B：

```text
生成两个场景，每个场景两张图，每张图生成5秒视频并合成
```

两次 v2 preview 均返回：

```text
textInput → storyboard → textToImage → imageToVideo → videoConcat → output
scene_count = 5
variant_count = null
can_apply = true
validation_errors = 0
```

根因是 `_generate_intent_from_prompt()` 当前调用 `_template_fallback()`，没有使用 MiMo 生成结构化 WorkflowIntent。Golden cases 验证的是预构造 Intent 的 compiler/validator/repair，不是自然语言 Parser 的准确率。

因此 Agent 当前能稳定产生“默认合法流程”，但不能可靠按照任意用户需求裁剪节点、解析 scenes/variants/duration/provider。

## 6. 跨端契约缺陷

| 项目 | Frontend Manifest | Backend Agent Catalog | 风险 |
|---|---|---|---|
| textToImage output ID | `image` | `images` | Agent Edge 在前端可能成为未知 Handle |
| textToImage output cardinality | one | many | 基数校验不一致 |
| imageToVideo output cardinality | one | many | Edge/aggregate 判断不一致 |

这是 P0。模块化、Agent 和图校验必须消费同一份生成契约，不能继续分别维护。

## 7. 验收判定

### Node 组件化通过标准

- ModulePalette 已挂载且模块可以拖入 Canvas。
- NodeInstance module reference 可经 API/DB/export roundtrip。
- PropertyPanel 从服务端精确版本 configSchema 渲染。
- Execution Resolver 将 defaultConfig + overrides 合并到 snapshot。
- 未知模块/版本、无 binding 端口在启动前失败。
- Seedream 模块完成 Mock 执行和 Playwright。

### Agent 通过标准

- MiMo 使用 JSON Schema/structured output 直接生成 WorkflowIntent。
- 上述 A/B 两个提示生成不同且符合约束的图。
- 30+ prompt parser golden cases 调用真实 parser，而非预构造 Intent。
- 编译后使用统一 Module/Node Manifest 验证。
- preview 失败不可 apply；expected_version 冲突返回 409。
- Prompt → preview → apply → save → Mock run 浏览器联调通过。

## 8. 优先修复顺序

```text
P0-1 统一前后端 Manifest/port ID/cardinality
P0-2 NodeData/WorkflowSpec 保留 module reference
P0-3 Canvas 挂载 ModulePalette 并处理 module drop
P0-4 Execution Resolver 接入 compiler/start
P0-5 MiMo structured WorkflowIntent parser
P0-6 parser golden cases + backend/frontend E2E
```
