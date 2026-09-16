# ai_video_create 项目状态

> 基线日期：2026-09-16
> 状态版本：7.0
> Active 计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 评估原则：只采用当前环境可重复结果；历史报告单独列为证据，不替代当前门禁。

## 1. 结论

项目已完成主要产品模块和执行器骨架，处于“内部验收前的集成收敛期”，不是可发布 RC。

已经具备：

- React Flow 工作流编辑与持久化；
- NodeResult/ArtifactRef、scene map、Scheduler、RetryPolicy、WorkerPool；
- REST + WebSocket 执行监控；
- MiMo、Qwen Image、Wan3、ComfyUI、OpenAI、Ollama、Mock Provider；
- Agent preview/diff 和模板装载；
- Asset/Template 数据表与 API；
- Wan3 与 FFmpeg 的独立验收报告；
- GitHub Actions、Playwright 和 release-check 基础设施。

当前发布门禁仍是红色，原因集中在工具链和可复现性：

1. Vitest 会误收集 Playwright E2E，导致 `npm test` 退出。
2. TypeScript 测试 Location mock 有类型错误，导致 typecheck/build 失败。
3. 当前 Node 16.14.2 无法运行要求 Node 20+ 的 Playwright。
4. Wan3 UAT 依赖 Pillow，但 requirements 未声明，完整后端测试收集失败。
5. FFmpeg 报告使用另一个 Python 的 imageio-ffmpeg；当前 venv 和配置无法复现，7 项集成测试失败。
6. CI 对 lint、mypy 和 integration 使用 `|| true`，失败不会阻断合并。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 85% | 分层已形成，契约/迁移仍需治理 |
| Mock 用户链路 | 80% | 后端全链测试存在，浏览器门禁未运行 |
| 真实多模态 | 75% | MiMo/Qwen/Wan3 有真实证据，FFmpeg 当前不可复现 |
| Agent 与模板 | 75% | preview/diff/装载已接入，结构化工具与持久设置待完善 |
| 发布工程 | 45% | CI/E2E 文件存在，但当前门禁本身失败或吞错 |
| 综合产品完成度 | **约 70%** | 可内部联调，不应标记 RC 或发布 |

## 2. 当前可重复测试基线

当前本机：Windows、Node 16.14.2、npm 8.5.0、Python 3.12.3。

| 验证项 | 结果 | 状态 |
|---|---:|---|
| 前端指定单元测试文件 | 63 passed | 通过 |
| 根 `npm test` | Vitest 误收集 Playwright，Unexpected Exit | 失败 |
| TypeScript | 2 errors in `executionSocket.test.ts` | 失败 |
| Vite production build | 被相同 TypeScript errors 阻断 | 失败 |
| 后端核心（排除 integration） | 383 passed、6 skipped | 通过 |
| 后端排除 Wan3 UAT | 427 passed、7 failed、6 skipped | 失败 |
| 后端完整测试 | Pillow 缺失，收集失败 | 失败 |
| FFmpeg integration | 7 failed（当前配置找不到 ffmpeg） | 失败 |
| Playwright | Node 16；要求 Node 20+ | 未运行 |
| MiMo 真实 Chat | HTTP 200、`finish_reason=stop` | 历史实测通过 |
| Qwen Image 真实 T2I | 1280×720 PNG | 历史实测通过 |
| Wan3 真实 UAT | 报告记录 16/16 | 历史环境通过，当前 venv 不可复现 |
| FFmpeg UAT | 报告记录 19/19 | 历史环境通过，当前 venv 不可复现 |

### 报告可追溯性说明

- [`reports/wan3-uat.md`](reports/wan3-uat.md) 记录了真实 Wan3 任务和 MP4 下载。
- [`reports/ffmpeg-integration.md`](reports/ffmpeg-integration.md) 使用系统外另一个 Python 环境中的 imageio-ffmpeg。
- 两份报告日期为 2026-09-17，晚于当前基线日期 2026-09-16；应由报告作者确认日期并补充 commit、环境锁文件和原始测试输出。

## 3. 默认运行配置

```text
LLM       openai_compat / Xiaomi MiMo / mimo-v2.5-pro
Image     dashscope / qwen-image-3.0 / 1280x720
Video     wan3 / wan3.0-video / 480P / adaptive / 5s
Local     ComfyUI 可选（img2vid workflow 仍需真实节点模板）
Storage   data/assets
Database  data/ai_video_create.db
Host      127.0.0.1
```

配置与 Provider 说明：

- [`integrations/mimo-v2.5-pro.md`](integrations/mimo-v2.5-pro.md)
- [`integrations/qwen-image-3.0.md`](integrations/qwen-image-3.0.md)
- [`integrations/wan3-video.md`](integrations/wan3-video.md)

## 4. 功能完成矩阵

### 4.1 编辑器与工作流

| 能力 | 状态 | 缺口 |
|---|---|---|
| 画布移动/缩放/连线/删除 | 已实现 | 无浏览器回归门禁 |
| 节点添加 | 部分 | 点击添加，非侧栏拖入 |
| 属性配置 | 已实现 | 仍是手写配置，非 Node Manifest 生成 |
| Undo/Redo | 已实现 | 拖动过程可能产生过多历史项 |
| localStorage | 已实现 | 只维护当前工作流 |
| SQLite CRUD/乐观锁 | 已实现 | Update body 仍需强类型收紧 |
| 导入/导出 | API 已实现 | UI 入口缺失 |
| 自动保存 | 部分 | 失败只进 console，保存文案可能误导 |

### 4.2 执行引擎

| 能力 | 状态 | 证据/缺口 |
|---|---|---|
| NodeResult/ArtifactRef | 已实现 | contracts tests |
| Storyboard scene map | 已实现 | scene mapping integration tests |
| 上游结果注入 | 已实现 | Scheduler/Worker |
| 深层失败传播 | 已实现 | failure propagation tests |
| 取消竞态防护 | 已实现 | 状态条件更新 |
| RetryPolicy | 已实现 | retry tests + Migration 007 |
| external_job_id | 已实现 | Migration 006 + persistence tests |
| WorkerPool | 已实现 | worker pool tests |
| 执行收敛 | 已实现 | Scheduler/queue tests |
| 节点级手动重试 | 未闭环 | 前端 `retryNode` 仍是 TODO |
| 长任务重启续轮询 | 部分 | ID 持久化已完成，恢复编排仍需端到端验证 |
| 正式 schema migration 表 | 未实现 | 当前按 SQL 文件执行并忽略重复列 |

### 4.3 前端执行、Agent 和模板

| 能力 | 状态 | 缺口 |
|---|---|---|
| REST 启动/取消/轮询 | 已实现 | 错误态仍需统一 |
| WebSocket 重连/补拉 | 已实现 | Vitest 配置导致总测试失败 |
| ExecutionPanel | 已实现 | retry 按钮后端闭环未完成 |
| Agent generate preview | 已实现 | 严格工具调用/Schema constrained output 待加强 |
| GraphPatch diff/warning | 已实现 | 有损操作和 expected_version 需完整 UAT |
| TemplateSelector 装载 | 已实现 | 缺浏览器 E2E 证据 |
| Provider 设置 | 已实现 | API 只改内存，重启以 `.env` 为准 |
| 自定义 LLM | 已实现 | 单配置槽，尚非多 Provider CRUD |
| 资产预览/下载页 | 未完成 | API 有，完整产品页面不足 |
| 工作流列表/历史页 | 未完成 | API 有，UI 不完整 |

### 4.4 Provider 与媒体

| Provider/服务 | 状态 | 缺口 |
|---|---|---|
| Xiaomi MiMo | 真实调用通过 | 无自动外部 smoke 门禁 |
| Qwen Image 3.0 | 真实生图通过 | 多镜头成本/UAT 待完善 |
| Wan3.0 Video | 报告记录真实 UAT | 当前 venv 缺 Pillow，无法复现完整套件 |
| OpenAI | 适配器与 Contract | 未配置真实 Key UAT |
| Ollama | 适配器 | 本机服务未验证 |
| ComfyUI T2I | 基础 workflow | 本机服务未验证 |
| ComfyUI I2V | 占位 | 不可用于生产 |
| FFmpeg | 实现已增强 | 当前路径不可用，依赖未声明 |

## 5. 架构实现评估

### 5.1 优点

- API、Engine、Handler、Provider、Repository 和 Service 边界已经形成。
- 图像、视频、文本 Provider 按 capability 分离，Wan3 未混入 ComfyUI。
- 执行结果、外部 Job ID、重试字段和资产血缘均进入 SQLite。
- 前端工作流状态和 executionStore 开始拆分。
- 真实 Provider 与离线 Contract Test 并存，方向正确。
- 安全默认监听 127.0.0.1，Settings API 不返回 Key。

### 5.2 架构债务

1. **共享契约仍分散**：Node 类型/配置仍在前端、模型、Agent 各自维护。
2. **迁移器不够正式**：无 `schema_migrations`，靠 duplicate column 容错。
3. **配置持久化不足**：设置页只改内存，未落 ProviderConfig/secret reference。
4. **队列事务需压力验证**：claim 的 SELECT/BEGIN 时序仍需多连接并发证明。
5. **资产安全需收紧**：路径 root、原子写、MIME/大小和引用删除策略需统一验收。
6. **执行状态双轨**：`store.ts` 和 `executionStore.ts` 同时包含执行逻辑，应只保留一个事实入口。
7. **外部任务恢复未产品化**：Wan3 ID 可保存，但重启恢复的完整状态机和 UI 证据不足。

## 6. 发布阻断清单

| ID | 阻断项 | 优先级 | 关闭标准 |
|---|---|---:|---|
| R0-1 | Vitest 收集 Playwright | P0 | Vitest include 仅 `src/**/*.test.*`，`npm test` 通过 |
| R0-2 | Location mock 类型错误 | P0 | typecheck 和 build 通过 |
| R0-3 | Node 版本不一致 | P0 | 本地/README/CI 统一 Node 20+ |
| R0-4 | Pillow 未声明 | P0 | requirements 安装后完整 pytest 可收集 |
| R0-5 | FFmpeg 路径不可复现 | P0 | venv 声明依赖或系统安装；integration 19/19 当前环境通过 |
| R0-6 | CI 吞掉失败 | P0 | 移除关键 job 的 `|| true`，正确请求 `/api/health` |
| R0-7 | CI YAML 乱码 | P1 | UTF-8 可读 job 名称和注释 |
| R0-8 | Playwright 未执行 | P0 | Node 20 安装浏览器后核心 E2E 通过 |
| R0-9 | 前端 retry TODO | P1 | 失败节点可调用 retry API并恢复状态 |
| R0-10 | 报告元数据不一致 | P1 | 校正日期，记录 commit、环境、命令和原始输出 |

## 7. 里程碑

| 里程碑 | 当前状态 | 下一出口 |
|---|---|---|
| M0 工程基线 | 回归为红色 | R0-1 至 R0-6 全部关闭 |
| M1 编辑闭环 | 进行中 | 导入导出/列表/保存错误 UI + 浏览器 E2E |
| M2 Mock 执行闭环 | 后端基本完成 | Playwright 执行、retry UI、重启恢复 |
| M3 真实多模态 | 有历史 UAT | 当前锁定环境复现 Qwen/Wan3/FFmpeg 全链 |
| M4 Agent/模板 | 功能已接入 | E2E + 结构化工具 + 设置持久化 |
| M5 Release Candidate | 未达到 | 三平台 CI、发布检查、操作文档全绿 |

## 8. 下一阶段计划

### Sprint 0：恢复绿色门禁（2-3 天）

1. 配置 Vitest include/exclude，彻底隔离 Playwright。
2. 修复 `executionSocket.test.ts` 的 Window/Location mock 类型。
3. Node 升级到 20，更新 README 和启动检查。
4. 将 Pillow 和 FFmpeg 运行方案加入 requirements/安装文档。
5. 让 FFmpegService 使用明确配置或受控 fallback，并在当前 venv 复现 19 项测试。
6. 修复 CI UTF-8、`/api/health` 和 `|| true`。
7. 运行 unit、integration、typecheck、build、Playwright，并归档结果。

出口：根 `npm test`、typecheck、build、后端完整 pytest 均为绿色；Playwright 至少 Chromium 核心集通过。

### Sprint 1：产品闭环（1 周）

1. 完成节点级 retry API/UI。
2. 移除 `store.ts` 中旧执行状态，统一 executionStore。
3. 增加工作流列表、导入导出、保存失败与版本冲突 UI。
4. 增加资产列表、图片/片段/成片预览和下载。
5. 建立 Mock 浏览器全链 E2E。
6. 验证 Wan3 重启后凭 external_job_id 恢复且不重复提交。

出口：内容创作者可以在浏览器完成创建、执行、失败重试、刷新恢复、预览与下载。

### Sprint 2：Release Candidate（1-2 周）

1. 三平台 CI matrix 全绿。
2. SSRF、路径穿越、密钥脱敏、磁盘满和 Provider 超时演练。
3. DB 备份/恢复和迁移中断演练。
4. 100 节点、4 Worker、API P95 和内存基准。
5. 锁定 Provider/FFmpeg 环境，复现真实 MiMo → Qwen → Wan3 → FFmpeg 流程。
6. 完成安装、升级、回滚和故障排查手册。

出口：Release Checklist 全绿后才生成 `v1.0.0-rc.1`。

## 9. 文档治理

- 文档入口：[`README.md`](README.md)。
- 产品需求：[`product/PRD.md`](product/PRD.md)。
- 架构：[`architecture/SYSTEM-DESIGN.md`](architecture/SYSTEM-DESIGN.md)。
- Active 计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)。
- 历史计划只放 `plans/archive/`，不用于完成度判断。
- Provider 配置放 `integrations/`；测试证据放 `reports/`。
- 状态数字必须来自同一环境、同一 commit、同一次命令。
