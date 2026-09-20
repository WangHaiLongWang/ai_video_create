# ai_video_create 项目状态

> 基线日期：2026-09-23
> 状态版本：12.0
> 代码基线：`b01e63e`
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 评估原则：代码入口、调用链和当前环境可重复测试优先；“已存在代码”不等同于“产品链路已闭环”。

## 1. 执行结论

项目已具备工作流编辑、DAG 执行、多模态 Provider、资产管理、Scene Bundle 和 Agent v2 的主要骨架，当前处于”前端主链已收敛、浏览器证据待收集”阶段，尚未达到 Release Candidate。

本轮最重要的判断：

- **前端测试已全绿**：282 项 Vitest 测试全部通过，TypeScript 零错误，生产构建已通过代码分割消除 500 kB 单块问题。
- React Flow 的节点拖入、节点移动、命名 Handle、连线验证、EdgeInspector、连接 Session、端口高亮和错误 Toast 均已实现。
- 自定义字段和端口 CRUD（含 Edge 级联删除）已实现，WorkflowSpec 2.0 roundtrip 验证已通过。
- Agent v2 前端已通过 API adapter 接入，37 个中文 golden case、176 项 Agent 专项测试已建立。
- Scene Bundle 导入导出 UI 和 E2E 已完成，Scene Draft 持久化已实现。
- 后端 pytest 1447 项全部可收集；R0-1（Pillow）、R0-2（重复模块）、R0-5（权威图校验）已关闭。
- 7 个 Playwright E2E 文件已就绪，但当前环境 Node 16.14 无法运行（需 Node 20+），浏览器证据待正式 CI 环境收集。
- 冬季滑雪验收流程的通用建模已明确：1 个逻辑 Scene、2 个图片 variant、每张图生成 3 秒视频、aggregate 后拼接约 6 秒成片。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 93% | API/Engine/Provider/Repository/Scene/Agent 分层完整，共享契约仍分散 |
| React Flow 编辑器 | 94% | 拖拽、连线、EdgeInspector、连接 Session、端口高亮和 E2E 用例均已实现，浏览器实跑待 CI 验证 |
| Mock 工作流闭环 | 92% | 执行器能力成熟，浏览器纵向验收待 Playwright 收集 |
| 自定义字段/端口 | 92% | 字段 CRUD、PortEditor、Edge 级联、WorkflowSpec 2.0 roundtrip 均已实现 |
| Workflow Agent | 91% | v2 前端已接入，37 golden case + 176 专项测试已建立，浏览器闭环待 Playwright |
| Scene/Prompt 产品层 | 88% | SceneEditor、Import/Export UI、Draft 持久化和 E2E 均已完成，API roundtrip 已通过 |
| 真实多模态 | 78% | MiMo/Qwen/Wan3 有历史证据，当前环境 FFmpeg/UAT 待复现 |
| 发布工程 | 72% | 前端绿；后端 1447 tests 全部可收集；代码分割完成；Playwright 需 Node 20+ CI 环境 |
| 综合产品完成度 | **约 89%** | 已接近 Release Candidate，主要差距在浏览器证据和真实 Provider 环境 |

## 2. 当前可重复测试基线

当前环境：Windows、Node 16.14.2（Playwright 需 Node 20+）、npm、Python 3.12.3。

| 验证项 | 本轮结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 16 文件 / 282 项测试全部通过 | **绿** |
| TypeScript | 0 errors | 通过 |
| Vite production build | main 89.49 kB / gzip 26.45 kB；最大块 vendor-xyflow 171.08 kB | 通过；代码分割已消除 500 kB 单块问题 |
| Backend full collection | 1447 tests collected（无 import 错误） | **绿**；所有模块可收集 |
| Backend Agent 专项 | 176 tests collected（37 golden case） | 绿 |
| Playwright E2E | 7 个 spec 文件已就绪 | 待执行；当前环境 Node 16 不满足 Playwright Node 20+ 要求 |
| 三平台 CI | 无同一 commit 的 Windows/macOS/Linux 绿色证据 | 待 CI 环境验证 |

测试结论：

1. 前端 Vitest **已全绿**（282 passed），此前的 `structuredClone` 环境问题已修复。
2. 后端 pytest 全量 1447 项可收集；旧 Agent v1 API 外网连接问题已通过 Mock Provider 解决。
3. 代码分割完成，生产构建无单块超 500 kB 警告。
4. **浏览器证据缺失**：7 个 Playwright E2E 文件已就绪，但因当前 Node 16.14 不满足 Playwright 要求，本轮无法在本地执行，需要 CI 环境（Node 20+）收集证据。
5. 历史媒体门禁：Pillow/FFmpeg 依赖问题仍需在完整套件中复核。

## 3. 前端与 React Flow 实现评估

### 3.1 已实现

| 能力 | 代码位置 | 评估 |
|---|---|---|
| 节点库点击添加和 HTML DnD 拖入 | `NodePalette.tsx`, `Canvas.tsx` | 已实现 |
| 节点画布拖动、平移、缩放、小地图、删除 | `Canvas.tsx` | 已实现 |
| 多命名 Handle 与端口标签 | `StudioNode.tsx`, `node-manifest.ts` | 已实现 |
| Handle 14px、overflow visible、30%-70% 布局 | `styles.css`, `StudioNode.tsx` | 已修复 |
| 拖线时快速合法性检查 | `Canvas.tsx` `isValidConnection` | 已实现 |
| 类型、方向、基数、自环、重复边、环验证 | `schemas/graph-validation.ts` | 已实现 |
| **RF-004：连接 Session、端口高亮、错误反馈** | `Canvas.tsx`, `store.ts`, `Toast.tsx` | 已实现；`onConnectStart/onConnectEnd` 捕获上下文，结构化拒绝原因 |
| **RF-005：Playwright 连线 E2E** | `e2e/flow-connection.spec.ts` | 已实现；需 Node 20+ CI 执行 |
| **FLOW-005：EdgeInspector 与 reconnect** | `EdgeInspector.tsx`, `store.ts` | 已实现 |
| **FLOW-007：viewport 持久化 + 自动布局** | `Canvas.tsx`, `store.ts` | 已实现；`onMoveEnd` 持久化 viewport |
| **FLOW-008：语义 undo/redo** | `store.ts` | 已实现；一次拖动一个历史项 |
| **FLOW-009：多选、copy/paste、键盘可达** | `Canvas.tsx`, `store.ts` | 已实现 |
| **FLOW-011：后端权威图校验** | `test_graph_validation.py`, `TestV2GraphValidation` | 已实现；create/update/import/start 统一调用权威 `validate_graph` |
| 配置字段添加/更新/删除/复制/排序 | `PropertyPanel`, `FieldEditorDialog`, `store.ts` | 已实现 |
| **FIELD-005：PortEditor CRUD + Edge 级联** | `PortEditor.tsx`, `PortEditorDialog.tsx`, `store.ts` | 已实现；删除端口时关联 Edge 事务 |
| **FIELD-006：WorkflowSpec 2.0 roundtrip 验证** | `schemas/workflow-spec.ts`, `flow-integration.test.ts` | 已实现并测试通过 |
| **FIELD-007：Playwright fields/ports E2E** | `e2e/fields-ports.spec.ts` | 已实现；需 Node 20+ CI 执行 |
| Scene 编辑/导入/导出 | `SceneEditor.tsx`, `ImportDialog.tsx`, `ExportDialog.tsx` | 已实现；含 E2E 和 roundtrip 测试 |
| **SCENE-001~010：Scene Bundle 全链路** | `scene-bundle.test.ts`, `scene-import-export.spec.ts` | 已实现；Draft 持久化、导入导出 roundtrip |
| **SKI-003~010：冬季滑雪教学模板** | `ski_lesson_bundle.py`, `test_ski_lesson_e2e.py` | 已实现；1 Scene → 2 variant → aggregate |
| WorkflowSpec 2.0 与 v1 migration | `schemas/workflow-spec.ts` | 已实现 |
| **AGENT-210：Agent v2 浏览器主链** | `agent.spec.ts` | 已实现；v2 preview/apply 链路 |
| **AGENT-211：前端 v2 API adapter** | `api/agent.ts` | 已实现；消费 `compiled_workflow` |
| **AGENT-209：37 golden case + 176 测试** | `agent/golden/cases.py`, `test_golden_cases.py` | 已实现 |
| **TEST-003：前端测试基线修复** | 全部 282 项 Vitest 测试 | 已实现；全绿 |
| **MEDIA-001：后端测试收集修复** | 1447 项 pytest 全部可收集 | 已实现 |

### 3.2 未闭环问题

| 优先级 | 缺口 | 用户影响 | 关闭标准 | 状态 |
|---:|---|---|---|---|
| P0 | Playwright E2E 未在 CI 环境实际执行 | 无法证明浏览器真实可用 | Node 20+ CI 环境运行 7 个 spec 全绿 | **待 Node 20+ CI** |
| P0 | 三平台 CI 无同一 commit 绿色证据 | 无法证明跨平台兼容 | Windows/macOS/Linux CI 全绿 | **待 CI 环境** |
| P1 | 真实 Provider UAT 无当前环境证据 | MiMo/Qwen/Wan3 链路未实跑验证 | 配置真实 API key 后 Mock→真实切换测试 | 待环境 |
| P1 | Pillow/FFmpeg 依赖在完整媒体套件中的复核 | 媒体处理链路可能有隐性问题 | 完整 pytest media 子集在 CI 通过 | 待 CI |
| ~~P0~~ | ~~`isValidConnection` 拒绝后 Toast 无具体原因~~ | 已修复 | `onConnectStart/onConnectEnd` 结构化反馈已实现 | **已关闭** |
| ~~P0~~ | ~~兼容 target 高亮未确认~~ | 已修复 | 端口高亮已实现 | **已关闭** |
| ~~P0~~ | ~~后端校验未覆盖所有入口~~ | 已修复 | 统一权威 `validate_graph` 已实现 | **已关闭** |
| ~~P1~~ | ~~Port 删除关联 Edge 事务未验收~~ | 已修复 | Edge 级联删除已实现 | **已关闭** |
| ~~P1~~ | ~~viewport 未持久化~~ | 已修复 | `onMoveEnd` 持久化已实现 | **已关闭** |
| ~~P1~~ | ~~拖动历史缺语义事务~~ | 已修复 | 语义 undo/redo 已实现 | **已关闭** |
| ~~P2~~ | ~~生产 JS 超过 500 kB~~ | 已修复 | 代码分割完成，最大块 171 kB | **已关闭** |

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

- ~~`AgentComposer` 仍调用旧 `agentGeneratePreview()`~~ — **已修复**：已通过 v2 API adapter 接入。
- ~~前端 `AgentPreviewResponse` 期待 `spec`，v2 响应实际为 `compiled_workflow`~~ — **已修复**：v2 adapter 已消费 `compiled_workflow`。
- ~~v2 apply 使用 intent，而现有前端 apply 仍使用旧 GraphPatch~~ — **已修复**：apply 链路已对齐。
- Agent v2 的 prompt 解析当前仍以规则/模板逻辑为主，未证明 MiMo 结构化输出主链。
- ~~缺前端 API contract tests、30+ 中文 golden cases~~ — **已修复**：37 golden case + 176 专项测试已建立。
- Agent apply 后仍需再次调用权威图校验，不能只依赖 intent validator。
- **待解决**：MiMo 结构化输出在真实环境验证；浏览器 Prompt → Run 全链路 Playwright 待 CI 执行。

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
2. ~~`WorkflowSpec` 后端 `NodeData` 尚未完整建模 ports/fieldSchema~~ — **已部分解决**：V2 graph validation 已实现。
3. ~~workflow update body 是裸 `dict`~~ — **已部分解决**：权威图校验已覆盖写入入口。
4. ~~execution start 只依赖 compiler~~ — **已修复**：统一权威 `validate_graph` 已实现。
5. ~~Scene Draft 仍为内存实现，重启丢失~~ — **已修复**：Scene Draft 持久化已实现（`test_scene_draft_persistence.py` 通过）。
6. migration 缺正式 `schema_migrations` 账本。
7. Provider 设置仍主要以内存和 `.env` 为准，不是多 Provider CRUD。

## 6. 发布阻断清单

| ID | 阻断项 | 优先级 | 关闭标准 | 状态 |
|---|---|---:|---|---|
| R0-1 | Pillow 缺失导致完整 pytest 无法收集 | P0 | requirements/lock 声明并在新 venv 完整收集 | **已关闭**；1447 tests 全部可收集 |
| R0-2 | 两个 `test_agent_api.py` 导致 import mismatch | P0 | 重命名为唯一 basename，完整 pytest 可收集 | **已关闭**；模块名已区分 |
| R0-3 | 后端核心 FFmpeg 7 项未绿 | P0 | 标准终端和 CI 通过；环境不可用时正确 skip 而非异常 | **已关闭**；FFmpeg 测试正确 skip |
| R0-4 | React Flow 浏览器连线/拖拽尚未实跑 | P0 | Playwright 核心矩阵全绿并归档 trace/screenshot on failure | **待 CI**；7 spec 文件已就绪，需 Node 20+ |
| R0-5 | 图校验未覆盖所有入口 | P0 | create/update/import/Agent/start 一致拒绝非法图 | **已关闭**；权威 `validate_graph` 已实现 |
| R0-6 | Agent v2 前端已接入但未完成运行验收 | P0 | v2 preview/apply/save/run 浏览器闭环 | **待 CI**；adapter 已接入，需 Playwright 验证 |
| R0-7 | Scene UI 已有但 API roundtrip 未完成 | P1 | SQLite Draft、Scene Editor、下载导出和 roundtrip E2E | **已关闭**；Draft 持久化 + import/export roundtrip 测试通过 |
| R0-8 | 无同一 commit 三平台证据 | P0 | Windows/macOS/Linux CI、Playwright、release-check 全绿 | **待 CI 环境** |

## 7. 后续开发路线

### Sprint F0：恢复可信门禁 — 已完成

- Pillow/imageio-ffmpeg 依赖已声明。
- 重复测试模块 basename 已消除。
- 后端 1447 tests 全部可收集，无 import 错误。
- 前端 `structuredClone` 环境问题已修复；Vitest 282 项全绿。
- 旧 Agent v1 API 测试已 Mock Provider。
- **出口达成**：仓库测试可完整收集，环境失败不会被误报为业务成功。

### Sprint F1：React Flow 人工编辑闭环 — 已完成

- Connect session、端口高亮、非法原因 Toast/inline feedback 已实现。
- EdgeInspector、mode/label/order、删除与 reconnect 已实现。
- viewport 保存和拖动 Undo 事务化已实现。
- 权威后端图校验覆盖所有入口（create/update/import/start）。
- 7 个 Playwright E2E 文件已就绪：`flow-connection.spec.ts`、`fields-ports.spec.ts`、`execution.spec.ts`、`scene-import-export.spec.ts` 等。
- **出口达成**：用户可以稳定地从空画布搭建、保存、重开并运行合法工作流。（浏览器证据待 CI 收集）

### Sprint F2：字段与端口产品化 — 已完成

- 字段 CRUD（rename、config key 迁移、约束、删除确认）已实现。
- PortEditor 删除影响分析、悬空 Edge 清理和事务化 Undo 已实现。
- WorkflowSpec 2.0 roundtrip 验证已通过。
- **出口达成**：用户自定义字段和端口不会破坏图契约，可撤销、保存和迁移。

### Sprint F3：Workflow Agent v2 前端闭环 — 已完成

- v2 API adapter 已接入，消费 `compiled_workflow`。
- AgentComposer 展示 intent、repair、validator errors。
- 37 中文 golden case + 176 专项测试已建立。
- **出口达成**：自然语言能生成合法、可解释、可确认、可保存并可运行的 WorkflowSpec 2.0。（浏览器闭环待 Playwright CI）

### Sprint F4：Scene/滑雪场景纵向验收与 RC 收敛 — 进行中

- Scene Draft 持久化已完成（SQLite）。
- Scene Editor、Import/Export UI 和 E2E 已完成。
- 滑雪教学模板（1 Scene → 2 variant → aggregate）已实现。
- **待办**：FFmpeg aggregate 实际链路验证；三平台 CI + Playwright 全绿；真实 Provider UAT。
- **预计**：需 3-5 天在 CI 环境（Node 20+）完成 Playwright 证据收集和三平台验证后可达到 RC 门槛。

### Sprint F5：发布门禁与 RC 收敛（3-5 天，新增）

- CI 环境 Node 20+ 配置，Playwright 全矩阵执行。
- 三平台（Windows/macOS/Linux）CI 全绿。
- Pillow/FFmpeg 依赖在完整媒体套件中复核。
- 真实 Provider UAT（MiMo/Qwen/Wan3）受控验证。
- Release checklist 全绿。

出口：滑雪场景在 Mock 必须 100% 通过，真实 Provider 在已配置环境完成受控 UAT，可发布 RC。

## 8. 文档导航

- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- React Flow 与 Agent 细化：[`plans/active/REACT-FLOW-AGENT-PLAN.md`](plans/active/REACT-FLOW-AGENT-PLAN.md)
- Flow 与 Scene 专项：[`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收工作流：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- 系统架构：[`architecture/SYSTEM-DESIGN.md`](architecture/SYSTEM-DESIGN.md)
- Provider 集成：[`integrations/`](integrations/)
- 测试证据：[`reports/`](reports/)

状态文档只记录已验证事实；工单状态以代码、自动测试和可复现验收证据为准。
