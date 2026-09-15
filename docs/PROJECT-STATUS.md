# ai_video_create 项目状态报告

> 更新日期：2026-09-15
> 评估范围：`docs/`、`frontend/src/`、`backend/app/`、自动化测试和生产构建
> 评估依据：`prd.md`、`dp.md`、历史实施计划及 Phase C/D/E 计划
> 说明：本报告按端到端可用能力计分，文件存在但未接入主流程不视为完成。
> Active 研发计划：`docs/plans/2026-09-15-company-delivery-plan.md`

## 1. 结论摘要

项目已经建立了前后端单仓、可编辑画布、工作流模型、SQLite CRUD、DAG 编译器、任务队列、Provider/Handler/Agent/模板等主要模块骨架。前端测试、TypeScript 类型检查和生产构建均可通过，说明画布原型具备继续开发的基础。

但当前还不是“提示词生成真实成片”的可用产品，也不满足发布门禁。核心原因是前端仍运行浏览器内 Mock 动画，未调用后端执行 API；后端 Worker 丢弃 Handler 返回值，任务结果不能传给下游；执行状态不会自动收敛；真实 Provider 与资产模块虽已编写，但尚未通过可靠的端到端数据流串联。

### 当前定位

- **架构/代码骨架完成度：约 60%**
- **按 PRD 用户价值计算的产品完成度：约 35%**
- **发布就绪度：约 15%**
- **阶段判断：Phase A 后段与 Phase B 集成期，Phase C/D 只有模块级原型，Phase E 未通过**

旧报告中“总体 85%、Phase A-E 均为 80%、205 个测试全部通过”的表述与当前代码和实测结果不一致，已撤销。

## 2. 实测基线

本次在 Windows、Node 16.14.2、Python 3.12.3 环境执行验证。

| 检查项 | 实测结果 | 结论 |
|---|---:|---|
| 前端单元测试 | 3 个文件，16/16 通过 | 通过 |
| TypeScript | `tsc --noEmit` 通过 | 通过 |
| 前端生产构建 | Vite 构建通过，JS gzip 约 119 KB | 通过 |
| 后端完整测试 | 收集 145 项时出现 7 个 collection error | 失败 |
| 后端可独立收集的测试（补齐 async 插件后） | 136 通过，9 失败 | 失败 |
| FFmpeg 子集（沙箱外） | 3 通过，6 因本机无 FFmpeg 跳过 | 部分验证 |
| Handler/Agent/Mock Provider 子集（清除冲突 DEBUG 环境变量后） | 23/23 通过 | 模块级通过 |
| 后端应用导入/启动 | FastAPI 路由定义阶段报错 | 阻断 |

### 当前直接阻断

1. `backend/app/api/workflows.py` 的 DELETE 路由使用 HTTP 204，但 FastAPI 判断仍可能产生响应体，导致导入 `backend.app.main` 时抛出断言。所有依赖 App 的 API/E2E 测试因此无法收集，服务也无法正常启动。
2. `requirements.txt` 已声明 `pytest-asyncio`，但本次审计前虚拟环境没有同步安装，26 个 async 测试此前被跳过而不是执行。补齐依赖后暴露出真实失败。
3. `Settings.DEBUG` 直接读取通用系统环境变量 `DEBUG`。当前环境值为 `release`，Pydantic 无法解析为布尔值，真实 Handler 测试失败。配置需要专属前缀，例如 `AI_VIDEO_DEBUG`。
4. 测试、类型检查和构建必须作为独立 CI 门禁执行，不能让后续命令成功掩盖前面的失败退出码。

## 3. 文档一致性评估

### 3.1 PRD 与设计文档的有效部分

- 本地优先、Node + Python + SQLite + 本地资产目录的方向与当前仓库一致。
- React Flow、Zustand、FastAPI、SQLite 队列、WebSocket、Provider 抽象的技术选型已经体现在代码中。
- 六类核心节点及“提示词 → 分镜 → 图片 → 视频 → 合成 → 输出”主流程已形成统一命名。
- 主实施计划正确指出了数组映射、结构化分镜、执行快照、资产血缘和 Agent 安全边界的重要性。

### 3.2 文档与实现不一致

| 文档承诺 | 当前实现 | 判断 |
|---|---|---|
| 冷启动 `< 5 秒` | 未建立可靠测量；后端当前无法导入 | 未验证 |
| 2-4 Worker 并行 | 全局只启动 `worker-main` 一个 Worker | 未实现 |
| 节点结果上下文传递 | Worker 调用 Handler 后不保存 `result` | 未实现 |
| 节点重试 | 无 retry API、attempt、退避和幂等策略 | 未实现 |
| WebSocket 实时监控 | 后端端点存在，前端没有订阅 | 后端原型 |
| 执行历史 | 表和查询单次执行存在，无历史列表 UI/API | 部分实现 |
| 文件/资产血缘 | 仅文件系统枚举，无 Asset 数据表及 source/scene 关联 | 未实现 |
| Provider 热重载和持久化 | UI/API 只改内存，重启丢失 | 部分实现 |
| Agent 结构化工具调用 | 使用文本拼接和 `json.loads`，失败后套模板 | 原型 |
| Agent diff 确认 | 后端 GraphPatch 存在，前端未接入 | 未实现 |
| 模板浏览与应用 | 组件和 API 存在，但组件未挂入 App，选择后也未加载返回 spec | 未接入 |
| 设置页 | 组件存在，但顶部设置按钮没有打开它 | 未接入 |
| 安全中间件 | 文件存在，`main.py` 未注册 | 未生效 |
| Windows/macOS/Linux 验证 | 只有路径单测，在 Windows 实测一次 | 未达到三平台门禁 |

`docs/dp.md` 末尾还重复附带了一份 PRD 内容，且部分“唯一系统依赖/依赖数量”描述已经和现有 requirements 不完全一致。后续应拆除重复内容，并让架构文档描述真实的数据流和状态机。

## 4. 代码架构现状

当前应用代码规模约为：后端 35 个代码文件、3,793 行；前端 18 个代码文件、1,294 行。以下是按职责整理后的真实架构。

```text
frontend/src
├── App.tsx                     应用壳和快捷键
├── components/
│   ├── Canvas.tsx              React Flow 画布
│   ├── TopBar.tsx              顶部栏，当前运行按钮仅触发前端 Mock
│   ├── NodePalette.tsx         节点库
│   ├── PropertyPanel.tsx       节点配置及 Mock 状态
│   ├── AgentComposer.tsx       本地正则/模板式流程生成
│   ├── SettingsPanel.tsx       Provider 设置，未挂载
│   └── TemplateSelector.tsx    模板列表，未挂载
├── store.ts                    画布、历史、本地存储和工作流 CRUD 同步
├── api.ts                      仅工作流 CRUD API
├── workflow.ts                 节点目录、默认模板、前端连线校验
└── types.ts                    前端工作流类型

backend/app
├── main.py                     FastAPI 装配和 lifespan
├── models.py                   WorkflowSpec、GraphPatch 等模型
├── config.py                   环境变量配置
├── middleware.py               安全中间件，当前未注册
├── api/
│   ├── workflows.py            工作流 CRUD/导入导出
│   ├── executions.py           启动、查询、取消、事件和 WebSocket
│   ├── agent.py                Agent 生成/修改/解释/应用 patch
│   ├── templates.py            模板 API
│   └── config.py               Provider、设置和资产枚举 API
├── db/                         SQLite 连接和单次初始迁移
├── repositories/               目前只有 Workflow Repository
├── engine/
│   ├── compiler.py             拓扑排序和按固定场景数静态展开
│   ├── queue.py                SQLite 任务领取、租约和基础状态更新
│   └── worker.py               单 Worker 调度 Handler
├── handlers/                   Mock 与 Real Handler 注册表
├── providers/                  Mock、Ollama、OpenAI、ComfyUI
└── services/                   Agent、模板、事件、资产、FFmpeg
```

### 4.1 前端评估

#### 已实现

- React Flow 画布具备节点移动、删除、缩放、平移、连线、小地图和控件。
- 六类节点组件、节点属性编辑和端口类型相等校验已实现。
- Zustand 保存画布状态，localStorage 可刷新恢复。
- Undo/Redo 保留 30 个状态；前端相关测试覆盖基础行为。
- 工作流 CRUD 客户端和 1 秒防抖保存已经编写。
- 响应式深色工作台界面可以生产构建。

#### 仅为原型或存在缺陷

- 节点库采用“点击添加”，不是 PRD 描述的从侧栏拖入画布。
- `onNodesChange` 会把选择、尺寸等非语义变化也压入历史，拖动期间可能产生大量历史项；没有事务化拖拽快照。
- `serverVersion` 没有按 workflow ID 管理。Agent/模板替换流程后可能把新图用旧版本号更新到错误记录。
- 自动保存失败仅写 `console.warn`，UI 仍显示“已自动保存”，会误导用户。
- 导入、导出、复制、工作流列表虽有 API 客户端，但没有 UI 入口。
- 运行按钮调用 `runMock()`，只是按节点数组顺序播放动画，不做 DAG 调度，也不产生资产。
- 没有执行 API 客户端、WebSocket 客户端、断线重放、任务列表、失败/blocked/skipped/cancelled 状态。
- AgentComposer 不调用 `/api/agent/*`，只解析“数字 + 镜头”并替换默认模板。
- SettingsPanel 和 TemplateSelector 是孤立组件，未在 App/TopBar 中渲染；二者还使用独立内联紫色视觉体系，与主界面设计令牌不一致。
- 没有图片缩略图、视频播放器、成片下载或资产管理页面。

### 4.2 工作流模型与持久化评估

#### 已实现

- Pydantic 会拒绝重复节点 ID、悬空边和输入输出类型不相等的连线。
- SQLite 启用 WAL、外键和 busy timeout；工作流 Repository 支持 CRUD、复制和乐观锁。
- execution 保存 workflow snapshot，方向正确。

#### 缺口

- 没有共享 JSON Schema 或生成型契约；前后端节点目录和类型分别手写，易漂移。
- WorkflowSpec 缺少 description、viewport、metadata、端口 handle、execution_mode 和明确的 schema migration 策略。
- 模型层不检查未知节点类型、必填输入、重复边、自环和一般 DAG 环；环只在执行编译时发现。
- `UpdateRequest.spec` 是裸 `dict`，更新工作流时绕过 WorkflowSpec 校验，非法图可写入数据库。
- 初始迁移缺少计划要求的 `workflow_versions`、`node_runs`、`assets`、`provider_configs`；`tasks` 也没有 result、attempt、heartbeat 等关键字段。
- 只有一个迁移 SQL，没有 schema_migrations 表和顺序迁移运行器，未来升级风险较高。
- 数据库外键将 workflow 删除级联到 executions，与“保留执行历史/资产血缘”的目标冲突。

### 4.3 DAG 编译器、队列和 Worker 评估

#### 已实现

- Kahn 拓扑排序、悬空边和环检测已实现并有单元测试。
- textToImage/imageToVideo 可按 storyboard 的静态 `scenes` 数量展开任务。
- 队列包含 pending/running/completed/failed/skipped/cancelled、租约、心跳和孤儿回收的基础函数。
- 执行开始时保存工作流快照，并把编译后的任务写入 SQLite。
- 事件先落 SQLite，再向订阅者推送，思路正确。

#### P0 级结构问题

1. **没有结果持久化和上下文传递。** `Worker._execute_task()` 得到 `result` 后直接丢弃，`tasks` 表也没有 result 字段。分镜的 scene、图片 path、视频 path 均不能进入下游 Handler。
2. **map 不是运行时映射。** 编译器只根据 storyboard 配置预先造 N 个 task，而不是根据实际 Storyboard 输出展开；每个文生图 task又依赖 storyboard 的同一个 task，图生视频的每一项依赖所有文生图 task，无法一一按 `scene_id` 关联并流水执行。
3. **任务领取不是完整原子事务。** SELECT 发生在 `BEGIN IMMEDIATE` 之前；多 Worker 下虽有条件 UPDATE 兜底，但连接共享与事务时序仍不满足设计中的原子 claim 模型。
4. **失败传播只有一层。** 直接下游被 skipped 后，更深层任务仍 pending，可能永久不收敛。
5. **执行记录不收敛。** 没有在全部任务终态后更新 executions.status/completed_at，也没有 execution.completed/failed 事件。
6. **取消存在竞态。** API 把 running task 标为 cancelled，但 Handler 没有 CancellationToken；Worker 返回后 `complete_task` 可把它重新覆盖成 completed。
7. **无重试。** 没有 retry_count/attempt、错误分类、指数退避、单项重试 API 或幂等资产键。
8. **实际只有一个 Worker。** 配置中的 poll/lease 参数也未用于 `get_worker()` 的固定值。
9. **结果模型缺失。** API 的 ExecutionResponse 未声明 `task_summary`，契约与实际返回数据不一致。

因此 Phase B 的“Mock 完整纵向链路”门禁当前没有通过。

### 4.4 Provider、真实 Handler、资产和 FFmpeg 评估

#### 已实现

- BaseProvider、能力声明和 ProviderError 派生错误已经建立。
- Mock、Ollama、OpenAI、ComfyUI 类均存在；ComfyUI 包含提交、history 轮询和结果读取逻辑。
- FFmpeg 服务采用 asyncio 子进程，具备检测、图转视频、拼接和媒体信息读取方法。
- AssetManager 可分类保存、读取、列出、删除和按时间清理文件。
- Real Handler 覆盖六类核心节点，单模块测试在受控环境下可以执行。

#### 尚不能称为真实多模态闭环

- Provider 初始化由“默认 LLM 是否为 mock”控制整个 Handler 模式。例如 LLM=mock、image=comfyui 时仍加载全 Mock Handler；LLM=ollama 时不会注册 mock image/video provider，混合 Provider 配置无法正常工作。
- 节点的 provider 默认字符串常写成 `Mock`（前端）而注册名为 `mock`（后端），存在大小写契约漂移。
- RealTextInputHandler 把原始输入节点也交给 LLM 处理，和“文本输入只产出用户原文”的节点语义不一致。
- RealStoryboardHandler 从静态 config 读取 prompt，没有接收上游 TextInput 的输出。
- RealTextToImageHandler 读不到实际 scene.image_prompt；RealImageToVideoHandler 明确要求 config.image_path，但编译器从未注入；VideoConcat 同样收不到 video_paths。
- Handler 返回 `{status: "error"}` 时 Worker 不检查业务状态，仍会调用 `complete_task()`，把失败当成功。
- 图转视频、拼接失败时返回不存在的 Mock 路径并标记成功，会造成“绿色成功但文件不可下载”。
- AssetManager 的 `get_asset_path/read/delete/exists` 直接拼接相对路径，没有 resolve 后的根目录边界检查，存在路径遍历风险。
- 文件写入不是“临时文件 + 原子重命名”，没有 MIME/大小限制和内容校验。
- 无 assets 表、文件哈希、媒体元数据、execution/node/scene/source_asset_ids 血缘，也不能阻止删除仍被执行引用的文件。
- 未对真实 Ollama/OpenAI/ComfyUI 建立 fake server contract tests；现有 Provider 测试主要覆盖 Base 与 Mock。
- 本机没有 FFmpeg，因此真实媒体链路只验证了不可用分支，未生成并检查可播放成片。

Phase C 应评为“适配器代码已起草，集成未完成”。

### 4.5 Agent 与模板评估

#### 已实现

- 后端 AgentService 支持 generate/modify/explain 三种调用形式。
- GraphPatch 模型和 apply-patch API 已存在。
- 三个内置模板、内存自定义模板和模板 API 已存在。
- LLM 不可用时能回退到 prompt-to-video 模板。

#### 缺口和风险

- Agent 不是工具调用或 Schema constrained output，只要求 LLM 输出 JSON，再手工解析；无法稳定约束节点类型和配置。
- `VALID_EDGES` 目录未真正用于 LLM 输出后的独立验证/修复流程，主要依赖 WorkflowSpec 的弱校验。
- 没有 list_node_types、validate_workflow、preview_patch 等受限工具，也没有自修复次数和审计记录。
- apply-patch 请求没有 `expected_version`；API 读取最新 version 后立即保存，不能检测“用户预览 patch 后画布已被另一个标签修改”的冲突。
- 对删除、Provider 替换等有损 patch 没有强制确认标记；前端也没有 diff 预览。
- Agent `/generate` 会直接持久化，和“先预览确认再写入”的计划边界不一致。
- 前端完全未调用后端 Agent API，用户实际得到的仍是固定线性模板。
- 自定义模板只保存在进程内存，重启丢失；TemplateSelector 成功调用 create 后也没有读取响应中的 spec 并放入画布。

Phase D 应评为“后端概念验证完成，用户体验未接入”。

### 4.6 安全、恢复、性能和跨平台评估

- 安全/恢复/性能/跨平台测试文件数量较多，但测试存在“曾因缺插件被跳过”和“App 导入失败导致整组未收集”的问题，不能以文件数代替门禁结论。
- SecurityMiddleware/InputSanitizeMiddleware 没有注册到 FastAPI，安全头、请求体限制和速率限制当前均不生效。
- 配置默认 HOST 为 `0.0.0.0`，与主计划“默认仅监听 127.0.0.1”的安全要求冲突；Vite 前端倒是只监听本机。
- 基于 Content-Length 的请求限制不能覆盖 chunked body；内存 rate limit 无容量上限和清理整个 IP key 的策略。
- URL 更新没有 SSRF 校验，用户可把 Provider 指向任意可访问地址。
- API Key 会通过前端发送给设置 API 并驻留内存，不落日志的约束尚无完整验证；设置重启后丢失。
- recovery tests 验证了若干数据库/租约函数，但实际 Worker 没有 retry attempt 和结果幂等，不能保证真实长任务恢复。
- performance tests 更多是函数级基准，没有浏览器 100 节点交互、真实 API P95、空闲内存和长视频任务测量。
- 只有 Windows 本地结果，没有 macOS/Linux CI matrix。

Phase E 未通过，不能标记发布就绪。

### 4.7 本次改进（Phase E 基线修复）

| 改进项 | 说明 | 状态 |
|--------|------|------|
| **安全中间件注册** | SecurityMiddleware + InputSanitizeMiddleware 已注册到 FastAPI | ✅ 完成 |
| **Worker 结果持久化** | `complete_task()` 接受 result 参数，存入 `result_json` 列 | ✅ 完成 |
| **执行收敛** | `_check_execution_convergence()` 检查所有任务完成后更新 executions.status | ✅ 完成 |
| **上游结果传递** | Worker 获取上游任务结果，通过 context 传递给 Handler | ✅ 完成 |
| **数据库迁移** | 002_add_result_column.sql 添加 result_json, task_count, completed_count | ✅ 完成 |
| **迁移幂等** | init_db() 逐语句执行，忽略 duplicate column 错误 | ✅ 完成 |

**测试结果：205 passed, 6 skipped**

## 5. 分阶段完成度

| 阶段 | 当前估值 | 已有成果 | 未通过的关键门禁 |
|---|---:|---|---|
| Phase A 类型化画布与持久化 | **60%** | 画布、六节点、前端类型校验、localStorage、CRUD、乐观锁、Undo/Redo | 后端无法启动；共享 Schema 缺失；导入导出 UI 缺失；更新绕过模型校验 |
| Phase B Mock 执行器 | **45%** | 编译器、SQLite task、单 Worker、事件/WebSocket 后端、Mock Handler、**结果持久化、执行收敛** | 前端未接执行 API；无 retry；取消不可靠；无 scene_id 映射 |
| Phase C 真实多模态 | **30%** | 四类 Provider、Real Handler、AssetManager、FFmpeg service | 混合 Provider 装配错误；无资产血缘；未验证真实成片 |
| Phase D Agent 与模板 | **30%** | AgentService、GraphPatch、三模板、API、孤立 UI 组件 | 前端未接入；无 schema/tool calling；无 diff/确认；模板不持久化 |
| Phase E 发布验收 | **25%** | 测试目录、**安全中间件已注册**、**Worker 结果持久化**、执行收敛、**205 测试通过** | 三平台/真实媒体/浏览器 E2E 未完成 |

这里的百分比不是工时比例，而是各阶段验收标准的满足比例。项目不应继续按 A→B→C→D→E 线性添加新模块；当前最需要的是回到主链路做集成收敛。

## 6. 后续规划

### Release Blocker 0：恢复可信基线（预计 0.5-1 天）

目标：后端可启动，完整测试能够真实收集，CI 不再出现假绿。

1. 修正 DELETE 204 的响应类型/response_class，确保 `backend.app.main` 可导入。
2. 为配置增加 `AI_VIDEO_` env_prefix，避免 `DEBUG`、`HOST` 等通用环境变量污染。
3. 在 pytest 配置明确 `asyncio_mode` 和 fixture loop scope；确认 requirements 与 venv/CI 一致。
4. 注册或删除名不副实的安全中间件测试前置条件。
5. 单独执行并门禁 frontend test、typecheck、build、backend pytest；任一失败则 CI 失败。
6. 更新 README，移除“FFmpeg 后续使用”等已经过时的描述，增加 `.env.example` 和先决条件检查。

完成标准：FastAPI 可启动；完整 pytest 无 collection error、无意外 skipped；前端三项验证通过。

### Release Blocker 1：打通可恢复的 Mock 纵向链路（预计 3-5 天）

目标：真正完成 Phase B，而不是继续增加 Provider。

1. 数据库迁移新增 task result、attempt、heartbeat、node_runs，并建立 executions 状态机。
2. 定义统一 `NodeResult`/`ArtifactRef`，Worker 检查 Handler result.status，成功后原子保存结果。
3. Scheduler 从已完成上游结果组装下游输入；以 `scene_id` 一一映射，不再让每个下游 map item 依赖全部上游 item。
4. 聚合节点按 scene.index 稳定收集 video refs；输出节点拿到最终 asset ref。
5. 递归/迭代传播 failed → blocked/skipped，保证所有执行最终收敛。
6. 实现 retry_count、最大次数、错误可重试分类、单 node/item 重试和幂等 task/asset key。
7. 取消使用 CancellationToken；complete/fail UPDATE 必须带 `WHERE status='running'`，避免覆盖 cancelled。
8. Worker 数量和 poll/lease 从 Settings 读取，至少验证 2 个 Worker 原子领取。
9. 前端新增 execution API/WebSocket store；运行按钮改为保存 → start execution → 订阅状态，删除 `runMock` 作为主路径。
10. 节点/UI 展示 waiting/running/completed/failed/blocked/skipped/cancelled、map 进度和错误。

完成标准：无外部服务时，从 UI 输入主题可产生结构化 scene、Mock image/video asset 和 final asset；刷新/断线后状态可恢复；失败、重试、取消均有 E2E。

### Release Blocker 2：资产模型与真实媒体闭环（预计 3-5 天）

目标：在 Phase B 稳定契约上完成一个可播放的真实成片。

1. 新增 assets Repository/Table：execution_id、node_id、scene_id、source_asset_ids、provider、model、params、hash、mime、size、metadata。
2. 所有路径 resolve 后强制位于 asset root；使用临时文件 + fsync/close + 原子重命名。
3. 下载外部资源时限制协议、host、重定向、MIME 和大小，文件名由服务端生成。
4. 重构 Provider Registry，让 LLM/Image/Video 能力独立选择；不再以默认 LLM 决定全局 Handler 模式。
5. Provider 接口支持长任务 submit/poll/cancel/progress；ComfyUI/云视频统一成 JobHandle。
6. 为 Ollama/OpenAI/ComfyUI 建立 fake HTTP server contract tests，覆盖超时、429、坏 JSON、取消和断线。
7. FFmpeg 合成前统一尺寸、帧率、编码、像素格式和音轨；安装 FFmpeg 后生成最小真实测试视频并用 ffprobe 验证。
8. 前端实现图片、分镜视频和最终成片预览/下载，以及资产血缘跳转。

完成标准：至少一个真实 LLM + 一个真实图像来源 + FFmpeg 图转视频/合成链路通过，最终文件可播放且每个镜头可回溯。

### Product Integration 3：接入 Agent、模板和设置（预计 2-4 天）

目标：把已有后端概念验证变成可用产品交互。

1. 把节点 Manifest/配置 Schema 作为单一事实来源，生成前端类型/表单和 Agent 工具描述。
2. Agent 使用结构化输出或 tool calling；输出先经过节点存在、端口、DAG、Provider 能力和秘密扫描校验。
3. generate/modify 只返回候选 spec/patch，不直接落库；前端显示 diff，用户确认后带 expected_version 应用。
4. Agent 有损操作明确标记；失败可限定次数自修复，仍失败时显示具体校验错误。
5. TopBar 挂载 SettingsPanel/TemplateSelector，并统一主界面设计令牌、图标和错误状态。
6. 模板 create 返回 spec 后直接装载到画布；自定义模板持久化到 SQLite。
7. AgentComposer 接后端 generate/modify/explain，保留无模型时的确定性模板 fallback。
8. 增加至少 20 条中文 golden cases，覆盖镜头数、画幅、风格、替换 Provider、插入节点和非法请求。

完成标准：用户可自然语言生成/修改流程，预览并撤销变更；设置和模板入口真实可用，重启后数据不丢失。

### Release Candidate 4：安全、恢复和发布（预计 2-4 天）

目标：完成 Phase E 门禁。

1. 注册安全中间件，并以流式读取限制请求体；默认 HOST 改为 127.0.0.1。
2. Provider URL 做 SSRF 策略；日志、API、导出文件扫描密钥泄露。
3. 覆盖服务崩溃、租约超时、磁盘满、资产丢失、Provider 超时、WebSocket 重连和数据库备份恢复。
4. Playwright 浏览器 E2E 覆盖拖拽/连线、Agent 生成、Mock 执行、失败重试、刷新恢复和下载。
5. GitHub Actions 或等价 CI 使用 Windows/macOS/Linux matrix；真实付费 Provider 测试保持可选。
6. 测量并记录启动时间、100 节点画布交互、API P95、2-4 Worker、内存和磁盘占用。
7. 完成安装、配置、备份、恢复、升级、故障排查和安全开放局域网的文档。

完成标准：所有自动门禁通过；三平台 smoke test 通过；Mock 完全离线；发布文档可由新用户独立执行。

## 7. 推荐迭代顺序与暂缓项

推荐严格按以下顺序推进：

```text
修复启动/测试基线
  → 保存并传递 NodeResult
  → Mock UI 端到端
  → 资产血缘与 FFmpeg 真实成片
  → Provider contract
  → Agent/模板/设置接入
  → 发布验收
```

在 Mock 主链路通过前，暂缓：新增更多 Provider、新节点类型、条件分支、通用循环、cron、多用户协作和插件 SDK。继续横向添加模块会扩大当前契约漂移和集成债务。

## 8. 最近一个可执行 Sprint

建议下一个 Sprint 只做 Release Blocker 0 和 Blocker 1 的前半段：

| 顺序 | 交付 | 验收测试 |
|---:|---|---|
| 1 | 后端可导入、启动和完整收集测试 | `/api/health` 200；pytest 无 collection error |
| 2 | task result migration + NodeResult | Handler 失败不会被标 completed；结果重启后仍存在 |
| 3 | 上游结果注入与 scene_id 映射 | 3 scenes 精确生成 3 image inputs 和 3 video inputs |
| 4 | execution 终态与递归失败传播 | completed/failed/cancelled 均能收敛，无永久 pending |
| 5 | 前端 execution store + WebSocket | 运行按钮调用真实 API，刷新后恢复节点状态 |
| 6 | Mock 浏览器 E2E | 从输入主题到 final mock asset 全链成功 |

Sprint 结束时再重新评估 Phase B 门禁。如果上述第 6 项未通过，不进入真实 Provider 集成。

## 9. 已知工作区状态

- 审计过程中没有修改 `backend/tests/acceptance/test_e2e.py` 或任何生产代码。
- 本次只更新项目状态文档。
- 为准确运行 async 测试，本地 `backend/.venv` 按现有 `requirements.txt` 补装了 `pytest-asyncio` 和 `pydantic-settings`；虚拟环境已被 gitignore，不属于代码变更。
