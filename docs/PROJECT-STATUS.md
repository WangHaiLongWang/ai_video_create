# ai_video_create 项目状态报告

> 生成日期：2026-09-14
> 依据：对 frontend/、backend/、docs/、scripts/ 的全量代码扫描

---

## 1. 愿景目标

构建一个 **本地优先、可视化编排 AI 内容生成流程的 Web 平台**：

1. **可拖动流程图画布** — 用户通过拖拽节点、连线，自定义 AI 处理流水线
2. **Agent 生成流程** — 自然语言描述即可生成完整工作流
3. **完整纵向链路** — 提示词 → 文本描述 → 分段生成图片 → 图片转视频 → 合成关联
4. **本地运行** — 零 Docker、零外部数据库，Node + Python 即可启动

---

## 2. 当前项目进度总览

```
Phase A  ████████░░░░░░░░░░░░  ~40%   可编辑、可保存的类型化画布
Phase B  ░░░░░░░░░░░░░░░░░░░░  ~0%    可观察、可恢复的 Mock 执行器
Phase C  ░░░░░░░░░░░░░░░░░░░░  ~0%    真实多模态能力
Phase D  ░░░░░░░░░░░░░░░░░░░░  ~5%    Agent 与模板体验
Phase E  ░░░░░░░░░░░░░░░░░░░░  ~0%    发布验收
```

**总体完成度：约 15-20%（骨架已搭建，核心引擎未实现）**

---

## 3. 已完成内容

### 3.1 前端（frontend/）— 8 个源文件

| 已实现 | 说明 |
|--------|------|
| React + TypeScript + Vite 脚手架 | 构建工具链完整可用 |
| ReactFlow 画布 | 拖拽、缩放、平移、连线、小地图、控件 |
| 6 种节点类型 | textInput / storyboard / textToImage / imageToVideo / videoConcat / output |
| 节点面板（NodePalette） | 点击即可向画布添加节点 |
| 属性面板（PropertyPanel） | 选中节点后编辑配置（文本/数字/复选框） |
| 连线类型校验 | outputType → inputType 不匹配时拒绝连线 |
| Agent 编排面板（AgentComposer） | 中文提示词 → 解析镜头数 → 生成完整工作流 |
| Mock 执行引擎 | 逐节点模拟运行，带状态动画和进度条 |
| 取消执行 | runGeneration 计数器实现中断 |
| 自动保存 | 每次变更写入 localStorage，刷新恢复 |
| 暗色主题 UI | 响应式三栏布局，3 个断点适配 |
| 单元测试（2 个） | 工作流生成 + 连线校验 |

### 3.2 后端（backend/）— 5 个 Python 源文件

| 已实现 | 说明 |
|--------|------|
| FastAPI 应用骨架 | CORS 配置、自动 OpenAPI 文档 |
| 6 个 Pydantic 模型 | WorkflowSpec / WorkflowNode / WorkflowEdge / NodeData / Position / AgentRequest |
| 工作流校验器 | model_validator 检查唯一 ID、悬空边、端口类型兼容 |
| 工作流工厂 | `create_prompt_to_video()` 从提示词生成 6 节点线性管道 |
| `/api/health` | 返回 Python 版本、FFmpeg 可用性、运行模式 |
| `/api/workflows/validate` | 校验工作流结构 |
| `/api/agent/generate` | 接收提示词，返回 WorkflowSpec |
| API 测试（2 个） | 健康检查 + 生成端点 |

### 3.3 基础设施

| 已实现 | 说明 |
|--------|------|
| 单仓 monorepo | 根 package.json + concurrently 同时启动前后端 |
| 跨平台 Python 启动器 | scripts/run-python.cjs 自动定位 venv |
| 完整 PRD | docs/prd.md — 产品定位、功能分级、里程碑 |
| 架构设计文档 | docs/dp.md — 技术选型、目录结构、层栈设计 |
| 实施计划 | 15 个任务、5 个阶段、门禁标准 |

---

## 4. 未完成内容（差距分析）

### 4.1 Phase A 剩余（可编辑、可保存的类型化画布）

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 1 初始化单仓 | ✅ 完成 | 脚手架、健康检查、smoke test 均已就位 |
| Task 2 共享契约与节点注册表 | ⚠️ 部分完成 | 前后端各有类型定义但未统一 JSON Schema；缺少 TextSplit 节点；无环检测测试 |
| Task 3 SQLite 迁移与 Repository | ❌ 未开始 | 无数据库层、无迁移系统、无 Repository |
| Task 4 工作流 CRUD、导入导出 | ❌ 未开始 | 无 REST CRUD API、无导入导出、无撤销重做、无前端路由 |

### 4.2 Phase B（可观察、可恢复的 Mock 执行器）

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 5 Graph Compiler 与 map 语义 | ❌ 未开始 | 无编译器、无拓扑排序、无 map 展开 |
| Task 6 任务队列与 Worker | ❌ 未开始 | 无 SQLite 队列、无 Worker、无租约/心跳机制 |
| Task 7 执行事件与 WebSocket | ❌ 未开始 | 无事件总线、无 WebSocket、无实时状态推送 |
| Task 8 Handler 与 Mock 纵向链路 | ❌ 未开始 | 无 Handler 基类、无 Mock Provider 实现、无 E2E 测试 |

### 4.3 Phase C（真实多模态能力）

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 9 Provider 注册表与设置页 | ❌ 未开始 | 无 Provider 抽象、无设置 UI |
| Task 10 真实生图/生视频适配器 | ❌ 未开始 | 无 ComfyUI/HTTP 适配器 |
| Task 11 资产服务与 FFmpeg | ❌ 未开始 | 无文件存储管理、无 FFmpeg 调用 |

### 4.4 Phase D（Agent 与模板体验）

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 12 Workflow Agent（生成） | ⚠️ 极简版存在 | 当前 Agent 仅做正则解析 → 硬编码模板，无 LLM tool calling、无自修复循环、无 Schema 约束输出 |
| Task 13 Workflow Agent（修改与解释） | ❌ 未开始 | 无 GraphPatch、无 diff 预览、无确认流程 |
| Task 14 官方模板 | ⚠️ 前端有模板 | `createPromptToVideoWorkflow` 可用，但无后端模板服务、无模板注册/选择 UI |

### 4.5 Phase E（发布验收）

| 任务 | 状态 | 说明 |
|------|------|------|
| Task 15 安全、恢复、跨平台验收 | ❌ 未开始 | 无安全测试、无恢复测试、无性能基准 |

---

## 5. 文件资产清单

```
ai_video_create/
├── .gitignore
├── README.md                              ← 已更新项目名
├── package.json                           ← 已更新项目名
├── package-lock.json
├── docs/
│   ├── prd.md                             ✅ 完整 PRD
│   ├── dp.md                              ✅ 完整架构设计
│   ├── PROJECT-STATUS.md                  ← 本文档
│   └── plans/
│       └── 2026-09-14-ai-video-create-implementation-plan.md  ✅ 15 任务实施计划
├── scripts/
│   └── run-python.cjs                     ✅ 跨平台 Python 启动器
├── frontend/
│   ├── index.html
│   ├── package.json                       ← 已更新项目名
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── dist/                              ✅ 构建产物
│   └── src/
│       ├── main.tsx                       入口
│       ├── App.tsx                        5 个组件（TopBar/NodePalette/PropertyPanel/AgentComposer/Canvas）
│       ├── StudioNode.tsx                 自定义节点渲染
│       ├── store.ts                       Zustand 状态管理 + localStorage
│       ├── types.ts                       TypeScript 类型定义
│       ├── workflow.ts                    工作流工厂 + 节点目录 + 连线校验
│       ├── styles.css                     全部样式
│       └── workflow.test.ts               2 个 Vitest 测试
└── backend/
    ├── __init__.py
    ├── pyproject.toml                     ← 已更新项目名
    ├── requirements.txt                   5 个依赖
    ├── .venv/                             虚拟环境（已创建）
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                        FastAPI 3 个端点
    │   ├── models.py                      6 个 Pydantic 模型
    │   └── workflow_factory.py            工作流生成工厂
    └── tests/
        └── test_api.py                    2 个 pytest 测试
```

---

## 6. 关键缺失能力（按优先级排序）

### 🔴 P0 — 没有则无法运行

1. **SQLite 数据层** — 工作流无法持久化到服务端，刷新即丢失（仅靠 localStorage）
2. **工作流 CRUD API** — 前后端无真正交互，所有数据仅在浏览器内存中
3. **Mock 执行引擎** — 当前前端 mock 仅模拟延迟，无真实任务调度、状态机、失败传播
4. **WebSocket 实时通信** — 无执行进度推送，节点状态无法实时反映

### 🟡 P1 — 核心体验

5. **Graph Compiler** — 无拓扑排序、无 map 语义展开、无数组映射执行
6. **Handler 抽象层** — 无节点执行器基类，无法扩展新节点类型
7. **撤销/重做** — 前端无 undo/redo 栈
8. **导入/导出** — 工作流无法序列化为文件或从文件恢复

### 🟢 P2 — 完整产品

9. **真实 AI Provider** — 无 LLM/图像/视频模型接入
10. **FFmpeg 合成** — 无视频拼接能力
11. **Agent LLM 驱动** — 当前 Agent 仅正则解析，非真正 LLM 编排
12. **资产管理系统** — 无文件上传、存储、预览、下载

---

## 7. 推荐执行路线

### 第一步：打通前后端闭环（Task 3 + Task 4）

```
优先级：最高
预计：3-5 天
目标：工作流可以保存到 SQLite，刷新后恢复，前后端真正通信
产出：
  - backend/app/db/ 数据库连接 + 迁移
  - backend/app/repositories/ CRUD 操作
  - backend/app/api/workflows.py REST 端点
  - frontend/src/api/ HTTP 客户端
  - 前端切换为 API 调用（保留 localStorage 作为离线降级）
```

### 第二步：构建 Mock 执行引擎（Task 5 + 6 + 7 + 8）

```
优先级：高
预计：5-7 天
目标：点击"运行"后，任务真正被调度、执行、推送状态
产出：
  - Graph Compiler（拓扑排序 + map 展开）
  - SQLite 任务队列 + Worker
  - WebSocket 事件推送
  - 6 个 Handler（全部 Mock）
  - 端到端 Mock 测试
```

### 第三步：接入真实 AI 能力（Task 9 + 10 + 11）

```
优先级：中
预计：5-7 天
目标：至少一个 LLM + 一个图像生成 + FFmpeg 合成跑通
产出：
  - Provider 注册表 + Ollama/OpenAI 适配
  - ComfyUI 或 API 图像生成
  - FFmpeg normalize + concat
  - 资产存储与管理
```

### 第四步：完善 Agent 能力（Task 12 + 13 + 14）

```
优先级：中
预计：3-5 天
目标：自然语言 → 生成/修改工作流，带预览和确认
产出：
  - LLM tool calling Agent
  - GraphPatch + diff UI
  - 官方模板注册
```

---

## 8. 测试覆盖现状

| 范围 | 测试数 | 覆盖 |
|------|--------|------|
| 前端工作流生成 | 1 | ✅ 节点数、边数、参数传递 |
| 前端连线校验 | 1 | ✅ 类型兼容/不兼容 |
| 后端健康检查 | 1 | ✅ 状态码、返回结构 |
| 后端 Agent 生成 | 1 | ✅ 镜头数解析、结构正确性 |
| 后端工作流校验 | 0 | ❌ 无边界测试（重复 ID、环、悬空边） |
| SQLite / Repository | 0 | ❌ 不存在 |
| 执行引擎 | 0 | ❌ 不存在 |
| 安全 / 恢复 | 0 | ❌ 不存在 |
| **合计** | **4** | 覆盖率极低 |

---

## 9. 技术债务与风险

1. **前后端类型未统一** — 前端 `types.ts` 和后端 `models.py` 各自定义 WorkflowSpec，无共享 JSON Schema
2. **前端全在 App.tsx** — 5 个组件 + 根组件全在一个文件（~190 行），需拆分
3. **无错误边界** — 前端无 Error Boundary，后端无全局异常处理中间件
4. **localStorage 作为唯一存储** — 浏览器清除数据即丢失所有工作流
5. **Mock 执行无真实状态机** — 前端 mock 仅用 setTimeout 模拟，无 failed/blocked/skipped 状态
6. **无 i18n** — UI 字符串硬编码中文，无法国际化
7. **package-lock.json 存在但 node_modules 未提交** — 每次需要 npm install

---

## 10. 下一步行动项

- [ ] 创建 SQLite 数据库层（`backend/app/db/`）
- [ ] 实现工作流 CRUD REST API（`backend/app/api/workflows.py`）
- [ ] 前端接入后端 API（替换纯 localStorage 模式）
- [ ] 统一前后端 WorkflowSpec 类型定义（共享 JSON Schema）
- [ ] 拆分 App.tsx 为独立组件文件
- [ ] 添加后端工作流校验边界测试
- [ ] 启动 Graph Compiler 设计与实现
