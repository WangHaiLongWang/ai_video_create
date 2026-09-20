# ai_video_create 项目状态

> 基线日期：2026-09-20
> 状态版本：11.0
> 代码基线：`b01e63e`
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 评估原则：代码入口、调用链和当前环境可重复测试优先；“已存在代码”不等同于“产品链路已闭环”。

## 1. 执行结论

项目已具备工作流编辑、DAG 执行、多模态 Provider、资产管理、Scene Bundle 和 Agent v2 的主要骨架，当前处于“前端主链收敛与发布门禁修复期”，尚未达到 Release Candidate。

本轮最重要的判断：

- React Flow 的节点拖入、节点移动、命名 Handle、基础连线验证和错误 Toast 已实现，早期“完全无法连线”的主要 DOM 问题已修复。
- 连线基础交互已经补齐 EdgeInspector 和连接 E2E 文件；但本轮尚未运行浏览器套件，连接开始/结束反馈和兼容端口高亮仍需真实浏览器确认。
- 自定义配置字段和端口 CRUD UI 已实现（`PortEditorDialog` 已替代只读占位）；删除端口的关联 Edge 事务、后端 Schema 和 E2E 仍需收口。
- Agent v2 前端已切换到 `/api/agent/generate-preview-v2`，并消费 `compiled_workflow`；仍需验证 apply、expected_version、保存和执行的完整浏览器链路。
- 前后端都有图校验器，但工作流 update、import、execution start 等入口没有统一调用同一个权威 `validate_graph`；当前 Pydantic 模型对带 Handle 的 v2 Edge 直接跳过端口校验。
- 冬季滑雪验收流程的通用建模已明确：1 个逻辑 Scene、2 个图片 variant、每张图生成 3 秒视频、aggregate 后拼接约 6 秒成片。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 91% | API/Engine/Provider/Repository/Scene/Agent 分层完整，共享契约仍分散 |
| React Flow 编辑器 | 88% | 拖拽、连线、EdgeInspector 和 E2E 用例已具备，浏览器实跑与反馈细节待验收 |
| Mock 工作流闭环 | 90% | 执行器能力成熟，浏览器纵向验收和完整门禁不足 |
| 自定义字段/端口 | 82% | 字段和 PortEditorDialog 已实现，服务端契约和删除事务待验收 |
| Workflow Agent | 86% | v2 前端已接入，端到端运行和真实 MiMo 配置仍待验收 |
| Scene/Prompt 产品层 | 82% | SceneEditor、Import/Export UI 和 E2E 已有，API/持久化 roundtrip 待验收 |
| 真实多模态 | 78% | MiMo/Qwen/Wan3 有历史证据，当前环境 FFmpeg/UAT 待复现 |
| 发布工程 | 62% | 前端绿色；后端全量收集、媒体环境和三平台证据未绿 |
| 综合产品完成度 | **约 84%** | 已接近内部 Beta，仍不是 RC |

## 2. 当前可重复测试基线

当前环境：Windows、Node 20.19.0、npm 10.8.2、Python 3.12.3。

| 验证项 | 本轮结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 15 passed / 1 failed；276 passed、1 failed | 未绿；`PropertyPanel` 测试环境缺 `structuredClone` |
| TypeScript | 0 errors | 通过 |
| Vite production build | JS 611.69 kB / gzip 171.00 kB | 通过，有 chunk > 500 kB 警告 |
| Backend 目标回归集 | 276 passed / 4 failed | 未绿；旧 Agent v1 API 测试默认连接 MiMo 外网失败 |
| Backend full collection | 未重跑 | 需在依赖和测试环境修复后执行 |
| Playwright | E2E 文件已新增/扩充，本轮未执行 | 未验证 |
| 三平台 CI | 无同一 commit 的 Windows/macOS/Linux 绿色证据 | 未验证 |

测试结论应区分三类问题：

1. 产品回归：前端有 1 个测试环境失败；typecheck/build 通过。
2. 配置阻断：旧 Agent v1 测试没有 Mock Provider，默认 MiMo 外网不可达。
3. 浏览器证据缺失：E2E 已存在但本轮未执行，不能据此宣称前端闭环。
4. 历史媒体门禁：Pillow/FFmpeg 依赖问题仍需在完整套件中复核。

## 3. 前端与 React Flow 实现评估

### 3.1 已实现

| 能力 | 代码位置 | 评估 |
|---|---|---|
| 节点库点击添加和 HTML DnD 拖入 | `NodePalette.tsx`, `Canvas.tsx` | 已实现 |
| 节点画布拖动、平移、缩放、小地图、删除 | `Canvas.tsx` | 已实现 |
| 多命名 Handle 与端口标签 | `StudioNode.tsx`, `node-manifest.ts` | 已实现基础版 |
| Handle 14px、overflow visible、30%-70% 布局 | `styles.css`, `StudioNode.tsx` | 已修复 |
| 拖线时快速合法性检查 | `Canvas.tsx` `isValidConnection` | 已实现 |
| 类型、方向、基数、自环、重复边、环验证 | `schemas/graph-validation.ts` | 已实现 |
| 非法连接消息状态与 Toast | `store.ts`, `Toast.tsx`, `App.tsx` | 已挂载，需浏览器确认前置拒绝反馈 |
| 配置字段添加/更新/删除/复制/排序 | `PropertyPanel`, `FieldEditorDialog`, `store.ts` | 已实现基础版 |
| Edge 编辑与重连 | `EdgeInspector.tsx`, `store.ts` | 已实现基础版，需 E2E 验证 |
| 端口 CRUD | `PortEditor.tsx`, `PortEditorDialog.tsx`, `store.ts` | 已实现基础版，需关联 Edge 事务验收 |
| Scene 编辑/导入/导出 | `SceneEditor.tsx`, `ImportDialog.tsx`, `ExportDialog.tsx` | 已实现 UI，需 API roundtrip 验收 |
| WorkflowSpec 2.0 与 v1 migration | `schemas/workflow-spec.ts` | 已实现基础版 |

### 3.2 未闭环问题

| 优先级 | 缺口 | 用户影响 | 关闭标准 |
|---:|---|---|---|
| P0 | `isValidConnection` 拒绝后不保证触发 `onConnect`，Toast 可能没有具体原因 | 用户仍感知为“放开后没反应” | `onConnectStart/onConnectEnd` 捕获上下文并显示结构化原因 |
| P0 | 兼容 target 高亮/不兼容端口降暗尚未实跑确认 | 多端口图难连接 | 拖线期间视觉状态 + ARIA 文案 |
| P0 | Playwright 连线矩阵文件已存在但未执行 | 无法证明浏览器真实可用 | 实际运行合法、类型错误、基数、自环、重复、成环、刷新 roundtrip |
| P0 | 后端校验未覆盖所有写入/运行入口 | 非法图可能进入 DB 或执行器 | create/update/import/Agent apply/start 统一权威校验并返回结构化 422 |
| P1 | Port 删除关联 Edge 事务未完成验收 | 可能产生悬空边 | 删除影响确认、同步删除 Edge、Undo |
| P1 | EdgeInspector 已实现但 reconnect/执行语义未验收 | map/aggregate 结果可能不一致 | Edge inspector + reconnect 保留 EdgeData |
| P1 | viewport 未在 `onMoveEnd` 持久化 | 刷新后视图不稳定 | local/API/export roundtrip |
| P1 | 拖动历史缺语义事务 | Undo 体验不稳定 | 一次拖动只产生一个历史项 |
| P2 | 生产 JS 超过 500 kB | 首屏和维护成本上升 | route/panel lazy load 或 manualChunks |

### 3.3 拖拽验收定义

“拖拽功能完成”必须同时满足：

1. 从节点库拖入后，节点出现在指针对应的 flow 坐标；缩放和平移后坐标仍正确。
2. 节点可以移动；移动结束产生一个 Undo 事务并触发可靠保存。
3. 从 source Handle 拖到合法 target Handle 后边立即出现。
4. 非法目标不能落边，并显示稳定错误码与中文原因。
5. 保存、刷新、导出、导入后 node position、viewport、sourceHandle、targetHandle 和 EdgeData 不丢失。
6. 鼠标主路径通过 Playwright；键盘至少可以选择、删除和读取端口错误状态。

## 4. Workflow Agent 评估

### 4.1 已实现的后端能力

- `WorkflowIntent`、alias/port connection 模型。
- Intent compiler 输出带 `sourceHandle/targetHandle` 的 WorkflowSpec。
- Validator-driven repair、repair steps 和调用量估算。
- `/api/agent/generate-preview-v2`、`modify-preview-v2`、`apply-v2`。
- 滑雪场景 variant fan-out 与 aggregate 的通用意图基础。

### 4.2 产品接入缺口

- `AgentComposer` 仍调用旧 `agentGeneratePreview()` / `/agent/generate-preview`。
- 前端 `AgentPreviewResponse` 期待 `spec`，v2 响应实际为 `compiled_workflow`。
- v2 apply 使用 intent，而现有前端 apply 仍使用旧 GraphPatch 或直接 `setWorkflow(spec)`。
- Agent v2 的 prompt 解析当前仍以规则/模板逻辑为主，未证明 MiMo 结构化输出主链。
- 缺前端 API contract tests、30+ 中文 golden cases、Prompt → Preview → Apply → Save → Run 的 Playwright。
- Agent apply 后仍需再次调用权威图校验，不能只依赖 intent validator。

目标链路：

```text
用户 Prompt
  → WorkflowIntent（结构化输出）
  → Node Manifest/Template 工具
  → Compiler 生成 WorkflowSpec 2.0
  → 权威 graph validator
  → 最多 2 次有限修复
  → 布局 + 调用量/成本预估 + diff
  → 用户确认
  → expected_version apply
  → 保存并可直接运行
```

## 5. 后端与数据架构评估

优势：

- API、Engine、Handler、Provider、Repository、Service 边界已经形成。
- NodeResult/ArtifactRef、scene map、retry、external job id、WorkerPool 和资产血缘具备基础。
- MiMo、Qwen Image、Wan3、ComfyUI 和 Mock 按能力分离。
- Scene Bundle、materializer、JSON/Markdown/CSV/Text/Qwen/Wan exporter 已有实现。

主要债务：

1. Node Manifest/validator 前后端双实现，缺共享 fixtures 或代码生成。
2. `WorkflowSpec` 后端 `NodeData` 尚未完整建模 ports/fieldSchema；v2 Handle 边在模型 validator 中被跳过。
3. workflow update body 是裸 `dict`，绕过强类型 WorkflowSpec 校验。
4. execution start 只依赖 compiler，没有显式调用权威 graph validator。
5. Scene Draft 仍为内存实现，重启丢失。
6. migration 缺正式 `schema_migrations` 账本。
7. Provider 设置仍主要以内存和 `.env` 为准，不是多 Provider CRUD。

## 6. 发布阻断清单

| ID | 阻断项 | 优先级 | 关闭标准 |
|---|---|---:|---|
| R0-1 | Pillow 缺失导致完整 pytest 无法收集 | P0 | requirements/lock 声明并在新 venv 完整收集 |
| R0-2 | 两个 `test_agent_api.py` 导致 import mismatch | P0 | 重命名为唯一 basename，完整 pytest 可收集 |
| R0-3 | 后端核心 FFmpeg 7 项未绿 | P0 | 标准终端和 CI 通过；环境不可用时正确 skip 而非异常 |
| R0-4 | React Flow 浏览器连线/拖拽尚未实跑 | P0 | Playwright 核心矩阵全绿并归档 trace/screenshot on failure |
| R0-5 | 图校验未覆盖所有入口 | P0 | create/update/import/Agent/start 一致拒绝非法图 |
| R0-6 | Agent v2 前端已接入但未完成运行验收 | P0 | v2 preview/apply/save/run 浏览器闭环 |
| R0-7 | Scene UI 已有但 API roundtrip 未完成 | P1 | SQLite Draft、Scene Editor、下载导出和 roundtrip E2E |
| R0-8 | 无同一 commit 三平台证据 | P0 | Windows/macOS/Linux CI、Playwright、release-check 全绿 |

## 7. 后续开发路线

### Sprint F0：恢复可信门禁（2-3 天）

- 声明 Pillow/imageio-ffmpeg 或明确系统 FFmpeg 依赖。
- 消除重复测试模块 basename。
- 标准环境运行完整 pytest；归档失败环境、命令和 commit。
- 修复 happy-dom/测试 setup 的 `structuredClone` 缺失。
- 旧 Agent v1 API 测试强制 Mock Provider，不允许默认访问 MiMo 外网。
- 保持 frontend 277 tests、typecheck、build 绿色。

出口：仓库测试可完整收集，环境失败不会被误报为业务成功。

### Sprint F1：React Flow 人工编辑闭环（3-5 天）

- 实现 connect session、端口高亮、非法原因 Toast/inline feedback。
- Edge inspector、mode/label/order、删除与 reconnect。
- viewport 保存和拖动 Undo 事务化。
- 权威后端图校验覆盖所有入口。
- 实跑已有 Playwright：`flow-connection.spec.ts`、`fields-ports.spec.ts`、`execution.spec.ts`。
- 补兼容端口高亮、连接结束反馈和 Edge reconnect。

出口：用户可以稳定地从空画布搭建、保存、重开并运行合法工作流。

### Sprint F2：字段与端口产品化（3-5 天）

- 完成字段 rename 时 config key 迁移、保留字段约束和删除确认。
- 完成 PortEditor 的删除影响分析、悬空 Edge 清理和事务化 Undo。
- 删除端口时列出关联 Edge，并在一个 Undo 事务中更新图。
- 前后端 Schema roundtrip 和浏览器 E2E。

出口：用户自定义字段和端口不会破坏图契约，可撤销、保存和迁移。

### Sprint F3：Workflow Agent v2 前端闭环（3-5 天）

- 已有 v2 API client/type adapter，当前重点是 contract、expected_version 和浏览器验收。
- AgentComposer 展示 intent、repair、validator errors、cost 和 diff。
- apply 使用 intent + expected_version；成功后从服务端重新加载。
- 接入 MiMo 结构化输出与模板 fallback 标识。
- 30+ 中文 golden cases 和 Playwright Prompt → Run。

出口：自然语言能生成合法、可解释、可确认、可保存并可运行的 WorkflowSpec 2.0。

### Sprint F4：Scene/滑雪场景纵向验收与 RC 收敛（5-8 天）

- 1 Scene → 2 Qwen Image variants → 2 个 Wan3 3 秒视频 → FFmpeg aggregate。
- 校验 scene_id + variant_id 血缘、顺序、失败重试、成本提示和最终下载。
- 完成 Scene Draft API roundtrip、导出下载和必要的 Prompt 导出 UI。
- 同一 commit 执行完整 CI、三平台 smoke 和 release-check。

出口：滑雪场景在 Mock 必须 100% 通过，真实 Provider 在已配置环境完成受控 UAT。

## 8. 文档导航

- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- React Flow 与 Agent 细化：[`plans/active/REACT-FLOW-AGENT-PLAN.md`](plans/active/REACT-FLOW-AGENT-PLAN.md)
- Flow 与 Scene 专项：[`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收工作流：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- 系统架构：[`architecture/SYSTEM-DESIGN.md`](architecture/SYSTEM-DESIGN.md)
- Provider 集成：[`integrations/`](integrations/)
- 测试证据：[`reports/`](reports/)

状态文档只记录已验证事实；工单状态以代码、自动测试和可复现验收证据为准。
